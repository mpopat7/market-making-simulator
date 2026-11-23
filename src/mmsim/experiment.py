"""Run the experiment in docs/EXPERIMENT.md and write one JSON row per result.

    python3 -m mmsim.experiment --seeds 0-99 --out artifacts/dev.jsonl

For each (scenario, seed) the runner plays:
  * one reference world per (strategy, delay), with the market maker in the book;
  * one background-only world, shared by every approximate model: Q1 replays
    of each reference instruction log, and Q2 adaptive market makers.
The background-only world never sees the market maker, so one copy serves all
of them. Fees do not change any decision, so they are applied in the report.
"""

import argparse
import json
import os
import traceback
from multiprocessing import Pool

from .agents import STRATEGIES, Agent
from .venues import MODELS, EngineVenue, VirtualVenue
from .world import STEPS, WARMUP, Params, World

DELAYS = (0, 1, 5)


def _play(world: World, agents: list[Agent]) -> None:
    for _ in range(WARMUP + STEPS):
        world.advance()
        for agent in agents:
            agent.phase5(world.step, world.value)
        world.finish_step()


def _empty_fraction(world: World) -> float:
    return world.empty_side_steps / STEPS


def run_seed(p_jump: float, informed: float, seed: int, delays=DELAYS) -> list[dict]:
    params = Params(p_jump=p_jump, informed=informed)
    scenario = {"p_jump": p_jump, "informed": informed, "seed": seed}
    rows = []

    reference = {}
    for strategy in STRATEGIES:
        for delay in delays:
            world = World(params, seed)
            agent = Agent(lambda ledger, w=world: EngineVenue(w, ledger), strategy, delay)
            _play(world, [agent])
            reference[strategy.name, delay] = (agent, world.value, _empty_fraction(world))

    world = World(params, seed)
    replays, adaptive = {}, {}
    for (name, delay), (ref_agent, _, _) in reference.items():
        for model in MODELS:
            make = lambda ledger, m=model: VirtualVenue(world, ledger, m)
            replays[name, delay, model] = Agent(make, trace=ref_agent.trace)
    for strategy in STRATEGIES:
        for delay in delays:
            for model in MODELS:
                make = lambda ledger, m=model: VirtualVenue(world, ledger, m)
                adaptive[strategy.name, delay, model] = Agent(make, strategy, delay)
    _play(world, [*replays.values(), *adaptive.values()])
    background_empty = _empty_fraction(world)

    for (name, delay), (ref_agent, ref_value, ref_empty) in reference.items():
        ref = ref_agent.summary(ref_value)
        rows.append({**scenario, "question": "q2", "strategy": name, "delay": delay,
                     "model": "ref", "empty_fraction": ref_empty, **ref})
        for model in MODELS:
            replay = replays[name, delay, model]
            est = replay.summary(world.value)
            ref_fills, est_fills = ref_agent.ledger.filled, replay.ledger.filled
            sizes = ref_agent.ledger.size
            false_volume = sum(max(0, est_fills.get(o, 0) - ref_fills[o]) for o in sizes)
            missed_volume = sum(max(0, ref_fills[o] - est_fills.get(o, 0)) for o in sizes)
            full_mismatch = sum(
                (ref_fills[o] == sizes[o]) != (est_fills.get(o, 0) == sizes[o]) for o in sizes
            )
            rows.append({**scenario, "question": "q1", "strategy": name, "delay": delay,
                         "model": model, "empty_fraction": max(ref_empty, background_empty),
                         "ref_pnl": ref["pnl"], "ref_volume": ref["volume"],
                         "ref_position": ref["position"], "ref_final_value": ref_value,
                         "pnl": est["pnl"], "volume": est["volume"], "position": est["position"],
                         "final_value": world.value, "false_volume": false_volume,
                         "missed_volume": missed_volume, "full_fill_mismatch": full_mismatch,
                         "orders": len(sizes)})

    for (name, delay, model), agent in adaptive.items():
        rows.append({**scenario, "question": "q2", "strategy": name, "delay": delay,
                     "model": model, "empty_fraction": background_empty,
                     **agent.summary(world.value)})
    return rows


def _job(args) -> list[dict]:
    p_jump, informed, seed, delays = args
    try:
        return run_seed(p_jump, informed, seed, delays)
    except Exception:
        return [{"p_jump": p_jump, "informed": informed, "seed": seed,
                 "question": "failure", "error": traceback.format_exc()}]


def _seed_range(text: str) -> list[int]:
    start, _, end = text.partition("-")
    return list(range(int(start), int(end or start) + 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", required=True, help="inclusive range, e.g. 0-99")
    parser.add_argument("--p-jump", type=float, nargs="+", default=[0.01, 0.04])
    parser.add_argument("--informed", type=float, nargs="+", default=[0.0, 0.3])
    parser.add_argument("--delays", type=int, nargs="+", default=list(DELAYS))
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=os.cpu_count())
    args = parser.parse_args()

    jobs = [(p, i, s, tuple(args.delays)) for p in args.p_jump for i in args.informed
            for s in _seed_range(args.seeds)]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as out, Pool(args.workers) as pool:
        for done, rows in enumerate(pool.imap_unordered(_job, jobs), start=1):
            for row in rows:
                out.write(json.dumps(row) + "\n")
            print(f"\r{done}/{len(jobs)} seeds", end="", flush=True)
    print()


if __name__ == "__main__":
    main()
