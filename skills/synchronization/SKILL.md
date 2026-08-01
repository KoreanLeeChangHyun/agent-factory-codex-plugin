---
name: synchronization
description: Resolve destinations and synchronize Google Drive or Gmail workspace materials.
---

# Agent Factory Synchronization

## Entry contract

Use this skill for workspace synchronization configuration, Google Drive file
sync, or Gmail message and attachment sync. Read the management reference and
the selected provider reference completely before any authorization or copy.

## Reference routing

- `references/synchronization-management.md`: Resolve and manage project-local synchronization destinations.
- `references/google-drive.md`: Share, authorize, import, refresh, mirror, or troubleshoot Google Drive files.
- `references/google-mail.md`: Authorize, import, refresh, mirror, or troubleshoot Gmail messages and attachments.

## Assets and tools

`scripts/sync.py` owns destination resolution and configuration;
`scripts/sync_gmail.py` owns Gmail synchronization. `scripts/requirements.txt`
declares the combined dependency set, `assets/` owns schemas, and `tests/`
owns provider and manager regression coverage.
