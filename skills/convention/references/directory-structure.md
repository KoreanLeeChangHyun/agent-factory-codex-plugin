# Source, Runtime and Cloud Layout

<a id="source-and-installation"></a>

## 1. Source and installation

- **Plugin:** `<plugin-root>/skills/<id>/`, `agent`, `convention` and `document`; preserve
  single-name identities. No repository `.codex/` mirror or duplicate Skill contract
  tree. These packages are Provider instructions, not Client Document or Project Skill
  backends.
- **Consumer:** canonical Processed and Specification packages contain one user-language
  `SKILL.md` plus optional `assets/`, under the local roots below. Optional
  `.codex/skills/<category>[-<domain>]-<name>/` exposure derives from the canonical Specification; it is never a separate
  editable source. Follow the [naming and metadata contract](../../document/SKILL.md#naming-and-metadata).
- **Locators:** resolve source, installed Skill and immutable cloud revision separately.
  Git owns authoring; current MCP schema/authority governs selected connected
  publication.
- **MCP domains:** Document, Gather, Tool, Workspace; no plugin Skill directories. Never
  hardcode development sibling `../mcp` as an installed path.

<a id="local-runtime"></a>

## 2. Local runtime

- Follow [home-runtime.md](../../agent/references/home-runtime.md) for path resolution, project/session/run layout, initialization and
  runtime migration.
- Preserve exec/loop entry points, support modules and extension path compatibility.
- Keep temporary Explorer evidence in its producing run; create no standalone root.
- Keep credentials with their authority, outside runtime evidence and Git.
- Use shell/file tools for bounded local inspection.
- Store durable documents using [Document routing](../../document/SKILL.md#routing). Its local standalone packages are
  `<project-root>/docs/original/<category>[-<domain>]-<name>/`, `<project-root>/docs/processed/<category>[-<domain>]-<name>/`, and `<project-root>/docs/skills/<category>[-<domain>]-<name>/`; this is complete standalone behavior, not
  an error fallback.
- Add no local MCP/provider/Document service.

<a id="cloud-domains"></a>

## 3. Cloud domains

- MCP-only operation is valid and does not require this plugin, its Skills or its
  runtime. The plugin documents only this product boundary.
- The resolved MCP application owns its domain implementation, dependencies, deployment
  and connected state. Use its current authenticated guides and schemas for physical
  storage and application layout.
- A future Agent Factory cloud Document MCP receiver requires an authorized connection
  and a resolved target workspace/project. It becomes authoritative only after complete,
  verified migration of the local inventory. Follow [Documents](../../document/SKILL.md#future-connected-storage-and-migration). That receiver and
  migration path are not currently implemented by this plugin.
- Do not add MCP domain backends, Workspace assets or launchers to the plugin or a
  consumer project. Non-authoritative installation/connection cache may use `~/.agent-factory/`
  outside repositories.
- Legacy `db.sqlite` is non-authoritative, never a new-work route. Create no local
  `db.sqlite`, document/sync config or `.agent-factory/tool/` stores.
  Hosts/plugins/MCP/manifests/credential authorities retain their state.
- Read authenticated guides/schemas for selected integrations; report absent
  capability/account/permission honestly after one was selected. In plugin-only mode,
  absence is expected and requires no diagnostic.

<a id="legacy-migration"></a>

## 4. Legacy migration

<a id="inputs-and-identity"></a>

### 4.1. Inputs and identity

- Retain `.agent-factory/document/{original,processed,specification}/`, `document/sync.json`, collections, SQLite and sidecars until inventory,
  independent backup and verified import.
- One immediate child directory identifies one legacy Document; nested contents belong
  to it. Producer/category wrappers are not identities.
- `processed/legacy-inquery-<legacy-id>/` is inactive Processed evidence with legacy status/provenance, never
  another type or active workspace.

<a id="preservation"></a>

### 4.2. Preservation

- Document formats, semantic authority and physical migration invariants follow
  [Documents](../../document/SKILL.md). For selected connected publication, MCP owns its Human-facing publication
  assets.
- Retirement grants no deletion of Human data, source, credentials or backups. Cutover,
  destruction and unresolved conflicts retain exact Human authority.

<a id="ecosystem-boundary"></a>

## 5. Ecosystem boundary

- Group files beneath `tests/` into purpose or component directories; follow
  [Testing Convention](testing.md#source-organization) for categories and collection.
- Follow each application's native layout; Agent Factory paths are not universal.
- [Python packaging layouts](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) illustrate ecosystem-specific import/installation tradeoffs.
