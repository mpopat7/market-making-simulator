"""Summarize experiment rows into the tables in docs/EXPERIMENT.md, section 7.

    python3 -m mmsim.report artifacts/dev.jsonl > artifacts/dev-report.md

Every interval is a 95% percentile bootstrap over per-seed values (paired
differences where the statistic is a difference). Seeds with any failure in a
scenario are excluded from that scenario and listed.
"""

import argparse
import json
from collections import defaultdict

import numpy as np

FEES = (0.0, 0.1)
LIQUIDATION_COST = 2
EMPTY_LIMIT = 0.05
RESAMPLES = 10_000
BOOTSTRAP_SEED = 0
PER_1000 = 1000 / 20000


def bootstrap(values: list[float]) -> tuple[float, float, float]:
    data = np.asarray(values, dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    means = data[rng.integers(0, len(data), (RESAMPLES, len(data)))].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return data.mean(), low, high


def fmt(stat: tuple[float, float, float], digits: int = 1) -> str:
    mean, low, high = stat
    return f"{mean:.{digits}f} [{low:.{digits}f}, {high:.{digits}f}]"


def net_pnl(pnl: float, volume: int, position: int, fee: float) -> float:
    """Profit after fees and liquidating the final inventory."""
    return pnl - fee * volume - LIQUIDATION_COST * abs(position)


def load(path: str):
    rows = [json.loads(line) for line in open(path)]
    failed = defaultdict(set)
    for row in rows:
        scenario = (row["p_jump"], row["informed"])
        if row["question"] == "failure" or row.get("empty_fraction", 0) > EMPTY_LIMIT:
            failed[scenario].add(row["seed"])
    kept = [r for r in rows if r["question"] != "failure"
            and r["seed"] not in failed[(r["p_jump"], r["informed"])]]
    return kept, failed


def q1_table(rows, fee: float) -> list[str]:
    groups = defaultdict(list)
    for r in rows:
        if r["question"] == "q1":
            groups[r["p_jump"], r["informed"], r["delay"], r["strategy"], r["model"]].append(r)
    lines = [
        f"### Q1: execution error on the fixed instruction log (fee {fee})",
        "",
        "PnL error is model minus reference, mark-to-fair after fees, per 1,000 steps. "
        "Volumes are summed per run.",
        "",
        "| p_jump | informed | delay | strategy | model | PnL error | false volume | missed volume | net volume error % | n |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for key in sorted(groups):
        g = groups[key]
        pnl_error = [((r["pnl"] - fee * r["volume"]) - (r["ref_pnl"] - fee * r["ref_volume"])) * PER_1000 for r in g]
        net = [100 * (r["volume"] - r["ref_volume"]) / max(r["ref_volume"], 1) for r in g]
        lines.append(
            "| " + " | ".join(str(k) for k in key) + " | "
            + " | ".join([fmt(bootstrap(pnl_error)),
                          fmt(bootstrap([r["false_volume"] for r in g]), 0),
                          fmt(bootstrap([r["missed_volume"] for r in g]), 0),
                          fmt(bootstrap(net)), str(len(g))]) + " |"
        )
    return lines


def q2_table(rows, fee: float) -> list[str]:
    by_seed = defaultdict(dict)
    for r in rows:
        if r["question"] == "q2":
            by_seed[r["p_jump"], r["informed"], r["delay"], r["model"]][r["seed"], r["strategy"]] = r
    lines = [
        f"### Q2: skew minus fixed, each strategy adapting to its own fills (fee {fee})",
        "",
        "Differences are paired by seed. PnL is after fees and liquidation, per 1,000 steps. "
        "Verdict compares the model's sign with the reference's.",
        "",
        "| p_jump | informed | delay | model | PnL difference | inventory std difference | volume difference | verdict | n |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    def stats(key):
        runs = by_seed[key]
        seeds = sorted({s for s, _ in runs if (s, "fixed") in runs and (s, "skew") in runs})
        diff = lambda f: [f(runs[s, "skew"]) - f(runs[s, "fixed"]) for s in seeds]
        pnl = bootstrap(diff(lambda r: net_pnl(r["pnl"], r["volume"], r["position"], fee) * PER_1000))
        return pnl, bootstrap(diff(lambda r: r["inventory_std"])), bootstrap(diff(lambda r: r["volume"])), len(seeds)

    def sign(stat):
        _, low, high = stat
        return 1 if low > 0 else -1 if high < 0 else 0

    for key in sorted(by_seed):
        pnl, inv, vol, n = stats(key)
        ref_sign = sign(stats((*key[:3], "ref"))[0])
        if key[3] == "ref":
            verdict = "reference"
        elif sign(pnl) == 0 or ref_sign == 0:
            verdict = "inconclusive"
        else:
            verdict = "agrees" if sign(pnl) == ref_sign else "disagrees"
        lines.append("| " + " | ".join(str(k) for k in key) + " | "
                     + " | ".join([fmt(pnl), fmt(inv, 2), fmt(vol, 0), verdict, str(n)]) + " |")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rows")
    args = parser.parse_args()
    rows, failed = load(args.rows)

    out = [f"# Results from {args.rows}", ""]
    for fee in FEES:
        out += q1_table(rows, fee) + [""] + q2_table(rows, fee) + [""]
    out.append("### Failed or excluded seeds")
    out.append("")
    if not any(failed.values()):
        out.append("None.")
    for (p_jump, informed), seeds in sorted(failed.items()):
        if seeds:
            out.append(f"- p_jump {p_jump}, informed {informed}: {sorted(seeds)}")
    print("\n".join(out))


if __name__ == "__main__":
    main()
