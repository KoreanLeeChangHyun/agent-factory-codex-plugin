# Gather Management

Choose the gathering capability that matches the source:

- `references/google-drive.md`: Import or refresh Google Drive materials in the
  local workspace.
- `references/google-mail.md`: Import or refresh Gmail messages and attachments
  in the local workspace.
- `references/slack.md`: Import bounded channel history and files from Slack.
- `references/notion.md`: Import a shared Notion page tree and its files.
- `references/discord.md`: Import bounded channel history and attachments from Discord.
- `references/onedrive.md`: Import selected OneDrive files or folders.

## Project And Destination Contract

The Git top-level is the project root. The `.agent-factory` directory may be
tracked, untracked, or ignored; its Git index state does not change canonical
configuration behavior.

Gather owns the project sync configuration and resolver:

- Manager: `scripts/sync.py`, resolved from this `SKILL.md` directory.
- Schema: `assets/schema/sync.schema.json`.
- Project configuration: `<git-project-root>/.agent-factory/document/sync.json`.
- Drive default: `<git-project-root>/source/google/drive`.
- Gmail default: `<git-project-root>/source/google/mail`.
- Slack default: `<git-project-root>/source/slack`.
- Notion default: `<git-project-root>/source/notion`.
- Discord default: `<git-project-root>/source/discord`.
- OneDrive default: `<git-project-root>/source/microsoft/onedrive`.
- Precedence: explicit command destination, source-specific project setting,
  then source default.

Gathered source collections must resolve outside `<git-project-root>/.agent-factory/`.
Gather owns only `.agent-factory/document/sync.json` inside that operational work root;
the manager rejects both relative and absolute destinations that would place
source evidence there.

OAuth client, token, and delegated-auth cache paths must also resolve outside
the Git project. Provider scripts require regular non-symlink credential files
and atomically publish generated token/cache content with user-only `0600`
permissions; they do not repair or follow an unsafe existing path.

For connector-backed collection, Gather declares the provider capability,
minimum scope, Human-approval or administrator-consent need, and exact source
selection bounds. Tool resolves or prepares the logical connection lifecycle
and reports requested versus actually granted scope without escalating it.
Gather still owns destination resolution, the bounded read-only sync, and its
Original Document output.

Google Drive and OneDrive authentication/token-cache code is currently coupled
to the provider scripts. Keep it in place until a concrete Tool
connection/token lifecycle interface and Gather capability/scope request
interface exist. No Tool registry/state backend or migration is implemented by
this contract.

Use the manager before a sync operation. It validates the Git top-level,
validates project configuration, resolves relative destinations from that
top-level, accepts an explicitly selected absolute destination, and prints the
normalized resolved destination:

```bash
python <gather-skill-directory>/scripts/sync.py resolve --source google-drive
python <gather-skill-directory>/scripts/sync.py resolve --source google-mail
python <gather-skill-directory>/scripts/sync.py resolve --source slack
python <gather-skill-directory>/scripts/sync.py resolve --source notion
python <gather-skill-directory>/scripts/sync.py resolve --source discord
python <gather-skill-directory>/scripts/sync.py resolve --source onedrive
```

Set or inspect a persistent source-specific override without moving or deleting
existing data:

```bash
python <gather-skill-directory>/scripts/sync.py set \
  --source google-drive \
  --destination source/customer-drive
python <gather-skill-directory>/scripts/sync.py show
```

Configuration shape:

```json
{
  "schemaVersion": "1.0.0",
  "sources": {
    "google-drive": {
      "destination": "source/customer-drive"
    },
    "slack": {
      "destination": "source/customer-slack"
    },
    "notion": {
      "destination": "source/customer-notion"
    },
    "discord": {
      "destination": "source/customer-discord"
    },
    "onedrive": {
      "destination": "source/customer-onedrive"
    }
  }
}
```

An absent source keeps its default. Do not edit `sync.json` directly, infer the
project from the current working directory alone, or create a destination until
the manager has printed and the caller has checked the resolved destination.
