# Gather Google Mail

## Overview

Use this capability to gather Gmail messages and attachments visible to a real
user account into a local workspace. Default the local destination to
`source/google/mail` under the Git project root unless
`<git-project-root>/.agent-factory/sync.json` or the user gives a different
path.

Keep the workflow read-only by default. Do not send, delete, archive, label, or
modify Gmail messages unless the user explicitly asks for write-back behavior.

## Credential Convention

Use the shared local Google API OAuth client outside the repository:

- Config root: `${XDG_CONFIG_HOME:-$HOME/.config}`
- OAuth client JSON: `${XDG_CONFIG_HOME:-$HOME/.config}/google-api/oauth-client.json`
- Gmail token JSON: `${XDG_CONFIG_HOME:-$HOME/.config}/google-api/gmail-token.json`
- Local mail default: `source/google/mail` under the Git project root

Keep credential and token files out of git. Set credential and token permissions
to user-only read/write:

```bash
python <gather-skill-directory>/scripts/sync.py resolve --source google-mail
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
test -d "<resolved-mail-destination>" && find "<resolved-mail-destination>" -type f | wc -l || true
test -d "<resolved-mail-destination>" && du -sh "<resolved-mail-destination>" || true
```

## OAuth Scope

For body and attachment import, prefer:

```text
https://www.googleapis.com/auth/gmail.readonly
```

Do not use send, modify, compose, or full mail scopes unless the user explicitly
requests Gmail write behavior.

Create an Installed application OAuth client, enable Gmail API, and place its
downloaded JSON at the documented external config path. The first script run
opens user consent and stores a user-only refresh token outside the repository.
See Google's [Gmail scope contract](https://developers.google.com/workspace/gmail/api/auth/scopes).

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
python -m pip install -r <gather-skill-directory>/requirements.txt
python <gather-skill-directory>/scripts/sync_gmail.py \
  --query "project-name or search terms" \
  --max-results 100
```

Resolve `<gather-skill-directory>` as the parent `gather` skill root that owns
this reference.
Do not assume a fixed plugin installation root.

The script:

- Loads the shared `scripts/sync.py` resolver from the loaded Gather Skill root.
- Applies explicit `--destination`, then the `google-mail` entry in
  `.agent-factory/sync.json`, then `source/google/mail`.
- Resolves relative paths from the Git top-level and prints the normalized
  resolved destination before OAuth or filesystem writes.
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

- Use `scripts/sync.py` from the loaded Gather Skill root to inspect or set
  project overrides; do not edit `.agent-factory/sync.json` directly.
- Keep sync read-only unless the user explicitly asks for Gmail write actions.
- Do not delete local mail snapshots unless the user explicitly asks.
- Do not store OAuth client JSON or token JSON in the repository.
- Before importing a broad mailbox query, confirm the query and destination.
- Prefer Gmail search queries to limit scope when the user gives a project,
  sender, date range, or subject.

## Post-Sync Reporting And Optional Verification

After syncing, report information already produced by the sync:

- credential path used,
- normalized resolved destination and whether it came from explicit input,
  `.agent-factory/sync.json`, or the default,
- Gmail query used,
- approximate message count,
- attachment count and size if available,
- skipped messages or attachments,
- whether a token file was created.

Run optional filesystem checks only when the Human has authorized verification,
and dispatch them through a separate managed Verification Agent under the Main
Agent contract. Without that authority, do not run these commands; report the
sync-produced information and state that optional verification was not run.

When authorized, useful checks are:

```bash
find "<resolved-mail-destination>" -type f | wc -l
du -sh "<resolved-mail-destination>"
GOOGLE_API_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/google-api"
test -f "$GOOGLE_API_CONFIG_DIR/gmail-token.json" && ls -l "$GOOGLE_API_CONFIG_DIR/gmail-token.json"
```
