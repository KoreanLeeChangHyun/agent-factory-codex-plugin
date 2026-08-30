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

The current stateless adapter at `skills/tool/scripts/tool.py` routes lifecycle
mutations without performing them. Its `provider-route-required` result is not
approval, readiness, or evidence that the provider supports the operation.
Agent runtime binding is supplied separately through
`--capability-binding-file`; Tool does not create or persist that run record.

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

Current Google Drive and OneDrive scripts still contain provider-specific
authentication and token-cache lifecycle behavior inside `skills/gather/`.
That is an observed coupling, not the target ownership boundary. Do not move
it until a concrete Tool connection/token lifecycle interface and Gather
capability/scope request interface exist, preserve compatibility, and have
separately authorized migration and verification. No such runtime interface,
registry, or state backend is implemented by this Skill.
