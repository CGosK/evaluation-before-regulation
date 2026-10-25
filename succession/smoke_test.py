"""
Stage 1 of theory/FRONTIER_TEST.md: a small paid run of the whole pipeline before any scale spend.

  1. Haiku 5.5 plays a fresh 10-round game through the thesis runner (experiments_synthetic/duopoly.py).
  2. That game is branched at round 10 into control, deviate and hidden arms (Haiku, 3 rounds each).
  3. Fable 5.1 (effort medium) takes over one saved collusive thesis game at round 200 for both firms,
     plays 2 settling rounds, then control and deviate arms of 2 rounds each.

Then it checks the price override and the hidden arm, counts refusals, retries and failed stops, and
reports measured tokens and cost per call with projections for stages 2 and 3.

Usage:
    uv run --extra claude python succession/smoke_test.py --offline   # rehearsal with the stub model, free
    uv run --extra claude python succession/smoke_test.py             # paid: about 70 calls, capped at $4
Needs PRICING_ANTHROPIC_API_KEY (environment or repo-root compute.env) unless --offline, plus
PRICING_ANTHROPIC_WORKSPACE_ID for an organisation-level key. A free token-count preflight runs first.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "experiments_synthetic" / "experiments_runs" / "2_agents"
HAIKU, FABLE = "claude-haiku-5-5", "claude-fable-5-1"
STAGE2_HAIKU_CALLS = 8 * 2 * 200 + 8 * 2 * 15 * 3  # formation to round 200, then three 15-round arms
FABLE_CALLS_PER_SOURCE = 2 * (5 + 2 * 15)  # 5 settling rounds, control and deviate of 15 rounds


def sh(args: list, env: dict) -> None:
    print("$", " ".join(str(a) for a in args), flush=True)
    subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, env=env, check=True)


def preflight() -> None:
    """Free check before any paid call: token counting is not billed, but it needs a valid key, the
    right workspace and access to each model id."""
    import anthropic
    from poseidon_compute import llm_config

    llm_config._load()
    client = anthropic.Anthropic(api_key=os.environ["PRICING_ANTHROPIC_API_KEY"], max_retries=1)
    workspace = os.getenv("PRICING_ANTHROPIC_WORKSPACE_ID")
    for model in (HAIKU, FABLE):
        try:
            n = client.messages.count_tokens(
                model=model, messages=[{"role": "user", "content": "Set a price."}],
                **({"workspace_id": workspace} if workspace else {}),
            )
        except anthropic.APIStatusError as e:
            hint = ("\nAdd PRICING_ANTHROPIC_WORKSPACE_ID=wrkspc_... to compute.env (or use a workspace key)."
                    if "workspace" in str(e) else "")
            sys.exit(f"preflight failed for {model}, nothing was billed: {e.message}{hint}")
        print(f"preflight ok: {model} ({n.input_tokens} tokens counted, not billed)")


def records(path: Path) -> list:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="use the stub model; no key, no spend")
    ap.add_argument("--out", type=Path, default=ROOT / "succession" / "runs" / "smoke")
    args = ap.parse_args()

    out = args.out / ("offline" if args.offline else "paid")
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} already has results; move it aside to rerun")
    out.mkdir(parents=True, exist_ok=True)
    usage = out / "usage.jsonl"
    env = {**os.environ, "CLAUDE_USAGE_LOG": str(usage)}
    if args.offline:
        env["LLM_PROVIDER"] = "stub"
    else:
        preflight()

    before = set(RUNS.glob("*")) if RUNS.exists() else set()
    sh(["experiments_synthetic/duopoly.py", "--model", HAIKU, "--rounds", 10, "--plot-every", 0, "-y"], env)
    folder = max(set(RUNS.glob("*")) - before, key=lambda p: p.stat().st_mtime)
    sh(["succession/frontier.py", "--model", HAIKU, "--run-folders", folder, "--branch-round", 10,
        "--min-index", -1e9, "--settle", 0, "--rounds", 3, "--arms", "control", "deviate", "hidden",
        "--budget-usd", 0.5, "--out", out / "haiku", "-y"], env)
    sh(["succession/frontier.py", "--model", FABLE, "--effort", "medium", "--sources", 1,
        "--settle", 2, "--rounds", 2, "--arms", "control", "deviate", "--budget-usd", 4,
        "--out", out / "fable", "-y"], env)

    # --- checks -------------------------------------------------------------------------------
    calls = records(usage)
    rows = [r for f in sorted(out.glob("*/*.jsonl")) if f.name != "usage.jsonl" for r in records(f)]
    formation = json.loads((folder / "results.json").read_text())
    played = {HAIKU: sum(len(v) for v in formation.values()), FABLE: 0}
    for r in rows:
        played[r["model"]] = played.get(r["model"], 0) + 1
    problems = []
    forced = [r for r in rows if r["forced"]]
    if len(forced) != 2:
        problems.append(f"expected 2 forced rounds (one per model), found {len(forced)}")
    for r in forced:
        print(f"forced cut: {r['model']} round {r['round']}: model chose {r['model_price']:.3f}, "
              f"market used {r['price']:.3f}")
    hidden = [r for r in rows if r["cell"] == "hidden"]
    if not hidden or any("Competitor" in r["state"]["market_data"] for r in hidden):
        problems.append("hidden arm still shows the rival's price (or did not run)")

    print("\nmodel             calls  played  refusals  max_tokens  mean in  mean out  $/call     total $")
    per_call = {}
    for model in (HAIKU, FABLE):
        c = [x for x in calls if x["model"] == model]
        n = len(c) or 1
        cost = sum(x["cost_usd"] for x in c)
        per_call[model] = cost / n
        refusals = sum(x["stop_reason"] == "refusal" for x in c)
        cut_off = sum(x["stop_reason"] == "max_tokens" for x in c)
        print(f"{model:17} {len(c):5} {played[model]:7} {refusals:9} {cut_off:11} "
              f"{sum(x['input_tokens'] for x in c) / n:8.0f} {sum(x['output_tokens'] for x in c) / n:9.0f} "
              f"{cost / n:8.4f} {cost:10.4f}")
        if len(c) != played[model]:
            problems.append(f"{model}: {len(c)} calls for {played[model]} firm-rounds (retries or failures)")
    per_haiku, per_fable = per_call[HAIKU], per_call[FABLE]
    details = [x.get("output_tokens_details") for x in calls if x.get("output_tokens_details")]
    if details:
        print("output token breakdown (first Fable call):",
              next((x["output_tokens_details"] for x in reversed(calls) if x["model"] == FABLE), details[-1]))

    print(f"\nprojection at measured cost: stage 2 (Haiku, ~{STAGE2_HAIKU_CALLS:,} calls) "
          f"${STAGE2_HAIKU_CALLS * per_haiku:.2f}; stage 3 (Fable) ${FABLE_CALLS_PER_SOURCE * per_fable:.2f} "
          f"per source, so ${60 - STAGE2_HAIKU_CALLS * per_haiku:.0f} left buys "
          f"{int((60 - STAGE2_HAIKU_CALLS * per_haiku) // max(FABLE_CALLS_PER_SOURCE * per_fable, 1e-9))} sources")
    fable_notes = [r["state"]["plans"] for r in rows if r["model"] == FABLE][:1]
    if fable_notes:
        print("\nfirst Fable PLANS:", fable_notes[0][:400])
    print("\nPROBLEMS:\n- " + "\n- ".join(problems) if problems else "\nAll checks passed.")


if __name__ == "__main__":
    main()
