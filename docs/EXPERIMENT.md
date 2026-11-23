# Experiment specification

Milestone 2 of [PLAN.md](PLAN.md). This file states the experiment before any outcome is scored. Status: **draft for review, November 22, 2026. Not frozen.** Section 9 describes how it is frozen and how later changes are recorded.

All prices and costs are in integer ticks, and all quantities are integer units. A "step" is one tick of simulated event time, not wall-clock time.

## 1. The simulated world

### Fair value

A hidden fair value `V` starts at 1000 ticks. At the start of each step it moves up 1 tick with probability `p_jump / 2`, down 1 tick with probability `p_jump / 2`, and otherwise stays put.

*Why:* An integer random walk keeps the matching core free of floats. It also gives the informed traders below something to trade on, which creates adverse selection, the main risk a market maker faces.

### Background participants

Every step runs the phases below in this fixed order. The order matters, so it is part of the specification.

1. **Fair value update** (above).
2. **Background cancellations.** Each resting background order is canceled independently with probability `p_cancel`.
3. **Background liquidity provider** (owner `bg-lp`). With probability `p_post`, it posts one limit order. The side is equally likely to be buy or sell. The order sits `k` ticks away from `V` on that side, where `k = 1 + Geometric(0.5)`, capped at 5. The size is uniform on 1–5. The provider only posts passively: if the price would cross the current book, it skips posting that step.
4. **Background taker** (owner `bg-taker`). With probability `p_market`, it sends one market order of size uniform on 1–3. With probability `informed`, the order is informed: it buys if the best ask is below `V`, sells if the best bid is above `V`, and otherwise does nothing. Uninformed orders pick a side at random.
5. **Market maker decision** (section 2), which applies after the latency delay in section 4.

*Why:* This is the smallest flow that gives a book with depth, a queue that changes through both trades and cancellations, and a source of adverse selection whose strength can be adjusted. The phase order means informed traders act after a jump and before the market maker can requote. This is the stale-quote risk that real market makers face.

### Baseline parameters

| Parameter | Value | Meaning |
|---|---|---|
| `p_jump` | 0.02 | Fair value moves about once every 50 steps |
| `p_cancel` | 0.02 | A background order lasts about 50 steps |
| `p_post` | 0.6 | Background limit orders per step |
| `p_market` | 0.3 | Background market orders per step |
| `informed` | 0.0 | Share of market orders that are informed |

These parameters can be calibrated only on development seeds, and only to keep the world working: the book must not empty out regularly, and the market maker must get a reasonable number of fills. Each calibration change and its reason go in section 10, before freezing.

## 2. Strategies

Both strategies have owner `mm`, quote one bid and one ask of size 2, and observe `V` directly.

*Why observe `V`:* Estimating fair value is a separate research question. Giving both strategies the same perfect reference price means any difference between models comes from execution, not from signal quality. This is a stated simplification, not a claim about real market makers.

- **Fixed quotes:** bid `V − h`, ask `V + h`, with `h = 2`.
- **Inventory-adjusted quotes:** bid `V − h − s`, ask `V + h − s`, with skew `s = round(γ · q)`, where `q` is the market maker's current inventory and `γ = 0.2`. Being long lowers both quotes, which makes selling more likely and buying less likely. This is the discrete version of the inventory term in Avellaneda–Stoikov. `γ` is fixed in advance and not tuned.
- **Inventory limit:** if a fill on one side would push `|q|` above 20, the strategy stops quoting that side.
- **Requoting:** every step, the strategy computes the quotes it wants. If a resting quote already has the desired price, it stays in place and keeps its queue position. Otherwise it is canceled and replaced. The market maker starts with zero cash and zero inventory.

*Why keep quotes that haven't changed:* Canceling and replacing every step would always put the quote at the back of the queue. That would make the queue model irrelevant and the experiment pointless.

## 3. Execution models

**Reference (`ref`).** The market maker's orders are submitted to the matching engine alongside background flow. FIFO priority, partial fills, and self-trade prevention apply exactly as in the engine. Its effect on the book is real: it changes what background traders see and trade against.

The three approximate models never put the market maker's orders in the book. They run the same background flow without the market maker, which produces market data like a recorded historical feed: trade prints plus the price-level book (total size at each price, with no order identities). Each model then estimates the market maker's fills from that data.

- **`touch`** (optimistic): a resting quote fills completely as soon as a trade prints at its price or better.
- **`through`** (pessimistic): a quote fills completely only if a trade prints strictly better than its price. Trades exactly at its price never fill it.
- **`queue`** (queue-position estimate): when the quote is placed, the quantity ahead of it is the displayed size at its price. A trade at that price uses up the quantity ahead first, and any excess fills the quote, possibly in part. When size at that level is canceled, the quantity ahead shrinks by `canceled × ahead / level_size`, which assumes cancellations are spread evenly through the queue. A trade strictly through the price fills whatever is left of the quote. This follows the probabilistic queue models described in the HftBacktest documentation.

*Why these three:* `touch` and `through` are the two common shortcuts and roughly bracket the answer from above and below. `queue` is the standard better approximation. The question is how much better it is.

The approximate models leave out two things on purpose: queue information (they know the size at each price, not the order identities) and market impact (the background flow never reacts to the market maker's quotes). The measured error includes both. Section 7 says how they are reported separately.

## 4. Costs, delay, and the end of a run

- **Fees:** each unit the market maker fills as maker costs `fee` ticks. The baseline is `fee = 0`. Fee scenarios: `fee ∈ {0, 0.1}`. Fees are kept as a separate ledger in tenths of a tick, so the matching core stays in integer ticks.
- **Delay:** a market maker instruction decided at step `t` reaches the book at the start of phase 5 in step `t + d`. Cancels are delayed too, so a quote can fill while its cancel is still on the way. The baseline is `d = 0`. Delay scenarios: `d ∈ {0, 1, 5}`. Approximate models apply the same delay.
- **Warm-up:** the market maker does not quote during the first 1,000 steps, so the background book can fill in.
- **Run length:** 20,000 steps after warm-up.
- **End of run:** final inventory is closed out at `V_T` minus a liquidation cost of `c = 2` ticks per unit, roughly crossing a typical spread. Both the mark-to-fair value and the liquidated value are reported.

*Why add fees and delay after the baseline:* With `fee = 0, d = 0`, the only source of model error is the queue and impact assumptions. Each later scenario adds one effect at a time, so changes in the results can be attributed to it.

## 5. The two questions

**Q1: Execution error on a fixed order trace.** For each run and strategy, the reference run records every instruction the market maker sent: what it was, when, and at what price and size. Each approximate model then scores **that same instruction log** against the background-only market data. The strategy does not get to respond differently, so any difference from the reference fills is purely execution-model error.

**Q2: Adaptive comparison.** Each strategy runs once with each execution model as its fill source and reacts to its own estimated fills and inventory. The quotes, inventory, and results can all diverge. The question is whether the model changes which strategy looks better.

## 6. Pairing and random streams

Each run seed gives separate random streams for fair value, cancellations, provider posts, and taker orders. Each is a `random.Random` seeded from the string `f"{seed}:{stream}"`. The fair-value path is therefore **identical** across models and strategies for a given seed. The background streams start in the same state, but they drift apart once the book differs, because the number of cancel draws depends on how many orders are resting, and informed takers react to the quotes. This drift is part of market impact, and it is the reason section 3 says the error includes impact.

Within a seed, comparisons are always **paired**: the same seed under different models or strategies.

## 7. Metrics

**Primary error measure (Q1):** profit error, `PnL_model − PnL_ref` for the same instruction log, measured on mark-to-fair value at the end of the run and scaled per 1,000 steps. It is the primary measure because profit is the number a backtest is used to decide on.

**Secondary error measures (Q1)**, per run, with each quantity summed over the market maker's orders:
- false fill volume `Σ max(0, filled_model − filled_ref)`
- missed fill volume `Σ max(0, filled_ref − filled_model)`
- net executed-volume error as a share of reference volume
- the number of orders that fill fully under one model but only partly under the other

**Separating impact from queue error (Q1):** a fourth diagnostic model, `queue-oracle`, runs on the same background-only world as the other approximations, but with order-level data. It knows exactly which background orders are ahead of each quote, and which of them trade or cancel. Because its queue position is exact, its error against `ref` comes from impact alone. The gap between `queue-oracle` and `queue` is the error from queue approximation. This is a diagnostic, not a candidate model.

**Strategy comparison metric (Q2):** the per-run paired difference `PnL(inventory-adjusted) − PnL(fixed)` after fees and liquidation, together with the paired differences in inventory standard deviation, maximum absolute inventory, worst drawdown, and filled volume. The ranking from each model **agrees** with the reference if the difference has the same sign as the reference's and its 95% interval excludes zero, **disagrees** if the sign is opposite and the interval excludes zero, and is **inconclusive** otherwise.

Lower inventory risk counts as a gain only if it is reported next to the profit and volume it costs. The report shows the trade-off and does not declare a winner from one number.

## 8. Scenarios, runs, and uncertainty

**Development grid:** `p_jump ∈ {0.01, 0.04}` × `informed ∈ {0, 0.3}` × `fee ∈ {0, 0.1}` × `d ∈ {0, 1, 5}`, with **seeds 0–99**. Development runs are for debugging, calibration within section 1's limits, and checking that the report pipeline works.

**Final evaluation:** the same grid plus held-out settings that were never run during development (`p_jump = 0.02`, `informed = 0.15`), with **seeds 10000–10199**. Final seeds are run once, after freezing.

**Uncertainty:** each run produces one value for each statistic. Results are reported as the mean across runs with a 95% percentile bootstrap interval (10,000 resamples, bootstrap seed fixed in the config), and the bootstrap is always run on **paired per-seed differences**. Events within a run are never treated as independent samples.

**Failures:** a run that raises an error, fails an invariant check, or leaves one side of the book empty for more than 5% of steps after warm-up counts as a failure. Failed runs are counted and listed with their seeds in the report. They are left out of averages, but never dropped silently. A run that stops quoting because it hit the inventory limit is not a failure. Instead, the time spent at the limit is reported.

## 9. Freezing and reproducibility

1. Calibrate only on development seeds and record every change in section 10.
2. Freeze: set this file's status to *Frozen*, commit it, and tag the commit `experiment-v1`.
3. Run the final seeds from that tag. Each reported table lists the configuration file, the seed range, the commit hash, and the command that produced it.
4. Any change after freezing becomes `experiment-v2` with a written reason. Results under v1 are still reported.

A ranking reversal is one possible result to measure. It is not a goal. Null results get reported in the same way as other results.

## 10. Change log

- 2026-11-22: initial draft.
