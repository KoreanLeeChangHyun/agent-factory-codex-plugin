# Tool Lifecycle Contract

## Authority before lifecycle

Identify the authoritative provider before describing or changing lifecycle
state. A host-native tool, installed plugin, MCP server, project package
manifest, or explicitly selected external provider remains authoritative for
its own installation, version, connection, and runtime state. Tool supplies a
logical control contract across those providers; it is not a substitute
registry or package manager.

If no backend exposes the requested operation, report it as unresolved or
unavailable. Do not create a registry, state service, credential store, or
`.agent-factory/tool/` directory merely to make the logical model appear
implemented.

## Logical entry

A Tool entry may project only inspected or provider-reported facts:

- stable provider/tool identity and display metadata;
- authority kind and opaque authority reference;
- capability identifiers and bounded input/output metadata;
- installed and enabled state when the authority exposes them;
- connection identity without secret material;
- opaque credential reference, never a credential or token;
- requested and actually granted permission scopes;
- availability/health result, observation time, and honest unknown state;
- version/update facts and supported lifecycle operations.

Unknown, unsupported, stale, and unavailable are distinct states. Do not infer
health from installation, connection from configuration, or granted scope from
requested scope.

## Lifecycle operations

Route discovery, install, update, remove, connect, disconnect, enable, disable,
and health operations to the authoritative provider. Before a state-changing
operation, resolve the exact target, expected effect, authority, and required
Human approval. Preserve the provider's own confirmation and recovery
contract. Removing a Tool integration does not imply deleting external data or
credentials unless the Human separately authorizes those exact effects.

Request the minimum scope for the declared capability. Show requested and
granted scopes separately. A provider may grant less or more than requested;
surface the difference and stop when it exceeds the approved boundary. Tool
never escalates scope automatically.

## Agent binding

Tool readiness does not authorize execution. Agent binds a capability to the
specific Work or Verification task, supplies execution authority, and records
the resulting receipt. Tool may report capability and health metadata, but it
does not dispatch the task or claim its result.

Local inspection uses existing Agent shell/file tools and preserves the profile's exact authority. Cloud connection operations use the authenticated server's advertised tools and schemas. A route, `performed: false`, or configured entry is not evidence of execution, approval or readiness. Agent runtime binding remains separate through `--capability-binding-file`; Tool does not create that run record.

## Gather connector handshake

For connector-backed collection, Gather supplies:

- connector capability and source identity;
- minimum permission scope;
- whether Human approval or administrator consent is required;
- file, folder, drive, recursion, time, count, and other selection bounds;
- resolved destination and read-only synchronization intent.

Tool returns the resolved provider authority, connection identity, actually
granted scope, availability/health, and an opaque credential reference when
the provider uses one. Gather then performs and receipts the bounded sync under
its own fidelity, identity, provenance, and Original Document contract.

## Authenticated cloud lifecycle

Read `agent-factory://integrations/guide` and current tool schemas. Resolve an existing authorized organization, Workspace, provider connection and account. Use the server's existing connection API for connection creation; do not invent a tool name. `integration_inspect` returns cached metadata unless live inspection is explicitly requested. Keep health, scope-inspection support, requested scopes, observed grants, observation time and staleness separate. Unsupported permission enumeration or transient failure means unknown, not unauthenticated.

Use `integration_oauth_begin` for explicitly approved provider/account/scopes and the server's configured callback or advertised `integration_oauth_complete` flow. Preserve single-use state, initiating user and tenant binding; the cloud owns client secrets, exchange and encrypted refresh credentials. Use protected Human secret entry for token providers; `integration_token_set` stores a token but does not prove live access, and token-bearing tool arguments can be recorded in client transcripts. Do not ask an Agent to relay secrets through prompts or shell arguments. Never invent a credential store or silently switch accounts/scopes.

Connection readiness is not collection authorization. Gather creates and starts its own immutable bounded cloud collections after capability binding. New connection and collection configuration is cloud-owned; legacy local OAuth/device-code/token caches are retained migration inputs only. Local provider and Tool executables are retired after independently verified replacement. Do not infer deployed registration, configured credentials, consent or live provider access from this contract.
