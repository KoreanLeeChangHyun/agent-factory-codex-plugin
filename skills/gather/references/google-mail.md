# Gather Gmail

Read `gather-management.md` and the authenticated server's integrations guide and schemas first. Use its collection tools with a Tool-resolved connection; this reference specifies source semantics, not a local provider command.

## Selection and fidelity

Require a nonempty `query` or explicit `allow_all=true`, bounded items/pages/bytes and attachment intent. Require `gmail.readonly`. Preserve original RFC message bytes, extracted attachments and header/thread provenance. Do not mark read, label, send or delete mail. All-mail access is an explicit selection, never an empty-query default. Unsupported EML storage uses unchanged bytes in a package manifest.

## Connection and result

Use the server-advertised authentication route through Tool. Credentials remain in the cloud credential authority; do not put tokens in prompts, command arguments, repository files, receipts or source metadata. Distinguish requested scope, observed grant, account health, selection access and stale/unknown state. Missing capability or permission stops dependent collection without a local-script fallback.

Inspect cloud collection status and persisted results, including partial results, conversions and coverage limitations. Preserve collection/run/source identity across retries. Cancellation retains evidence. New local sync configuration and provider services are outside this contract; local provider executables are retired after independently verified cloud replacement.
