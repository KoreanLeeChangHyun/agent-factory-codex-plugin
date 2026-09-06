# Cloud Document adapter and migration

## Authority and routes

The Human-selected Agent Factory cloud MCP application owns new persistence, immutable revision publication, document configuration and search. Local shell/file tools inspect Git and prepare authorized evidence; they do not become a local Document backend or MCP/provider service. Read advertised schemas before invocation. Missing authentication, tenant binding, permissions or capability stops the dependent action honestly. Do not invent account IDs or credentials.

Use `document_read` for metadata, revisions, provenance and bounded downloads; `document_import` for byte-preserving imports and complete Specification packages; `document_write` for advertised metadata/provenance operations; `document_search` for bounded lexical retrieval; `document_index` for a selected revision. Package manifests, exact members and isolated Human previews are revision-scoped authenticated server delivery routes; use the server's returned routes and current guide. Do not infer a nonexistent package-member MCP tool or construct an arbitrary object-store URL.

## Import and publication

Bind schema version, exact tenant/Document identity, invariant `document_type`, source identity, collection context, filename/MIME, size/digest and expected revision from inspected evidence. New identities use expected revision zero; updates use the exact current revision. Preserve the same idempotency key and exact request after unknown acknowledgement. A changed payload under the same key conflicts; a new key does not bypass slug or revision conflicts. Read and reconcile conflicts without silent overwrite, resurrection or type promotion.

Native files stay byte-identical. ZIP paths must be safe relative paths without traversal, links, special files or collisions; use advertised package/byte limits. Do not extract arbitrary archives into project files. Preserve source inventory, provenance and limitations. A format transformation is separately authorized semantic Document work, not physical migration.

For content beyond inline limits, call `document_prepare_upload` with exact import metadata, size and digest. Upload raw bytes only to its relative path on the already resolved server with the required existing authentication and upload capability, never a token-bearing URL. Call `document_finalize_upload` for the same upload ID. Read current schemas for expiry and retry. Resume exact metadata/intent after unknown delivery; never delete staging after ambiguous commit. Finalization checks bytes, pair and revision preconditions before publishing.

A Specification publishes one complete ZIP containing exactly one AI root and one Human root, reciprocal package-relative metadata, Git repository/commit, content inventory and review evidence bound to both representation hashes. Server publication stages immutable bytes, reads them back for digest comparison, then commits revision, current pointer, index and idempotency receipt transactionally. Object storage and database are not one transaction; retained staging after failure is recovery evidence. Preserve the prior publication on failure. Hash coverage and `review_attested` do not constitute independent semantic acceptance.

## Reading and search

Cloud lexical search is bounded, tenant-scoped and independent of embeddings. Read the current Document after discovery to inspect its revision, provenance and authority. Search hits, indexing or a rendered browser page do not establish acceptance, completeness or semantic truth. Unsupported binary text extraction must remain explicit.

Human package preview is isolated in an opaque-origin sandbox. Use validated package-relative assets; do not grant same-origin application access, credential access or arbitrary network fetching to document code. Raw member downloads do not execute HTML on the application origin. Preserve readable Korean baseline content and local assets even when a dynamic renderer is unsupported.

## Physical migration and recovery

Initialization and migration remain Document capabilities, separate from classification, transformation and acceptance. Preserve every Document's identity, `documentType`, provenance, authority and Specification binding. Legacy local direct packages and sync configuration are retained source inputs, not new consumer runtime stores. `db.sqlite` is a legacy non-authoritative projection, never a migration manifest, journal or recovery authority.

Inventory source and destination first; retain an independent backup. A deterministic operation must bind a closed versioned allowlist of identities, locators, ordered effects, inventories/hashes, sizes, revisions, authority references, conflicts, pair groups, postconditions and recovery behavior. Revalidate current state immediately before execution. Raw model prose, code, SQL, shell fragments or schema-shaped proposals never grant executable authority. Advisory classification/provenance/reconciliation may leave `unknown` or `requiresDecision`.

Reject stale plans, unsafe paths/symlinks, collisions, unsupported versions/capabilities, unverifiable writers, insufficient or overbroad scope, missing provenance/authority, type changes and partial or semantically unaligned pairs. Initialization preserves existing content and is idempotent. Stage and validate before publication; a single-file rename does not imply cross-backend or pair atomicity. If atomic pair publication cannot be guaranteed, preserve prior authority and retain recoverable staging.

Verify imported identity, type, provenance, bytes, pair and history independently before cutover. Copy success alone is not integrity, acceptance or cutover. Exact Human authority is required for destructive effects, overwrite, source retirement or deletion; code retirement does not authorize deleting user data. Recovery uses validated state/journal evidence, preferably idempotent resume or roll-forward where rollback safety is unproven. Do not rewrite history/hashes to conceal corruption or roll back over newer accepted writes.

## Responsibility and remaining deployment work

Main resolves authority and integrates; Work authors or invokes authorized deterministic operations without verifying itself; independent Verification assesses evidence and returns failures to the same Work. A deterministic server integrity check does not replace that role. Gather owns bounded external collection, Tool logical connection lifecycle, Agent local exec/loop and receipts, Workspace projections, and Convention shared rules. No additional Skill or Agent role is introduced.

The cloud choice is accepted; actual tenant/account IDs, credential authority, retention/deletion policy and unresolved conflicts must still be explicitly resolved. Advertised capability is checked at use time. This contract does not apply migrations, register workers, configure accounts, deploy, restart or attest complete steps 1–13. Earlier migration design provenance remains in run `run-20260830T135328504819Z-24544fc7` and the document-adapter/llm-document-migration research run records; the current cloud migration request supersedes its unresolved-backend/local-manager routing.
