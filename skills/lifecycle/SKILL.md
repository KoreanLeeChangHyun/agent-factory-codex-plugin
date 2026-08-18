---
name: lifecycle
description: Route Agent Factory work through fast Work Agent execution and post-feedback recording, with Intake, Specification, Work Unit, and Work Package flows available only when explicitly selected.
---

# Agent Factory Lifecycle

## Entry contract

Use this skill for Agent Factory lifecycle routing and canonical artifact
ownership. Read `references/lifecycle-entry.md` completely before lifecycle
work, then read each additional reference applicable to the operation.

## Reference routing

- `references/lifecycle-entry.md`: Choose the default feedback-first route or an explicitly requested advanced route.
- `references/lifecycle.md`: Follow work-first execution, Human feedback, background recording, and optional artifact flows.
- `references/common-document-contract.md`: Apply the shared canonical sectioned-document engine and package ownership contract.

## Assets and tools

`scripts/sectioned_document.py` owns the shared package engine. `assets/` owns
shared schemas, and `tests/` owns lifecycle, document-profile, metadata, and
manager-contract regression coverage.
