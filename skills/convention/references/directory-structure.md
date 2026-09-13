# Source, Runtime and Cloud Layout

## Source and installation

- **Plugin:** `<plugin-root>/skills/<id>/`, exactly `agent` and `convention`;
  preserve single-name identities. No repository `.codex/` mirror or duplicate
  Skill contract tree. These packages are Provider instructions, not Client
  Document or Project Skill backends.
- **Consumer:** `.codex/skills/<category>-<title>/` using the
  [Specification naming contract](documents.md#specification-naming).
- **Locators:** resolve source, installed Skill and immutable cloud revision
  separately. Git owns authoring; current MCP schema/authority governs selected
  connected publication.
- **MCP domains:** Document, Gather, Tool, Workspace; no plugin Skill directories.
  Never hardcode development sibling `../mcp` as an installed path.

## Local runtime

- Follow [home-runtime.md](../../agent/references/home-runtime.md) for path
  resolution, project/session/run layout, initialization and runtime migration.
- Preserve exec/loop entry points, support modules and extension path compatibility.
- Keep temporary Explorer evidence in its producing run; create no standalone root.
- Keep credentials with their authority, outside runtime evidence and Git.
- Use shell/file tools for bounded local inspection.
- Store durable documents using [Document routing](documents.md#routing). Its local
  standalone packages are `<project-root>/docs/original/<category>-<name>/`,
  `<project-root>/docs/processed/<category>-<name>/`, and
  `<project-root>/docs/specification/<category>-<name>/`; this is complete
  standalone behavior, not an error fallback.
- Add no local MCP/provider/Document service.

## Cloud domains

- MCP-only operation is valid and does not require this plugin, its Skills or its
  runtime. The plugin documents only this product boundary.
- The resolved MCP application owns its domain implementation, dependencies,
  deployment and connected state. Use its current authenticated guides and schemas
  for physical storage and application layout.
- A future Agent Factory cloud Document MCP receiver may become authoritative only
  after an authorized connection and target workspace/project destination are both
  resolved and the complete local inventory is migrated and verified under
  [Documents](documents.md#future-connected-storage-and-migration). That receiver
  and migration path are not currently implemented by this plugin.
- Do not add MCP domain backends, Workspace assets or launchers to the plugin or a
  consumer project. Non-authoritative installation/connection cache may use
  `~/.agent-factory/` outside repositories.
- Legacy `db.sqlite` is non-authoritative, never a new-work route.
  Create no local `db.sqlite`, document/sync config or `.agent-factory/tool/` stores.
  Hosts/plugins/MCP/manifests/credential authorities retain their state.
- Read authenticated guides/schemas for selected integrations; report absent
  capability/account/permission honestly after one was selected. In plugin-only
  mode, absence is expected and requires no diagnostic.

## Legacy migration

### Inputs and identity

- Retain `.agent-factory/document/{original,processed,specification}/`,
  `document/sync.json`, collections, SQLite and sidecars until inventory,
  independent backup and verified import.
- One immediate child directory identifies one legacy Document; nested contents
  belong to it. Producer/category wrappers are not identities.
- `processed/legacy-inquery-<legacy-id>/` is inactive Processed evidence with legacy
  status/provenance, never another type or active workspace.

### Preservation

- Document formats, semantic authority and physical migration invariants follow
  [Documents](documents.md). For selected connected
  publication, MCP owns its Human-facing publication assets.
- Retirement grants no deletion of Human data, source, credentials or backups.
  Cutover, destruction and unresolved conflicts retain exact Human authority.

## Ecosystem boundary

- Group files beneath `tests/` into purpose or component directories; follow
  [Testing Convention](testing.md#source-organization) for categories and collection.
- Follow each application's native layout; Agent Factory paths are not universal.
- [Python packaging layouts](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
  illustrate ecosystem-specific import/installation tradeoffs.
