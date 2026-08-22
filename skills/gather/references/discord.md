# Gather Discord

Use `scripts/sync_discord.py` to collect bounded message history from one
channel into the resolved `discord` destination (default `source/discord`). It
saves a boundary-specific message API representation under
`channels/<channel-id>/snapshots/`, downloads original attachment bytes, and
maintains `index.jsonl` with IDs, hashes, message/channel provenance, sizes, and
local paths. It never sends, edits, reacts to, or deletes messages.

## Connection And Authentication

Create a Discord application and bot, install it in the selected server, and
grant only `VIEW_CHANNEL` and `READ_MESSAGE_HISTORY` for the target channel.
Store the bot token outside the repository in `DISCORD_BOT_TOKEN`; never place
it in config, arguments, or the index. Confirm the bot can see the channel.
See Discord's [API reference](https://docs.discord.com/developers/reference)
and [message resource](https://docs.discord.com/developers/resources/message).

```bash
export DISCORD_BOT_TOKEN='...'
python <gather-skill-directory>/scripts/sync_discord.py \
  --channel-id CHANNEL_ID --before MESSAGE_ID --max-messages 200
```

`--before` and `--after` are mutually exclusive bounded selectors. Confirm the
channel, boundary, count, and resolved destination. Discord attachment URLs are
signed and expire; the script consumes them promptly from freshly fetched
messages and removes both attachment and proxy URLs from saved API evidence.
Different boundary/count selections retain separate snapshots. An existing
snapshot and indexed attachment are retained by default; `--overwrite`
intentionally replaces evidence for that same selection and refreshes already
indexed attachments.
