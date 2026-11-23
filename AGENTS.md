# Project agreements

## Resume work

Read README.md for current status, docs/PLAN.md for the specification and next milestone, and docs/DESIGN.md for decisions and references. Update status as work completes.

The initial repository is planning-only. The next implementation session starts with milestone 1: the six-event matching sequence, a minimal Python engine, and meaningful correctness tests. Review the core with the user before proceeding to the experiment milestones. Keep the work collaborative and explain matching and accounting decisions as they arise.

## Implementation and research

- Use python3 and integer tick prices in the matching core. Select dependencies when implementation needs them.
- Preserve FIFO price/time priority, partial-fill priority, deterministic ordering, and order-quantity accounting.
- Keep reference executions separate from approximate fill models. A full synthetic queue has known positions.
- Distinguish fixed-order-trace execution-error experiments from adaptive strategy comparisons.
- Specify experiments before scoring them; keep final evaluation scenarios separate from development.
- Report actual measurements, uncertainty, trading activity, failure cases, and terminal inventory handling.
- Describe synthetic conclusions as synthetic. Price-level replay does not establish actual queue positions or counterfactual fills and market impact.
- Keep gateways, UI work, multiple processes, live feeds, and a C++ port behind the milestones in docs/PLAN.md. Do not create placeholder modules or install a future stack in advance.
- Keep personal recruiting context, credentials, client material, downloaded raw data, and generated artifacts out of this public repository. Use synthetic example identifiers and data.
- Check source licenses before borrowing code or data. Credit references and preserve required attribution.
- Commit, push, create a PR, or change remote state only when the user requests it. Do not add generated-by or co-author footers.
