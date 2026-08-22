# Gather Slack

Use `scripts/sync_slack.py` to collect a bounded channel history plus attached
files into the resolved `slack` destination (default `source/slack`). It saves
the API message representation under a boundary-specific file in
`channels/<channel-id>/snapshots/`,
downloads original file bytes, and maintains `index.jsonl` with source IDs,
channel/message identity, hashes, sizes, and local paths. It never posts,
changes, or deletes Slack content.

## Connection And Authentication

Create or use a Slack app, install it to the workspace with OAuth v2, and keep
the resulting bot token outside the repository in `SLACK_BOT_TOKEN`. Grant
`files:read` plus the history scope matching the selected conversation type
(`channels:history`, `groups:history`, `im:history`, or `mpim:history`). Invite
the bot to private or otherwise membership-restricted conversations. Do not add
write scopes. See Slack's [OAuth v2 setup](https://api.slack.com/authentication/oauth-v2),
[`conversations.history`](https://api.slack.com/methods/conversations.history),
and [`files.info`](https://api.slack.com/methods/files.info).

```bash
export SLACK_BOT_TOKEN='xoxb-...'
python <gather-skill-directory>/scripts/sync_slack.py \
  --channel-id C0123456789 --oldest 1767225600 --max-messages 200
```

Use `--latest` as another Slack timestamp boundary. Confirm the selected
channel, bounds, and resolved destination before sync. Private download URLs
are used with the bearer token and are not written to the index. Keep tokens
out of shell history where possible and unset them afterward. Different
boundary/count selections retain separate snapshots. An existing snapshot and
indexed file are retained by default; pass `--overwrite` only to intentionally
replace evidence for that same selection and refresh already indexed files.
