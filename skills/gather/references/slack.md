# Gather Slack

Read `gather-management.md` and the authenticated server's integrations guide and schemas first. Use its collection tools with a Tool-resolved connection; this reference specifies source semantics, not a local provider command.

## Selection and fidelity

Require `channel_id`, exact `channel_type`, optional `oldest`/`latest`, bounds and attachment intent. Request the matching history scope (`channels:history`, `groups:history`, `im:history` or `mpim:history`), and `files:read` for attachments. Channel membership remains provider-owned. Preserve message API evidence and original `files.info` downloads. Thread replies are not traversed; report messages with replies as a coverage limitation. Never post, edit or delete content. Private download URLs and tokens are not provenance.

## Connection and result

Use the server-advertised authentication route through Tool. Credentials remain in the cloud credential authority; do not put tokens in prompts, command arguments, repository files, receipts or source metadata. Distinguish requested scope, observed grant, account health, selection access and stale/unknown state. Missing capability or permission stops dependent collection without a local-script fallback.

Inspect cloud collection status and persisted results, including partial results, conversions and coverage limitations. Preserve collection/run/source identity across retries. Cancellation retains evidence. New local sync configuration and provider services are outside this contract; local provider executables are retired after independently verified cloud replacement.
