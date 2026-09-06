# Gather Discord

Read `gather-management.md` and the authenticated server's integrations guide and schemas first. Use its collection tools with a Tool-resolved connection; this reference specifies source semantics, not a local provider command.

## Selection and fidelity

Require `channel_id`, optionally one of `before` or `after`, bounds and attachment intent. The bot needs VIEW_CHANNEL and READ_MESSAGE_HISTORY; privileged message-content intent can limit visible content. Empty content is not proof of full access. Preserve message API evidence and original attachment bytes. Signed attachment/proxy URLs expire and are redacted from stored evidence. Never send, edit, react to or delete messages.

## Connection and result

Use the server-advertised authentication route through Tool. Credentials remain in the cloud credential authority; do not put tokens in prompts, command arguments, repository files, receipts or source metadata. Distinguish requested scope, observed grant, account health, selection access and stale/unknown state. Missing capability or permission stops dependent collection without a local-script fallback.

Inspect cloud collection status and persisted results, including partial results, conversions and coverage limitations. Preserve collection/run/source identity across retries. Cancellation retains evidence. New local sync configuration and provider services are outside this contract; local provider executables are retired after independently verified cloud replacement.
