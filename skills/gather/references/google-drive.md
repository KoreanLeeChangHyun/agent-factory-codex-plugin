# Gather Google Drive

Read `gather-management.md` and the authenticated server's integrations guide and schemas first. Use its collection tools with a Tool-resolved connection; this reference specifies source semantics, not a local provider command.

## Selection and fidelity

Exactly one `folder_id` or `file_id`; declare recursion and all bounds. Require `drive.readonly`. Preserve binary files unchanged; export Docs, Slides and Drawings as PDF and Sheets as XLSX, explicitly recording conversion. Unsupported native types retain metadata and a limitation. Do not infer complete folder coverage, follow shortcuts outside selection or request write scopes.

## Connection and result

Use the server-advertised authentication route through Tool. Credentials remain in the cloud credential authority; do not put tokens in prompts, command arguments, repository files, receipts or source metadata. Distinguish requested scope, observed grant, account health, selection access and stale/unknown state. Missing capability or permission stops dependent collection without a local-script fallback.

Inspect cloud collection status and persisted results, including partial results, conversions and coverage limitations. Preserve collection/run/source identity across retries. Cancellation retains evidence. New local sync configuration and provider services are outside this contract; local provider executables are retired after independently verified cloud replacement.
