# Cloud Gather management

## Resolve authority and scope

Use the selected authenticated cloud MCP connection and read `agent-factory://integrations/guide` plus the advertised schemas. In the development checkout the implementation guide is `../mcp/docs/cloud-integrations.md`; this is a source locator, not an installed runtime path. Resolve organization, Workspace, provider account/connection, selection, recursion, item/page/byte limits, attachment intent and required read scopes from existing authority. Do not invent IDs, widen consent or infer grants from requested scopes. Tool handles connection preparation; use its lifecycle reference when connection or authentication is missing.

A connection identifies an account and its server-encrypted credentials. A collection independently fixes a nonempty name, immutable bounded selection and Workspace Original destination. Several collections may share one connection. New selection means a new collection, not a silent edit or expanded retry. No local destination path, arbitrary download URL or provider cursor is a collection input.

## Collect and inspect

1. `integration_inspect(connection_id, live=false)` reads known state. Live inspection is a separate provider call; successful account inspection does not prove access to every selected source.
2. `collection_create(request)` persists the bounded selection without external I/O.
3. `collection_start(collection_id, request_key)` queues authorized collection. Keep the durable key and run identity; consult the server schema for exact retry semantics.
4. `collection_status(run_id)` reports progress; `collection_results(run_id)` reports persisted Document IDs, revisions, hashes and limitations. Inspect results even after failure or cancellation.
5. `collection_cancel(run_id)` requests cancellation. It retains persisted Originals; an in-flight storage write may finish.

Counts include examined entries, including visited folders/blocks. Pages, metadata, attachments and retry responses consume shared bounds. A cap reached before provider exhaustion is `bounded`, not complete. A new request key rescans the original selection with the same bounds, not a continuation beyond them. Server workers own checkpoints, credential refresh, bounded retry and cancellation. On missing permission, expired cursor or unknown delivery, preserve identity and evidence; do not silently restart or widen selection.

## Fidelity and recovery

One stable source unit maps to one Original per collection; overlapping collections retain separate selection provenance. Record provider, connection, collection, source identity, selection, source metadata, run, retrieval time and limitations. Do not invent Document derivation links for an external source. Declare provider exports as conversions.

Preserve native bytes. Multipart evidence or unsupported storage MIME may use a deterministic ZIP containing unchanged artifacts and filename/MIME/hash manifest; this is packaging, not transcoding. Empty source bytes remain evidence. Signed URLs and credentials must not enter published provenance. Preserve ordinary nonsecret source URLs and meaningful query parameters. Cloud tools own safe fetching, response limits, immutable revisions and replay checkpoints; never fetch user-supplied arbitrary URLs through a substitute local provider.

New configuration, persistence and synchronization belong to the cloud. Existing local `sync.json`, source collections and authentication caches are legacy migration inputs, not new-work routes. Keep them until independently retained backup and verified import; deletion needs its own Human authority. Do not claim full source coverage, live authentication, deployed worker registration or completed cutover from a configuration or receipt alone.
