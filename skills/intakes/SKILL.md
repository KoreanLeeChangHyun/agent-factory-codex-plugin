---
name: intakes
description: Build canonical Agent Factory Intakes and acquire their required evidence.
---

# Agent Factory Intakes

## Entry contract

Use this skill for every Agent Factory Intake and its evidence acquisition.
Read `references/intake-management.md` completely, then read every capability
reference applicable to the evidence or decision being handled. Canonical
Intake writes must use `scripts/intake.py`.

## Reference routing

- `references/intake-management.md`: Create, validate, transition, and hand off canonical Intake packages.
- `references/intake-structure.md`: Apply the canonical Intake package structure and readiness contract.
- `references/analysis.md`: Inspect internal code, data, configuration, logs, tests, runtime behavior, and project documents.
- `references/web-search.md`: Collect and record authoritative external published evidence.
- `references/user-research.md`: Record direct observation, contextual inquiry, usability, and participant evidence.
- `references/interview.md`: Resolve one Human-owned project decision at a time.

## Assets and tools

`scripts/intake.py` is the only canonical Intake manager.
`scripts/requirements.txt` declares its dependencies; `assets/` owns its
profile and schema, and `tests/` owns regression coverage.
