# Market making simulator

An order-book simulator for studying how execution assumptions affect market-making backtests.

A backtest can look profitable because it assumes an order fills whenever the market touches its price. In an actual order queue, other orders may trade first, only part of the order may execute, or the quote may arrive too late. This project will measure how those differences affect strategy comparisons.

## Research question

How much do simplified execution assumptions change the apparent performance of a market-making strategy, and under which simulated market conditions do they change the strategy ranking?

The first version will compare fixed quotes with inventory-adjusted quotes in a controlled synthetic market. A matching engine with explicit order queues will provide the reference executions within that market. Simpler fill rules will provide the comparisons.

## Status

Planning, November 22, 2026. This repository contains the project specification and the first implementation task. The matching engine, strategies, experiments, and interface have not been implemented, and there are no measured results yet.

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

Read [AGENTS.md](AGENTS.md), then start with milestone 1 in [docs/PLAN.md](docs/PLAN.md). Dependencies and the package layout will be selected when implementation begins.
