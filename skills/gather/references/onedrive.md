# Gather OneDrive

Read `gather-management.md` and the authenticated server's integrations guide and schemas first. Use its collection tools with a Tool-resolved connection; this reference specifies source semantics, not a local provider command.

## Selection and fidelity

Select exactly one `item_id` or relative `path`, optional recursion and all bounds. Require `Files.Read`; `include_shared=true` deliberately requests `Files.Read.All` and is required with explicit `drive_id`. Resolve Human/admin consent before broadening access. Cloud OAuth replaces local MSAL/device-code caches for new work. Preserve original Graph file bytes, IDs, web URLs, timestamps and hashes. Remote-item shortcuts retain metadata plus a limitation. Never upload, move, rename, share or delete DriveItems. Do not send Graph credentials to content redirect/CDN targets.

## Connection and result

Use the server-advertised authentication route through Tool. Credentials remain in the cloud credential authority; do not put tokens in prompts, command arguments, repository files, receipts or source metadata. Distinguish requested scope, observed grant, account health, selection access and stale/unknown state. Missing capability or permission stops dependent collection without a local-script fallback.

Inspect cloud collection status and persisted results, including partial results, conversions and coverage limitations. Preserve collection/run/source identity across retries. Cancellation retains evidence. New local sync configuration and provider services are outside this contract; local provider executables are retired after independently verified cloud replacement.
