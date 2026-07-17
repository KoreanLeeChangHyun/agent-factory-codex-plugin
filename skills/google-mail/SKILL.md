---
name: google-mail
description: Sync Gmail messages and attachments visible to a user's Google account into a local workspace folder using a user-created Google API OAuth client, browser consent, and read-only Gmail access. Use when Codex needs to import, refresh, mirror, or troubleshoot Gmail mail materials, especially into source/google/mail under the current project root.
---

# Sync Google Mail

## Overview

Use this skill to bring Gmail messages and attachments visible to a real user
account into a local workspace. Default the local destination to
`source/google/mail` under the current project root unless the user gives a
different path.

Keep the workflow read-only by default. Do not send, delete, archive, label, or
modify Gmail messages unless the user explicitly asks for write-back behavior.

## Credential Convention

Use the shared local Google API OAuth client outside the repository:

- Config root: `${XDG_CONFIG_HOME:-$HOME/.config}`
- OAuth client JSON: `${XDG_CONFIG_HOME:-$HOME/.config}/google-api/oauth-client.json`
- Gmail token JSON: `${XDG_CONFIG_HOME:-$HOME/.config}/google-api/gmail-token.json`
- Local mail destination: `source/google/mail` under the current project root

Keep credential and token files out of git. Set credential and token permissions
to user-only read/write:

```bash
GOOGLE_API_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/google-api"
chmod 600 "$GOOGLE_API_CONFIG_DIR/oauth-client.json"
chmod 600 "$GOOGLE_API_CONFIG_DIR/gmail-token.json"
```

## Environment Probe

Start with non-destructive checks:

```bash
GOOGLE_API_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/google-api"
test -f "$GOOGLE_API_CONFIG_DIR/oauth-client.json" && ls -l "$GOOGLE_API_CONFIG_DIR/oauth-client.json"
python3 -m json.tool "$GOOGLE_API_CONFIG_DIR/oauth-client.json" >/dev/null
test -f "$GOOGLE_API_CONFIG_DIR/gmail-token.json" && ls -l "$GOOGLE_API_CONFIG_DIR/gmail-token.json" || true
test -d source/google/mail && find source/google/mail -type f | wc -l || true
test -d source/google/mail && du -sh source/google/mail || true
```

## OAuth Scope

For body and attachment import, prefer:

```text
https://www.googleapis.com/auth/gmail.readonly
```

Do not use send, modify, compose, or full mail scopes unless the user explicitly
requests Gmail write behavior.

If Google blocks a generic OAuth client, use the user-created Google API OAuth
client under `${XDG_CONFIG_HOME:-$HOME/.config}/google-api/` and ensure the
Google Cloud OAuth consent screen has the current Gmail account added as a test
user while the app is in Testing mode.

## Import Shape

When syncing messages, preserve source fidelity and make analysis easy:

- Store raw RFC 2822 message files as `.eml`.
- Store extracted attachments under a per-message attachment directory.
- Store a JSON index with message id, thread id, labels, headers, dates,
  snippet, local `.eml` path, and attachment paths.
- Avoid printing message bodies or secrets to the terminal unless the user asks.

Suggested layout:

```text
source/google/mail/
  messages/
    <message-id>.eml
  attachments/
    <message-id>/
      <filename>
  index.jsonl
```

## Preferred Script

Use the bundled script for repeatable imports:

```bash
python -m pip install -r <this-skill-directory>/scripts/requirements.txt
python <this-skill-directory>/scripts/sync_gmail.py \
  --query "project-name or search terms" \
  --max-results 100 \
  --destination source/google/mail
```

Resolve `<this-skill-directory>` from the directory containing this `SKILL.md`.
Do not assume a fixed plugin installation root.

The script:

- Uses `${XDG_CONFIG_HOME:-$HOME/.config}/google-api/oauth-client.json`.
- Creates or refreshes `${XDG_CONFIG_HOME:-$HOME/.config}/google-api/gmail-token.json`.
- Opens a browser for OAuth consent when no valid token exists.
- Refuses a broad mailbox import unless `--query` is set or `--allow-all` is explicit.
- Saves `.eml` files, extracted attachments, and `index.jsonl`.

Useful query examples:

```bash
--query "project-name or search terms"
--query "from:someone@example.com newer:2026/04/01"
--query "subject:project-name has:attachment"
```

## Safety Rules

- Keep sync read-only unless the user explicitly asks for Gmail write actions.
- Do not delete local mail snapshots unless the user explicitly asks.
- Do not store OAuth client JSON or token JSON in the repository.
- Before importing a broad mailbox query, confirm the query and destination.
- Prefer Gmail search queries to limit scope when the user gives a project,
  sender, date range, or subject.

## Verification

After syncing, report:

- credential path used,
- local destination path,
- Gmail query used,
- approximate message count,
- attachment count and size if available,
- skipped messages or attachments,
- whether a token file was created.

Useful checks:

```bash
find source/google/mail -type f | wc -l
du -sh source/google/mail
GOOGLE_API_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/google-api"
test -f "$GOOGLE_API_CONFIG_DIR/gmail-token.json" && ls -l "$GOOGLE_API_CONFIG_DIR/gmail-token.json"
```
