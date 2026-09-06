# Gather Notion

Read `gather-management.md` and the authenticated server's integrations guide and schemas first. Use its collection tools with a Tool-resolved connection; this reference specifies source semantics, not a local provider command.

## Selection and fidelity

Select one `page_id` and bounded descendant traversal with read-content capability and explicit page sharing. Authentication alone does not grant page access; permission enumeration may be unsupported. Preserve page/block API evidence and original files. Hosted file URLs expire: the cloud refreshes source metadata before download and redacts temporary/private URLs. Ordinary external file URLs from fresh selected page/block evidence retain nonsecret provenance; server-controlled HTTPS validation and bounds apply. Never introduce an arbitrary URL-fetch argument or mutate pages, blocks, comments or data sources.

## Connection and result

Use the server-advertised authentication route through Tool. Credentials remain in the cloud credential authority; do not put tokens in prompts, command arguments, repository files, receipts or source metadata. Distinguish requested scope, observed grant, account health, selection access and stale/unknown state. Missing capability or permission stops dependent collection without a local-script fallback.

Inspect cloud collection status and persisted results, including partial results, conversions and coverage limitations. Preserve collection/run/source identity across retries. Cancellation retains evidence. New local sync configuration and provider services are outside this contract; local provider executables are retired after independently verified cloud replacement.
