# Results: experiment-v1

Specification: [EXPERIMENT.md](EXPERIMENT.md), frozen at tag `experiment-v1`. Final seeds 10000–10199, nine market settings, delays 0/1/5, fees 0/0.1. Every one of the 1,800 seed runs completed; none failed or was excluded, and no book side was empty for more than 2% of steps.

These are results about the synthetic market defined in the specification. They do not show how these models would behave on a real exchange.

## Q1: execution error on a fixed instruction log

Inventory-skew strategy, no delay, no fees. PnL is mark-to-fair per 1,000 steps; error is model minus reference. Brackets are 95% bootstrap intervals over 200 seeds.

**Profit error**

| p_jump | informed | reference PnL | touch | through | queue | queue-oracle |
|---|---|---|---|---|---|---|
| 0.01 | 0.0 | 49.1 [48.5, 49.7] | 39.1 [37.6, 40.7] | -11.3 [-12.7, -9.9] | 3.7 [3.0, 4.4] | 3.3 [2.8, 3.9] |
| 0.01 | 0.15 | 32.8 [32.3, 33.2] | 30.2 [28.9, 31.6] | -11.3 [-12.6, -10.0] | 1.9 [1.3, 2.4] | 1.9 [1.5, 2.2] |
| 0.01 | 0.3 | 20.7 [20.3, 21.1] | 24.1 [22.8, 25.4] | -9.6 [-10.7, -8.6] | 0.2 [-0.3, 0.7] | 0.8 [0.6, 1.1] |
| 0.02 | 0.0 | 58.0 [57.2, 58.8] | 54.4 [51.5, 57.4] | -10.5 [-12.2, -8.9] | 4.5 [3.4, 5.6] | 2.9 [2.1, 3.7] |
| 0.02 | 0.15 | 41.2 [40.5, 41.9] | 46.0 [43.3, 48.7] | -9.2 [-10.6, -7.8] | 3.6 [2.6, 4.6] | 2.5 [1.9, 3.1] |
| 0.02 | 0.3 | 28.5 [27.9, 29.1] | 38.7 [36.5, 41.0] | -8.8 [-10.2, -7.5] | 2.5 [1.6, 3.4] | 1.6 [1.0, 2.1] |
| 0.04 | 0.0 | 86.5 [85.3, 87.8] | 77.9 [72.5, 83.6] | -6.7 [-9.5, -4.1] | 11.4 [9.2, 13.6] | 6.2 [4.1, 8.3] |
| 0.04 | 0.15 | 67.2 [66.1, 68.4] | 71.0 [65.9, 76.2] | -6.2 [-8.8, -3.9] | 8.8 [6.7, 10.7] | 5.1 [3.3, 6.6] |
| 0.04 | 0.3 | 52.1 [51.1, 53.1] | 56.5 [52.3, 60.7] | -6.6 [-8.6, -4.8] | 6.4 [4.8, 8.0] | 3.5 [2.3, 4.6] |

**Executed-volume error, % of reference volume**

| p_jump | informed | touch | through | queue | queue-oracle |
|---|---|---|---|---|---|
| 0.01 | 0.0 | 69.5 [68.8, 70.2] | -7.4 [-7.7, -7.0] | 6.9 [6.7, 7.2] | 6.1 [5.9, 6.3] |
| 0.01 | 0.15 | 82.4 [81.4, 83.5] | -11.1 [-11.7, -10.6] | 5.1 [4.8, 5.4] | 5.0 [4.9, 5.2] |
| 0.01 | 0.3 | 103.3 [101.6, 105.0] | -15.1 [-15.7, -14.4] | 2.9 [2.5, 3.2] | 3.9 [3.7, 4.1] |
| 0.02 | 0.0 | 86.2 [85.3, 87.1] | -3.1 [-3.4, -2.8] | 9.5 [9.3, 9.8] | 6.6 [6.4, 6.8] |
| 0.02 | 0.15 | 100.7 [99.4, 102.1] | -4.9 [-5.3, -4.6] | 8.2 [7.9, 8.5] | 5.7 [5.5, 5.9] |
| 0.02 | 0.3 | 119.4 [117.4, 121.4] | -6.5 [-7.0, -6.0] | 7.1 [6.8, 7.4] | 4.7 [4.5, 4.9] |
| 0.04 | 0.0 | 86.8 [85.8, 87.8] | 3.6 [3.3, 3.8] | 12.5 [12.2, 12.7] | 7.4 [7.2, 7.5] |
| 0.04 | 0.15 | 96.7 [95.5, 97.9] | 2.5 [2.3, 2.8] | 11.5 [11.3, 11.8] | 6.6 [6.4, 6.8] |
| 0.04 | 0.3 | 105.5 [104.1, 106.9] | 1.9 [1.5, 2.2] | 10.8 [10.5, 11.1] | 5.9 [5.7, 6.1] |

- **Touch fills roughly double the volume and profit.** Its profit error is about as large as the reference profit itself in every setting.
- **Through understates profit by 6–11 ticks per 1,000 steps.** Its volume error is small at high volatility, but that is false fills and missed fills cancelling out, not accuracy (see the full report).
- **The queue estimate is closest: 3–13% too much volume, and up to 13% too much profit.** In one setting (low volatility, heavy informed flow) its profit error is indistinguishable from zero.
- **Market impact accounts for most of the queue estimate's remaining error.** Queue-oracle knows the exact queue and still overstates profit by 1–6 ticks. That residual comes from the background flow, which never reacts to the market maker's quotes. Better queue estimation cannot remove it, and recorded data without the market maker cannot reveal it.

## Q2: does the execution model change the strategy ranking?

The comparison is inventory skew minus fixed quotes, after fees and liquidation, paired by seed. In the reference, skew earns more in 21 of 27 settings at zero fees (20 of 27 with the 0.1 fee); the rest are inconclusive, all at the lowest volatility with zero or one step of delay. **No approximate model ever disagrees with the reference.** Every comparison either agrees or is inconclusive, and the inconclusive cases are exactly the ones where the reference itself is inconclusive.

In this world the simple fill models get the size of the profit badly wrong but not the choice between the two strategies.

## Development finding

On development seeds, every approximate model first appeared to reverse the ranking at high volatility with informed flow. That was a bug: a virtual quote that crossed the displayed book could take the same stale order again on every requote. It was fixed before freezing and is recorded in the specification's change log. This kind of double-counting can come from replaying data the strategy cannot change.

## Reproduce

```bash
git checkout experiment-v1
python3 -m venv .venv && .venv/bin/pip install -e '.[test,report]'
.venv/bin/python -m mmsim.experiment --seeds 10000-10199 --p-jump 0.01 0.02 0.04 --informed 0.0 0.15 0.3 --out artifacts/final-v1.jsonl
.venv/bin/python -m mmsim.report artifacts/final-v1.jsonl > artifacts/final-v1-report.md
```

The full report has every strategy, delay, and fee combination. The run takes about seven minutes on 14 cores.
