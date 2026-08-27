# Loop engineering adoption inquiry

Investigate how to adopt loop engineering into this Agent Factory plugin while preserving the Human-owned test and risk boundaries.

Scope:

- Read `AGENTS.md`, `skills/agent/SKILL.md`, `skills/agent/references/main.md`, `work.md`, `review.md`, `inquery.md`, and `skills/inquery/references/workspace.md`.
- Inspect the current `skills/agent/scripts/agent_exec.py`, `tests/test_agent_exec.py`, and the existing uncommitted changes without modifying product files.
- Research current loop-engineering practice on the web. Prefer original/primary sources and preserve URLs. At minimum compare: bounded stop conditions, persistent state/spine, maker-checker separation, retry/circuit-breaker behavior, human escalation, budgets, and fresh-context versus resumable-session tradeoffs.
- Evaluate a concrete, minimal loop lifecycle that fits the existing `submit`, `send`, `status`, `result`, `inbox`, `cancel`, and `reconcile` commands. The lifecycle must not use platform sub-agents and must preserve exact managed Codex session IDs.
- Design machine-checkable completion and failure criteria for repeated Work -> Review -> bounded Work revision -> Review cycles. Work and Review Agents remain prohibited from tests. Human-authorized tests are orchestration evidence, not Work/Review Agent actions.
- Conduct only safe read-only parser/state experiments needed to validate the proposed CLI shape. Do not edit canonical product files, run repository tests/builds/linters/type checks, or perform irreversible/external actions.

Completion condition: write unrefined evidence and observations inside `.agent-factory/inquery/loop-engineering-20260828/`, then publish an evidence-backed result through the runtime-declared result path. Include the smallest bounded implementation proposal, state machine, stop conditions, CLI/API surface, failure modes, compatibility with the current uncommitted sandbox fix, and limitations.
