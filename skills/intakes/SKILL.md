---
name: intakes
description: Manage an optional topic-scoped evidence ledger when the Human explicitly requests Intake or substantial research needs durable canonical evidence.
---

# Agent Factory Intakes

## Entry contract

Use this skill only after the optional Intake route is selected. It is not a
precondition for bounded implementation or Human feedback. For every selected
Intake and every activity recorded in it,
Read `references/intake-management.md` completely, then read every capability
reference applicable to the activity being handled. Canonical
Intake writes must use `scripts/intake.py`.

## Reference routing

- `references/intake-management.md`: Create, append to, validate, and reference canonical Intake ledgers.
- `references/intake-structure.md`: Apply the canonical topic-scoped entry contract.
- `references/analysis.md`: Inspect internal code, data, configuration, logs, tests, runtime behavior, and project documents.
- `references/web-search.md`: Collect and record authoritative external published evidence.
- `references/user-research.md`: Record direct observation, contextual inquiry, usability, and participant evidence.
- `references/interview.md`: Resolve one Human-owned project decision at a time.

## Assets and tools

`scripts/intake.py` is the only canonical Intake manager.
`scripts/intake_agent_exec.py` delegates evidence acquisition to an isolated
Intake Agent session and emits only a compact ACK and terminal result.
`intake.py session-bind`, `session-show`, and `session-clear` own the Intake's
operational Codex session association without changing semantic document
version. Delegated-writer locks live under the OS temporary
directory rather than the repository.
`scripts/requirements.txt` declares its dependencies; `assets/` owns its
profile and schema, and `tests/` owns regression coverage.
