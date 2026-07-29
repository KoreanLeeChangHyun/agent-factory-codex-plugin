---
name: syncs
description: Route requests to supported Agent Factory synchronization capabilities.
---

# Synchronization

Choose the synchronization capability that matches the source:

- `syncs-google-drive`: Import or refresh Google Drive materials in the local workspace.
- `syncs-google-gmail`: Import or refresh Gmail messages and attachments in the local workspace.

## Project And Destination Contract

The Git top-level is the project root. The `.agent-factory` directory may be
tracked, untracked, or ignored; its Git index state does not change canonical
configuration behavior.

This skill owns the project sync configuration and resolver:

- Manager: `scripts/sync.py`, resolved from this `SKILL.md` directory.
- Schema: `assets/schema/sync.schema.json`.
- Project configuration: `<git-project-root>/.agent-factory/sync.json`.
- Drive default: `<git-project-root>/source/google/drive`.
- Gmail default: `<git-project-root>/source/google/mail`.
- Precedence: explicit command destination, source-specific project setting,
  then source default.

Use the manager before a sync operation. It validates the Git top-level,
validates project configuration, resolves relative destinations from that
top-level, accepts an explicitly selected absolute destination, and prints the
normalized resolved destination:

```bash
python <syncs-skill-directory>/scripts/sync.py resolve --source google-drive
python <syncs-skill-directory>/scripts/sync.py resolve --source google-gmail
```

Set or inspect a persistent source-specific override without moving or deleting
existing data:

```bash
python <syncs-skill-directory>/scripts/sync.py set \
  --source google-drive \
  --destination source/customer-drive
python <syncs-skill-directory>/scripts/sync.py show
```

Configuration shape:

```json
{
  "schemaVersion": "1.0.0",
  "sources": {
    "google-drive": {
      "destination": "source/customer-drive"
    }
  }
}
```

An absent source keeps its default. Do not edit `sync.json` directly, infer the
project from the current working directory alone, or create a destination until
the manager has printed and the caller has checked the resolved destination.
