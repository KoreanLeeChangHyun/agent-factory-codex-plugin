---
name: gather
description: Locate, import, refresh, or mirror distributed source material while preserving source fidelity, provenance, identity, and resolved destinations. Use for Google Drive, Gmail, Slack, Notion, Discord, or OneDrive collection, not for reconciling or promoting trusted project truth.
---

# Agent Factory Gather

## Entry contract

Use this skill to locate, import, refresh, or mirror distributed source
material as Original Documents. Original Documents may use diverse source formats, so preserve
source fidelity, identity, provenance, collection context, and its native or
source-appropriate form instead of converting it to one canonical file format.
Preserve the resolved destination. Treat gathered collections as evidence; do
not reconcile their claims or promote them into a Specification.

Keep synchronization mechanisms read-only by default. Read the management
reference and selected provider reference completely before authorization or
copy.

## Reference routing

- `references/gather-management.md`: Resolve and manage project-local gather destinations.
- `references/google-drive.md`: Share, authorize, import, refresh, mirror, or troubleshoot Google Drive files.
- `references/google-mail.md`: Authorize, import, refresh, mirror, or troubleshoot Gmail messages and attachments.
- `references/slack.md`: Connect and gather bounded Slack channel history and files.
- `references/notion.md`: Connect and gather a shared Notion page, blocks, and files.
- `references/discord.md`: Connect and gather bounded Discord channel history and attachments.
- `references/onedrive.md`: Connect and gather selected OneDrive files and folders.

## Assets and tools

`scripts/sync.py` owns destination resolution and configuration. Provider
syncs are `sync_google_drive.py`, `sync_gmail.py`, `sync_slack.py`,
`sync_notion.py`, `sync_discord.py`, and `sync_onedrive.py`. Keep
`.agent-factory/sync.json`, source identifiers, schemas, defaults, credential
safety, read-only behavior, and destructive-sync confirmations as the internal
synchronization contract.
