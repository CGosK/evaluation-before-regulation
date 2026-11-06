"""
Wave-9 games (followup/WAVE9_PLAN.md; November 2026, not part of the submission): the forced-raise test on
Opus 5.5 and Haiku 4.5, from each model's saved state at the branch round of the paper's 8 high-price states.

    --check            both arms for 2 rounds from one Haiku 4.5 state, in runs/wave9/checks/ (not results)
    default            control and raise arms, 12 rounds each, for both models and all 8 states
    --family F         one model only (the launcher runs one process per model)

The raise arm forces Firm B's price in the first arm round to 1.10 times the price its model chose, capped at
the highest price anyone would pay. It is succession/branch.Branch with run() copied and that one change.
Launches append the time, the command and the SHA-256 of the plan and the code to runs/wave9/launch.txt.

Usage:  .venv/bin/python followup/run_wave9.py [--check] [--config-dir ~/.claude] [--dry-run]
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "followup"), str(ROOT / "succession"), str(ROOT)]
from run_wave5 import CODE, sha  # noqa: E402

OUT = ROOT / "followup/runs/wave9"
PLAN = ROOT / "followup/WAVE9_PLAN.md"
FILES = CODE + ["followup/run_wave9.py", "succession/branch.py", "succession/frontier.py"]
RAISE, WTP = 1.10, 4.51
ROUNDS = 12
SETTLED = {  # family -> (model, effort, folder holding its saved settling rounds)
    "opus55": ("claude-opus-5-5", "medium", ROOT / "followup/runs/wave4/frontier/opus55"),
    "haiku45": ("claude-haiku-4-5", None, ROOT / "succession/runs/frontier/haiku45"),
}


def raise_branch_class():
    from branch import Branch, market_data

    class RaiseBranch(Branch):
        """Branch.run with Firm B's price in round deviate_at forced to RAISE times its model's price."""

        async def run(self, rounds, out, stop=None):
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists():
                for line in out.read_text().splitlines():
                    r = json.loads(line)
                    self.history[r["firm"]][r["round"]] = r["state"]
            done = max(int(k) for k in self.history["Firm B"]) - self.start
            with out.open("a") as fh:
                for t in range(self.start + 1 + done, self.start + 1 + rounds):
                    if stop and stop():
                        return False
                    answers = await asyncio.gather(
                        *(self.agents[f].act(self.prompt(f, t)) for f in ("Firm A", "Firm B"))
                    )
                    resp = {a["agent_name"]: a["content"] for a in answers}
                    prices = {f: float(resp[f]["chosen_price"]) for f in ("Firm A", "Firm B")}
                    chosen_b = prices["Firm B"]
                    if t == self.deviate_at:
                        prices["Firm B"] = min(RAISE * chosen_b, WTP * self.alpha)
                    q, pi = self.step_market(prices)
                    for f in ("Firm A", "Firm B"):
                        state = {
                            "plans": resp[f].get("plans", ""),
                            "insights": resp[f].get("insights", ""),
                            "observations": resp[f].get("observations", ""),
                            "market_data": market_data(
                                prices, q, pi, f, self.hidden, self.feedback(f, prices, pi)
                            ),
                            "chosen_price": prices[f],
                        }
                        self.history[f][t] = state
                        fh.write(
                            json.dumps(
                                {
                                    "source": self.source,
                                    "cell": self.cell,
                                    "firm": f,
                                    "round": t,
                                    "model": self.models[f],
                                    "price": prices[f],
                                    "profit": pi[f],
                                    "delta": (prices[f] - self.nash) / (self.mono - self.nash),
                                    "forced": f == "Firm B" and t == self.deviate_at,
                                    "model_price": chosen_b if f == "Firm B" else prices[f],
                                    "state": state,
                                }
                            )
                            + "\n"
                        )
                    fh.flush()
            return True

    return Branch, RaiseBranch


async def play_family(family: str, out: Path, rounds: int, n_sources: int):
    from branch import eligible_thesis_games

    Branch, RaiseBranch = raise_branch_class()
    model, _, settled = SETTLED[family]
    models = {"Firm A": model, "Firm B": model}
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for src in eligible_thesis_games(200, 0.3)[:n_sources]:
        name = src["experiment_timestamp"][0]
        settle = out / f"{name}_settle.jsonl"
        if not settle.exists():
            shutil.copy(settled / f"{name}_settle.jsonl", settle)
        prior = [json.loads(line) for line in settle.read_text().splitlines()]
        fork = max(r["round"] for r in prior)
        control = Branch(src, 200, models, "control", prior=prior)
        raised = RaiseBranch(src, 200, models, "raise", prior=prior, deviate_at=fork + 1)
        jobs += [b.run(rounds, out / f"{name}_{b.cell}.jsonl") for b in (control, raised)]
    await asyncio.gather(*jobs)
    print(f"✅ done {family}", flush=True)


def environment(family: str, config_dir: str, usage: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_EFFORT", "CLAUDE_USAGE_LOG")}
    env.update(
        LLM_PROVIDER="claude-code",
        CLAUDE_THINKING_BUDGET="0",
        MAX_THINKING_TOKENS="0",
        CLAUDE_CONFIG_DIR=config_dir,
        CLAUDE_USAGE_LOG=str(usage),
    )
    env.setdefault("CLAUDE_PAUSE_FILE", str(OUT / "pause.json"))
    if SETTLED[family][1]:
        env["CLAUDE_EFFORT"] = SETTLED[family][1]
    return env


def launch(families: list, out: Path, rounds: int, n: int, config_dir: str) -> int:
    procs = []
    for fam in families:
        log = out / "logs" / f"{fam}.txt"
        log.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            __file__,
            "--family",
            fam,
            "--out",
            str(out),
            "--rounds",
            str(rounds),
        ]
        cmd += ["--sources", str(n)]
        env = environment(fam, config_dir, out / "frontier" / fam / "usage.jsonl")
        procs.append(
            subprocess.Popen(
                cmd, cwd=ROOT, env=env, stdout=open(log, "w"), stderr=subprocess.STDOUT
            )
        )
    return max(p.wait() for p in procs)


def check(out: Path) -> bool:
    d = out / "frontier" / "haiku45"
    ok = True
    settle = [json.loads(line) for line in next(d.glob("*_settle.jsonl")).read_text().splitlines()]
    fork = max(r["round"] for r in settle)
    for arm in ("control", "raise"):
        rows = [
            json.loads(line) for line in next(d.glob(f"*_{arm}.jsonl")).read_text().splitlines()
        ]
        forced = [(r["round"], r["firm"]) for r in rows if r["forced"]]
        if arm == "raise":
            b = next(r for r in rows if r["forced"])
            good = (
                forced == [(fork + 1, "Firm B")]
                and abs(b["price"] - 1.10 * b["model_price"]) < 1e-9
            )
            print(
                f"raise: forced {forced}, price {b['price']:.4f} = 1.10 x {b['model_price']:.4f}: {'OK' if good else 'FAIL'}"
            )
        else:
            good = not forced
            print(f"control: forced {forced}: {'OK' if good else 'FAIL'}")
        first = min(r["round"] for r in rows)
        good &= first == fork + 1
        print(f"  {arm} starts at round {first}, after the saved state's round {fork}")
        ok &= good
    return ok


def record():
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    code = "; ".join(f"{c} {sha(ROOT / c)}" for c in FILES)
    with open(OUT / "launch.txt", "a") as fh:
        fh.write(f"{stamp} games: {' '.join(sys.argv)}\n")
        fh.write(f"WAVE9_PLAN.md sha256 {sha(PLAN)}\n")
        fh.write(f"code sha256: {code}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--family", choices=sorted(SETTLED))
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--rounds", type=int, default=ROUNDS)
    ap.add_argument("--sources", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config-dir", default=os.path.expanduser("~/.claude"))
    a = ap.parse_args()
    if a.family:
        asyncio.run(play_family(a.family, a.out / "frontier" / a.family, a.rounds, a.sources))
        sys.exit(0)
    if a.dry_run:
        from branch import eligible_thesis_games

        names = [s["experiment_timestamp"][0] for s in eligible_thesis_games(200, 0.3)[:8]]
        for fam, (_, _, settled) in SETTLED.items():
            have = [n for n in names if (settled / f"{n}_settle.jsonl").exists()]
            print(f"{fam}: {len(have)} of 8 saved states found in {settled.relative_to(ROOT)}")
        sys.exit(0)
    if a.check:
        code = launch(["haiku45"], OUT / "checks", 2, 1, a.config_dir)
        sys.exit(0 if code == 0 and check(OUT / "checks") else 1)
    record()
    sys.exit(launch(sorted(SETTLED), OUT, ROUNDS, 8, a.config_dir))
