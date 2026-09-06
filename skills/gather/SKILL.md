---
name: gather
description: Locate, import, refresh, or mirror distributed source material while preserving source fidelity, provenance, identity, and resolved destinations. Use for Google Drive, Gmail, Slack, Notion, Discord, or OneDrive collection, not for reconciling or promoting trusted project truth.
metadata:
  specification-id: gather
  human-entry: docs/specifications/gather/index.html
  ai-root: skills/gather/
---

# Agent Factory Gather

## Entry contract

Locate, import, refresh, or mirror distributed source material as Original Documents. Preserve native or source-appropriate bytes, source identity, provenance, collection context and the resolved destination. Gathered evidence is not reconciled Specification truth. Keep provider operations read-only; a bounded collection is not a complete mirror.

Gather owns selection, destination, limits, synchronization and Original output. Tool owns logical connection/authentication lifecycle and reports requested versus observed granted scopes. Agent binds the exact capability, authority, target and permitted effects to the run. Read the management and selected provider reference completely before collection.

## Reference routing

- `references/gather-management.md`: authenticated cloud collection workflow, destination, replay and recovery.
- `references/google-drive.md`: selected Drive files/folders and native exports.
- `references/google-mail.md`: bounded Gmail messages and attachments.
- `references/slack.md`: bounded channel history and files.
- `references/notion.md`: selected page, descendant blocks and files.
- `references/discord.md`: bounded channel messages and attachments.
- `references/onedrive.md`: selected DriveItems and folders.

## Execution boundary

New collection work uses the advertised tools of the resolved, authenticated Agent Factory cloud MCP application. Read `agent-factory://integrations/guide` and current tool schemas before invocation. Missing tools, connection, permissions or provider configuration are unavailable or unresolved capabilities; report them honestly without invoking legacy local scripts or selecting another account.

The cloud owns collection configuration and encrypted connection credentials. Do not create new project `document/sync.json`, local source mirrors, token caches or a local MCP/provider service. Local provider/sync executables, schema and dependency manifest are retired after verified cloud replacement. Existing source data remains migration input: inventory, back up and verify imports before any separately authorized data retirement; code retirement never authorizes deletion of Human data. Contract authoring does not establish live connection, registration, deployment or migration completion.
