# Market making simulator

An order-book simulator for studying how execution assumptions affect market-making backtests.

A backtest can look profitable because it assumes an order fills whenever the market touches its price. In an actual order queue, other orders may trade first, only part of the order may execute, or the quote may arrive too late. This project will measure how those differences affect strategy comparisons.

## Research question

How much do simplified execution assumptions change the apparent performance of a market-making strategy, and under which simulated market conditions do they change the strategy ranking?

The first version will compare fixed quotes with inventory-adjusted quotes in a controlled synthetic market. A matching engine with explicit order queues will provide the reference executions within that market. Simpler fill rules will provide the comparisons.

## Status

Milestones 1 and 2 done, and milestone 3 built, November 22, 2026. The engine, the synthetic market, both strategies, the four fill models, the experiment runner, and the report are implemented and tested. The development run (seeds 0–99) has been completed. The experiment specification is not yet frozen and the final evaluation has not been run, so there are no reported results yet.

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[test]'
.venv/bin/python -m pytest

# development run and report (about 90 seconds on 14 cores)
.venv/bin/pip install -e '.[report]'
.venv/bin/python -m mmsim.experiment --seeds 0-99 --out artifacts/dev.jsonl
.venv/bin/python -m mmsim.report artifacts/dev.jsonl > artifacts/dev-report.md
```

## First version

- One instrument and a Python matching engine with price/time priority.
- Market and limit orders, cancellations, partial fills, and deterministic event replay.
- Fixed quotes and inventory-adjusted quotes under a documented order-flow model.
- Comparisons of reference executions with simplified fill assumptions, including fees and, after the baseline works, explicit delays.
- A reproducible report covering execution errors, profit after costs, inventory exposure, uncertainty, and strategy rankings.

The first milestone is a six-event example that checks matching and accounting. The [project plan](docs/PLAN.md) specifies its expected outcomes and the experiment milestones.

## Interpretation

The reference engine defines correct executions under the synthetic market's stated rules. It does not establish how hypothetical orders would have traded in a real market. Recorded exchange data is a later extension, subject to the information available about queues, delays, and market impact.

Inventory-aware quoting and queue models already have a substantial literature. The intended contribution is a tested implementation and a measured comparison with reproducible assumptions. See the [references and design decisions](docs/DESIGN.md).

## Continue development

Read [AGENTS.md](AGENTS.md), then start with milestone 1 in [docs/PLAN.md](docs/PLAN.md). The simulator has no runtime dependencies. Tests use pytest and the report uses numpy.
