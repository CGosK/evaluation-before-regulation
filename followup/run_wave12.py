"""
Wave-12 games (study 3, followup/WAVE12_PLAN.md; not part of the submission): the limit in a mixed market, and
the cap's split. 100-round P1 duopolies with wave 2's settings (effort medium, thinking budget 0), all arms
interleaved:

    mixed            Opus 5.5 against Sonnet 5.5, no rule, seeds 1-10 (followup/mixed_rule_game.py)
    A2               the same pairing under wave 6's limit with no threat (rules6/limit_no_threat.py), seeds 1-10
    C2               Sonnet 5.5 under wave 11's cap (rules11/cap_fixed.py), seeds 21-40
    D                Sonnet 5.5 under the same cap from round 31 (rules12/cap_from31.py), seeds 1-20
    sonnet_baseline  Sonnet 5.5 with no rule, seeds 16-20, alongside wave 2's 10 and wave 11's 5
    Opus is Firm A in odd seeds of the mixed arms, as in wave 8.

    --check        no calls: the late cap against random prices, its wording against wave 11's cap, check_source
                   on the three rules, both reused rules' hashes against their waves' records, and the job list
    --check-game   in runs/wave12/checks/ (not results): one 33-round Haiku 4.5 game under the late cap, and a
                   3-round mixed game under the limit in each slot order; records the hashes too
    (default)      the games; appends the time, the command and the SHA-256 of the plan and the code to
                   runs/wave12/launch.txt

Run the usage guard alongside:  usage_guard2.py --runs followup/runs/wave12 --games 65
Usage:  .venv/bin/python followup/run_wave12.py [--check | --check-game] [--parallel 15] [--dry-run]
            [--config-dir ~/.claude]
"""

import argparse
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "followup"), str(ROOT / "succession")]
from platform_rules import check_source, load_rule  # noqa: E402
from prevention45 import active, done  # noqa: E402
from run_wave2 import FAMILIES  # noqa: E402
from run_wave5 import sha  # noqa: E402

OUT = ROOT / "followup/runs/wave12"
PLAN = ROOT / "followup/WAVE12_PLAN.md"
LIMIT = "followup/rules6/limit_no_threat.py"
CAP = "followup/rules11/cap_fixed.py"
LATE = "followup/rules12/cap_from31.py"
SHAS = {  # the reused rules, as their waves' launch records hold them
    LIMIT: "e658a5557f62c956ff3c13fc311bad31fbb91331fe04d73d9b755a47bff1b3a3",
    CAP: None,  # read from runs/wave11/launch.txt below
}
MIXED = "opus55+sonnet55"
ARMS = [
    ("mixed", MIXED, "none", range(1, 11)),
    ("A2", MIXED, LIMIT, range(1, 11)),
    ("C2", "sonnet55", CAP, range(21, 41)),
    ("D", "sonnet55", LATE, range(1, 21)),
    ("sonnet_baseline", "sonnet55", "none", range(16, 21)),
]
CODE = [
    "followup/platform_rules.py",
    "followup/platform_game.py",
    "followup/mixed_game.py",
    "followup/mixed_rule_game.py",
    "followup/run_wave2.py",
    "followup/run_wave5.py",
    "followup/run_wave12.py",
    "followup/wave12_results.py",
    "followup/usage_guard.py",
    "followup/usage_guard2.py",
    "experiments_synthetic/common.py",
    "src/agents/llm_providers.py",
    LIMIT,
    CAP,
    LATE,
]
LINE = "Platform price limit for my next price: 1.74."


def cap_sha() -> str:
    lines = (ROOT / "followup/runs/wave11/launch.txt").read_text().splitlines()
    code = [line for line in lines if line.startswith("code sha256:")][-1]
    return dict(p.rsplit(" ", 1) for p in code[len("code sha256: ") :].split("; "))[CAP]


def slots(seed: int) -> tuple:
    return ("opus55", "sonnet55") if seed % 2 else ("sonnet55", "opus55")


def jobs() -> list:
    """Every game, interleaved: the first game of each arm, then the second, and so on."""
    queues = [[(arm, fam, rule, s) for s in seeds] for arm, fam, rule, seeds in ARMS]
    out = []
    while any(queues):
        out += [q.pop(0) for q in queues if q]
    return out


def check(seed: int = 0) -> bool:
    rng = random.Random(seed)
    late, fixed = load_rule(str(ROOT / LATE)), load_rule(str(ROOT / CAP))
    fails = []
    for game in range(20):
        rule, ref = late(game), fixed(game)
        for t in range(1, 101):
            prices = {f: round(rng.uniform(1.3, 2.2), 2) for f in ("Firm A", "Firm B")}
            rule.round = ref.round = t
            out = rule.override(t, dict(prices))
            ref_out = ref.override(t, dict(prices))
            for f, p in prices.items():
                line = rule.notice(f, out, {})
                want = p if t < 31 else min(p, 1.74)
                told = "Platform notice: my price of" in line
                bad = out[f] != want or told != (t >= 31 and p > 1.74)
                bad |= (LINE in line) != (t >= 30)
                if t >= 31:
                    bad |= out != ref_out or line != ref.notice(f, ref_out, {})
                if bad:
                    fails.append(f"game {game} round {t} {f}")
    ok_rule = not fails
    ok_src = not any(check_source(ROOT / r) for r in (LIMIT, CAP, LATE))
    ok_sha = sha(ROOT / LIMIT) == SHAS[LIMIT] and sha(ROOT / CAP) == cap_sha()
    n = len(jobs())
    print(
        f"late cap: {'OK' if ok_rule else f'FAIL in {fails[:5]}'} (and the same as wave 11's cap from round 31)"
    )
    print(f"check_source on the three rules: {'OK' if ok_src else 'FAIL'}")
    print(
        f"limit rule unchanged since wave 6, cap unchanged since wave 11: {'OK' if ok_sha else 'FAIL'}"
    )
    print(f"jobs: {n} games, {n * 200:,} calls; first six: {[j[:2] + (j[3],) for j in jobs()[:6]]}")
    return ok_rule and ok_src and ok_sha and n == 65


def check_game_ok() -> bool:
    ok = True
    games = OUT / "checks/games/2_agents"
    found = sorted(games.glob("*_rule-w12-cap174-from31_*/results.json"))
    if not found:
        print("late cap check game: none found")
        return False
    res = json.loads(found[-1].read_text())
    rows = [(int(t), o) for r in res.values() for t, o in r.items()]
    line = all((LINE in o["market_data"]) == (t >= 30) for t, o in rows)
    forced = [(t, o) for t, o in rows if o.get("forced")]
    clip = all(t >= 31 and o["chosen_price"] == 1.74 and o["model_price"] > 1.74 for t, o in forced)
    told = all("Platform notice" in o["market_data"] for _, o in forced)
    above = [o for t, o in rows if t >= 31 and not o.get("forced") and o["chosen_price"] > 1.74]
    good = line and clip and told and not above and len(rows) == 66
    print(
        f"late cap check game: line only from round 30 {line}; {len(forced)} replaced, all from round 31 to "
        f"1.74 {clip}, all told {told}; unreplaced prices above 1.74 from round 31: {len(above)}: "
        f"{'OK' if good else 'FAIL'}"
    )
    ok &= good
    calls = [json.loads(x) for x in (OUT / "checks/usage.jsonl").read_text().splitlines()]
    effort = {c["model"]: c.get("effort") for c in calls}
    for model in ("claude-opus-5-5", "claude-sonnet-5-5"):
        good = effort.get(model) == "medium"
        print(f"{model}: effort {effort.get(model, 'NO CALLS')}: {'OK' if good else 'FAIL'}")
        ok &= good
    for seed in (1, 2):
        found = sorted(
            games.glob(f"*_mixed-{MIXED}_rule-w6-limit-no-threat_*seed{seed}/results.json")
        )
        if not found:
            print(f"mixed check game s{seed}: none found")
            ok = False
            continue
        meta = json.loads((found[-1].parent / "metadata.json").read_text())
        res = json.loads(found[-1].read_text())
        intended = dict(zip(["Firm A", "Firm B"], (FAMILIES[f][0] for f in slots(seed))))
        lines = [
            ("Platform price limit for my next price" in o["market_data"])
            for r in res.values()
            for o in r.values()
        ]
        good = meta["agents_models"] == intended and all(lines) and len(lines) == 6
        print(
            f"mixed check game s{seed}: models {meta['agents_models']}, limit line in {sum(lines)} of {len(lines)} firm-rounds: {'OK' if good else 'FAIL'}"
        )
        ok &= good
    return ok


def env_for(config_dir: str, games: Path, family: str = "") -> dict:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_EFFORT"}
    env.update(
        CLAUDE_EFFORT="medium",  # Opus 5.5 and Sonnet 5.5, as in their own games; Haiku 4.5 ignores it
        CLAUDE_THINKING_BUDGET="0",
        MAX_THINKING_TOKENS="0",
        CLAUDE_USAGE_LOG=str(games.parent / "usage.jsonl"),
        CLAUDE_CONFIG_DIR=config_dir,
        CLAUDE_PAUSE_FILE=str(OUT / "pause.json"),
        FOLLOWUP_GAMES=str(games),
        FOLLOWUP_FAMILY=family,
    )
    return env


async def play(arm, family, rule, seed, rounds, games, sem, config_dir, dry) -> str:
    log = games.parent / "logs" / f"{arm}_s{seed}.txt"
    flags = ["--provider", "claude-code", "--rounds", str(rounds), "--seeds", str(seed)]
    flags += ["--plot-every", "0", "-y"]
    if family == MIXED:
        models = [FAMILIES[f][0] for f in slots(seed)]
        cmd = ["followup/mixed_rule_game.py", "--models", *models, "--name", MIXED, "--rule", rule]
        cmd += [*flags, "--model", FAMILIES["opus55"][0]]
        env = env_for(config_dir, games)
    else:
        cmd = ["followup/platform_game.py", "--rule", rule, *flags, "--model", FAMILIES[family][0]]
        env = env_for(config_dir, games, family)
    cmd = [str(ROOT / ".venv/bin/python"), *cmd]
    if dry:
        return f"{arm} s{seed}: {' '.join(cmd[1:])}"
    if done(log):
        return f"{arm} s{seed}: already done"
    if active(log):
        return f"{arm} s{seed}: still running elsewhere"
    log.parent.mkdir(parents=True, exist_ok=True)
    async with sem:
        with open(log, "w") as fh:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=ROOT, env=env, stdout=fh, stderr=fh
            )
            code = await proc.wait()
    return f"{arm} s{seed}: {'done' if done(log) else f'FAILED (exit {code})'}"


async def main(todo, rounds, games, parallel, config_dir, dry):
    sem = asyncio.Semaphore(parallel)
    tasks = [
        asyncio.ensure_future(play(*j, r, games, sem, config_dir, dry))
        for j, r in zip(todo, rounds)
    ]
    for t in asyncio.as_completed(tasks):
        print(await t, flush=True)


def record(mode: str):
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(OUT / "launch.txt", "a") as fh:
        fh.write(f"{stamp} {mode}: {' '.join(sys.argv)}\n")
        fh.write(f"WAVE12_PLAN.md sha256 {sha(PLAN)}\n")
        fh.write(f"code sha256: {'; '.join(f'{c} {sha(ROOT / c)}' for c in CODE)}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--check-game", action="store_true")
    ap.add_argument("--parallel", type=int, default=15)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config-dir", default=os.path.expanduser("~/.claude"))
    a = ap.parse_args()
    if a.check:
        sys.exit(0 if check() else 1)
    if a.check_game:
        if not check():
            sys.exit("check failed")
        if not a.dry_run:
            record("check game")
        todo = [
            ("check-late", "haiku45", LATE, 1),
            ("check-mixed", MIXED, LIMIT, 1),
            ("check-mixed", MIXED, LIMIT, 2),
        ]
        asyncio.run(main(todo, [33, 3, 3], OUT / "checks/games", 3, a.config_dir, a.dry_run))
        sys.exit(0 if a.dry_run or check_game_ok() else 1)
    if not a.dry_run:
        if not PLAN.exists():
            sys.exit("no plan: WAVE12_PLAN.md must be written before any game runs")
        if not check():
            sys.exit("check failed")
        if not check_game_ok():
            sys.exit("run --check-game first")
        record("games")
    todo = jobs()
    asyncio.run(main(todo, [100] * len(todo), OUT / "games", a.parallel, a.config_dir, a.dry_run))
