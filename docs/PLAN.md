# Project plan

## Starting point

The repository currently contains planning files only. Begin with milestone 1; do not install a broad stack or build the later milestones in the first pass.

The first implementation should establish correct matching and understandable accounting. The research experiment follows once the engine can reproduce a small sequence exactly.

## Milestone 1: match and account for six events

Use one instrument, positive integer quantities, and integer prices in tick units. A monotonic event sequence determines time priority, including when events have the same timestamp. Avoid floating-point prices in the matching core.

### Matching rules

- A limit order crosses when its price permits a trade against the best opposite resting order. Any remainder rests at its limit price.
- Match the best price first, then the earliest resting order at that price.
- Execute at the resting order's price. A partial fill keeps the resting order's original priority.
- A market order consumes available opposite liquidity. Cancel its unfilled remainder when that liquidity runs out; it must not become a resting order.
- Cancel a resting order by its unique ID. A cancellation must not reorder other orders.
- Define explicit rejection behavior for duplicate IDs, nonpositive quantities, and cancellation of an unknown or completed order.

Order modification is outside this first milestone. If introduced later, document whether each modification retains or loses priority.

### Worked sequence

Prices below are integer ticks, not dollar amounts. A market order has no limit price.

| Event | Instruction | Expected trades | Resting book afterward |
|---|---|---|---|
| 1 | Add S1: sell 5 at 100 | None | Ask 100: S1 has 5 |
| 2 | Add S2: sell 4 at 100 | None | Ask 100: S1 has 5, then S2 has 4 |
| 3 | Market buy B1: quantity 6 | Buy 5 from S1 at 100, then 1 from S2 at 100 | Ask 100: S2 has 3 |
| 4 | Cancel S2 | None; cancel its remaining 3 | Empty |
| 5 | Add B2: buy 2 at 99 | None | Bid 99: B2 has 2 |
| 6 | Market sell S3: quantity 3 | Sell 2 to B2 at 99; cancel S3's remaining 1 | Empty |

### Acceptance checks

- Replaying the sequence yields the expected trades in the expected order and the expected book after every event.
- Each accepted order's submitted quantity equals its filled, resting, and canceled quantities combined.
- Resting quantities remain positive, completed orders leave the book, and bid/ask ordering remains valid.
- Matched participant inventory changes sum to zero. With fees disabled, their cash changes also sum to zero.
- Tests cover a crossing limit order, multiple price levels, rejection cases, and repeated deterministic replay in addition to the worked sequence.
- The matching logic is small enough to explain and debug directly, including a deliberately broken FIFO or partial-fill example.

Choose the smallest Python package layout and test setup that support this milestone. No market-data or plotting dependency is needed for the matching core.

## Milestone 2: define the experiment before scoring it

Status: drafted in [EXPERIMENT.md](EXPERIMENT.md), November 22, 2026; not yet frozen.

Write an experiment specification before comparing outcomes. Record the choices below as actual decisions, including why each choice is useful. They remain open at repository creation:

- The background order-flow generator, its parameters, and the price or fair-value process, if used.
- Strategy definitions, quote frequency, order size, inventory limits, and starting capital or inventory.
- The reference execution rules and the simplified rules to compare with them.
- Fees, event timing, any delay model, and the end-of-run inventory liquidation rule.
- The primary error measure, strategy comparison metric, development scenarios, and final evaluation scenarios.
- Run length, number of independent runs, seed handling, uncertainty method, and how unsupported or failed runs enter the report.

Use fixed quotes and inventory-adjusted quotes as initial baselines. State what an improvement means: lower inventory risk can come with less trading or lower profit, so report that tradeoff rather than treating lower inventory alone as a win.

Keep two questions separate:

1. With the strategy's submitted order trace held fixed, how far do simplified execution estimates deviate from reference executions? This isolates execution-model error.
2. When each strategy responds to its own fills and inventory, how does the execution model change its decisions and performance? Use paired background random streams where meaningful and document the coupling. Do not assume the resulting order books or strategy actions stay identical.

A fully specified synthetic queue has known positions. Queue uncertainty enters the approximate model when information is deliberately withheld. Do not give the reference engine arbitrary front-of-queue or back-of-queue fills and describe those as exact FIFO matching.

## Milestone 3: run a reproducible comparison

Status: implemented November 22, 2026 (`world.py`, `agents.py`, `venues.py`, `experiment.py`, `report.py`). The development run is complete. Freezing and final evaluation are pending.

Implement the smallest generator, strategies, and execution comparisons needed by the frozen experiment specification. Start with zero delay to establish a baseline; add fees and explicit delay scenarios in a documented order.

The report should include:

- False and missed fill estimates, partial-fill discrepancies, and executed-volume error.
- Profit after costs, inventory exposure, drawdown, and trading activity under each model.
- The liquidation assumptions and any residual inventory that cannot be liquidated.
- Paired performance differences, uncertainty intervals, and scenarios where strategy rankings agree or disagree.
- Failure cases and sensitivity to background flow, fees, and delays.

For synthetic experiments, calculate uncertainty across independent runs or appropriate paired run differences. Individual events within one run are not independent replications. If recorded data is added later, choose an uncertainty method that respects its temporal dependence.

Keep development and final evaluation scenarios separate. Freeze comparison choices before final evaluation. Record the configuration, seed set, code revision, and commands needed to reproduce every reported table. A ranking reversal is a possible outcome to measure, not a required result or a novel theory claim.

## Later extensions

Recorded market replay requires a specific source, a checked schema, recovery from missing data, permission to use the data, and an explicit description of what the feed reveals. Price-level data does not reveal individual queue positions. Order-level data improves observability but does not by itself validate counterfactual market impact.

A visual replay interface can follow the reproducible report. A C++ version can follow a measured performance need or a deliberate engineering goal. Compare implementations under the same workloads and machine/build conditions.

Gateways, multiple engine processes, multi-venue routing, production trading, and real-money execution are outside the first version.

## First-build checkpoint

After milestone 1, review the matching decisions and test failures together before expanding. If the implementation is hard to explain, simplify it and work through the core behavior. If a research question needs more infrastructure than the experiment can justify, consider using an established simulator for that question.

No calendar deadline or total time budget has been selected. This checkpoint is based on demonstrated behavior, not an assumed number of weeks.
