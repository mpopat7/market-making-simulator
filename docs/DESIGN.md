# References and design decisions

## Agreed direction

The planning review on November 22, 2026 favored a small matching engine plus a statistical execution-model experiment. The full exchange, gateway, and interface proposal would introduce several implementation tasks before the experiment could run.

The initial Python engine is a correctness and understanding checkpoint. The finished research artifact must add a reproducible comparison and explain the conditions under which its conclusions hold.

The review's strongest objection was that a small engine and a standard inventory-skew comparison could become a tutorial exercise. The response is to specify and measure execution-model error, compare with established approaches, and report the effects on strategy decisions. Original implementation work does not imply a new market-making theory.

## Project references

- [TanishqM1/TradingEngine](https://github.com/TanishqM1/TradingEngine) describes a C++ matching engine with a Go gateway and a Next.js interface. It informed the initial exchange-simulator concept; the gateway and distributed components are deferred here.
- [aiden-ma-uwaterloo/microtick](https://github.com/aiden-ma-uwaterloo/microtick) describes C++ matching, synthetic backtesting, and CSV replay. It is a reference for the separation between matching behavior and strategy evaluation. Its reported performance figures are not benchmarks for this project.

These repositories are architectural references. No implementation code has been copied into this repository. Check a source's license before reusing its code, data, or assets, and preserve any required attribution.

## Research references

- Marco Avellaneda and Sasha Stoikov, [High-frequency trading in a limit order book](https://math.nyu.edu/inmemoriam/avellaneda/HighFrequencyTrading.pdf), Quantitative Finance, 2008. The paper models inventory risk and quoting decisions; inventory-aware market making is an established baseline.
- [HftBacktest order-fill and queue-model documentation](https://hftbacktest.readthedocs.io/en/latest/order_fill.html). It describes queue approximations, partial-fill models, and the limitations of replaying market data that the strategy cannot change. Compare these approaches before selecting the execution experiment.
- [Coinbase Exchange WebSocket channels](https://docs.cdp.coinbase.com/exchange/websocket-feed/channels). The documentation distinguishes price-level book updates from order/trade messages. The unauthenticated Level 2 batch channel groups updates every 50 milliseconds. Access, capture reliability, historical coverage, and data-use terms must be checked if this source is selected.

## Interpretation rules

- The synthetic engine is a reference within its documented world. It is not ground truth for real-market strategy performance.
- A historical price touch does not prove that a resting order would fill. Explain queue and available-volume assumptions next to any replay result.
- An inventory-risk reduction must be assessed alongside profit, executed volume, and costs.
- A result under selected simulated conditions supports a claim about those conditions. Broader market claims require additional evidence.
- Record null results and disagreements between models. Do not change the comparison merely to produce a ranking reversal or positive profit.
- Claims of speed require measured workloads, hardware, build configuration, and reproducible commands.

## Matching-core decisions (milestone 1)

- **Rejections are events, not exceptions.** `submit()` returns a `Rejected` event so a replay log records every instruction's outcome. Rejected instructions leave the book and order records unchanged.
- **Rejection cases.** A reused order ID (including one from a completed order), a quantity that is not a positive integer, a limit price that is not a positive integer tick, and cancellation of an unknown, filled, or already canceled order.
- **Self-trade prevention cancels the newest order.** When an incoming order reaches a resting order from the same owner, the incoming remainder is canceled with reason `SELF_TRADE`. Earlier trades against other owners stand and the resting order keeps its queue position. A market maker quoting both sides would otherwise trade with itself after a quote crosses, which is a wash trade and distorts volume and fill counts.
- **Invariant checks live in the package**, not only in the tests, so simulation runs in later milestones can call `check_invariants` too.
- **Best-price lookup scans the price levels.** This is linear in the number of levels and is enough for the experiment's book sizes. Replace it with a sorted structure only if profiling shows a need.
