---
name: lifecycle
description: Route Agent Factory work through Intake, Work Unit execution, and Human review.
---

# Agent Factory Lifecycle

## Entry contract

Use this skill for Agent Factory lifecycle routing and canonical artifact
ownership. Read `references/lifecycle-entry.md` completely before lifecycle
work, then read each additional reference applicable to the operation.

## Reference routing

- `references/lifecycle-entry.md`: Apply lifecycle ownership, mandatory sequence, capability coordination, and integration boundaries.
- `references/lifecycle.md`: Follow the end-to-end Intake, Goal launch, execution, review, rework, integration, and cleanup flow.
- `references/common-document-contract.md`: Apply the shared canonical sectioned-document engine and package ownership contract.

## Assets and tools

`scripts/sectioned_document.py` owns the shared package engine. `assets/` owns
shared schemas, and `tests/` owns lifecycle, document-profile, metadata, and
manager-contract regression coverage.
