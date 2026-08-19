---
name: gather
description: Locate, import, refresh, or mirror distributed source material while preserving source fidelity, provenance, identity, and resolved destinations. Use for Google Drive or Gmail collection, not for reconciling or promoting trusted project truth.
---

# Agent Factory Gather

## Entry contract

Use this skill to locate, import, refresh, or mirror distributed source
material. Preserve source fidelity, provenance, identity, and the resolved
destination. Treat gathered collections as evidence; do not reconcile their
claims, refine them, or promote them into a trusted Specification.

Keep synchronization mechanisms read-only by default. Read the management
reference and selected provider reference completely before authorization or
copy.

## Reference routing

- `references/gather-management.md`: Resolve and manage project-local gather destinations.
- `references/google-drive.md`: Share, authorize, import, refresh, mirror, or troubleshoot Google Drive files.
- `references/google-mail.md`: Authorize, import, refresh, mirror, or troubleshoot Gmail messages and attachments.

## Assets and tools

`scripts/sync.py` owns destination resolution and configuration, and
`scripts/sync_gmail.py` owns Gmail synchronization. Keep
`.agent-factory/sync.json`, source identifiers, schemas, defaults, credential
safety, read-only behavior, and destructive-sync confirmations as the internal
synchronization contract.
