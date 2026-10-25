"""
Frontier-model forced-cut test (design: theory/FRONTIER_TEST.md).

For each source game: restore it at the branch round, hand both firms to --model, play --settle rounds,
then fork into arms that share that history:
    control   resampled continuation
    deviate   Firm B's price in the first arm round is forced to the Nash price (its model is still called)
    hidden    the rival's price is dropped from market data written after the fork

Sources are either eligible thesis games (both firms average index >= --min-index over the 10 rounds
before the branch) or run folders written by experiments_synthetic/duopoly.py.

Every Claude call is logged with its tokens and cost to <out>/usage.jsonl; the run stops before a round
that would start once that log's total passes --budget-usd.

Usage:
    uv run --extra claude python succession/frontier.py --model claude-fable-5-1 --effort medium \\
        --sources 1 --settle 5 --rounds 15 --arms control deviate --budget-usd 5
    uv run --extra claude python succession/frontier.py --model claude-haiku-5-5 \\
        --run-folders experiments_synthetic/experiments_runs/2_agents/<run> --branch-round 200 ...
Output: <out>/<source>_settle.jsonl and <out>/<source>_<arm>.jsonl, one line per firm-round.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import polars as pl

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from branch import Branch, eligible_thesis_games, load_run_folder, with_index

ARMS = ("control", "deviate", "hidden", "rpe", "brinfo")


def spent(usage: Path) -> float:
    if not usage.exists():
        return 0.0
    return sum(json.loads(line).get("cost_usd", 0.0) for line in usage.read_text().splitlines())


def eligible(src: pl.DataFrame, branch_round: int, min_index: float) -> bool:
    pre = with_index(src).filter(pl.col("round").is_between(branch_round - 9, branch_round))
    return pre.group_by("agent").agg(pl.col("delta").mean())["delta"].min() >= min_index


async def run_source(src, args, out: Path, stop) -> None:
    models = {"Firm A": args.model, "Firm B": args.model}
    name = src["experiment_timestamp"][0]
    settle_file = out / f"{name}_settle.jsonl"
    if args.settle:
        b = Branch(src, args.branch_round, models, "settle", strategy=args.strategy)
        if not await b.run(args.settle, settle_file, stop):
            return
    prior = [json.loads(line) for line in settle_file.read_text().splitlines()] if settle_file.exists() else []
    fork = max([r["round"] for r in prior], default=args.branch_round)
    arms = [
        Branch(src, args.branch_round, models, arm, prior=prior, hidden=arm == "hidden",
               deviate_at=fork + 1 if arm == "deviate" else None,
               mechanism=arm if arm in ("rpe", "brinfo") else None, strategy=args.strategy)
        for arm in args.arms
    ]
    await asyncio.gather(*(b.run(args.rounds, out / f"{name}_{b.cell}.jsonl", stop) for b in arms))


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="model for both firms after the branch")
    ap.add_argument("--effort", default=None, help="Claude output_config.effort (low ... max)")
    ap.add_argument("--run-folders", nargs="*", help="sources from duopoly.py run folders (default: thesis games)")
    ap.add_argument("--branch-round", type=int, default=200)
    ap.add_argument("--min-index", type=float, default=0.3)
    ap.add_argument("--sources", type=int, default=8)
    ap.add_argument("--settle", type=int, default=5, help="rounds both firms play before the fork")
    ap.add_argument("--rounds", type=int, default=15, help="rounds per arm")
    ap.add_argument("--arms", nargs="+", default=["control", "deviate"], choices=ARMS)
    ap.add_argument("--strategy", choices=["enforcer", "enforcer2"], default=None,
                    help="strategy given to both firms from the settling rounds on (succession/branch.py STRATEGIES)")
    ap.add_argument("--budget-usd", type=float, required=True, help="hard cap on logged spend")
    ap.add_argument("--call-cost-usd", type=float, default=0.15,
                    help="expected cost per call, used to skip sources the cap cannot finish")
    ap.add_argument("--parallel", type=int, default=4, help="sources played at once")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "runs" / "frontier")
    ap.add_argument("-y", action="store_true", help="skip the confirmation")
    args = ap.parse_args()

    if args.effort:
        os.environ["CLAUDE_EFFORT"] = args.effort
    args.out.mkdir(parents=True, exist_ok=True)
    usage = Path(os.environ.setdefault("CLAUDE_USAGE_LOG", str(args.out / "usage.jsonl")))

    if args.run_folders:
        pool = [load_run_folder(Path(p)) for p in args.run_folders]
        pool = [s for s in pool if eligible(s, args.branch_round, args.min_index)]
    else:
        pool = eligible_thesis_games(args.branch_round, args.min_index)
    sources = pool[: args.sources]
    calls = len(sources) * 2 * (args.settle + args.rounds * len(args.arms))
    print(f"{len(sources)} of {len(pool)} eligible sources; {args.model}"
          f"{f' (effort {args.effort})' if args.effort else ''}; up to {calls} calls; "
          f"cap ${args.budget_usd:.2f}, ${spent(usage):.2f} already logged in {usage}")
    if not sources:
        sys.exit("no eligible sources")
    if not args.y and input("Continue? [y/N] ").strip().lower() != "y":
        return

    def stop() -> bool:
        return spent(usage) >= args.budget_usd

    # Start a source only if the cap can still pay for it in full, reserving a source's worth for every
    # source already running, so the cap never leaves a game half played.
    per_source = 2 * (args.settle + args.rounds * len(args.arms)) * args.call_cost_usd
    sem, running = asyncio.Semaphore(args.parallel), []

    async def guarded(src):
        async with sem:
            name = src["experiment_timestamp"][0]
            if spent(usage) + per_source * (len(running) + 1) > args.budget_usd:
                print(f"skipped {name}: ${spent(usage):.2f} spent, a source needs ~${per_source:.2f}")
                return
            running.append(name)
            try:
                await run_source(src, args, args.out, stop)
                print(f"done {name}: ${spent(usage):.2f} logged", flush=True)
            finally:
                running.remove(name)

    await asyncio.gather(*(guarded(s) for s in sources))
    print(f"logged spend ${spent(usage):.4f}{' (cap reached)' if stop() else ''}")


if __name__ == "__main__":
    asyncio.run(main())
