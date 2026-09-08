# Source, Runtime and Cloud Layout

## Source and installation

- **Plugin:** `<plugin-root>/skills/<id>/`, exactly `agent` and `convention`;
  preserve single-name identities. No repository `.codex/` mirror or duplicate
  Skill contract tree. These packages are not consumer Document backends.
- **Consumer:** `.codex/skills/<category>-<title>/` using the
  [core naming contract](agent-factory-core.md#project-skill-naming).
- **Locators:** resolve source, installed Skill and immutable cloud revision
  separately. Git owns authoring; current MCP schema/authority governs publication.
- **MCP domains:** Document, Gather, Tool, Workspace; no plugin Skill directories.
  Never hardcode development sibling `../mcp` as an installed path.

## AI-generated documents

1. **MCP connected:** write generated documents through the connected Document MCP
   using its current tools and resolved destination.
2. **No Document MCP connection:** write under `<project-root>/docs/` with the
   `[분류]-[이름]` (`<category>-<name>`) basename. Use the document's appropriate
   extension for a single file, or that directory name for a multi-file package.
   Examples: `docs/분석-인증흐름.md`, `docs/설계-인증흐름/index.html`.

- Follow an explicit Human destination or format when supplied. Otherwise choose
  a concise category/name describing the document's purpose; these labels do not
  change its Original/Processed/Specification type or acceptance authority.
- Report connected-MCP write/permission failures; do not treat them as disconnection
  or silently create a second local copy. This convention adds no automatic sync,
  migration or local Document service.
- Keep maintained Skill instructions in their owning `skills/` package and temporary
  execution artifacts in their run directories; this rule routes generated documents.

## Local runtime

- Follow [home-runtime.md](../../agent/references/home-runtime.md) for path
  resolution, project/session/run layout, initialization and runtime migration.
- Preserve exec/loop entry points, support modules and extension path compatibility.
- Keep temporary Explorer evidence in its producing run; create no standalone root.
- Keep credentials with their authority, outside runtime evidence and Git.
- Use shell/file tools for bounded local inspection.
- Store durable documents using [AI-generated documents](#ai-generated-documents).
- Add no local MCP/provider/Document service.

## Cloud domains

- MCP owns Document metadata/revisions/search, connections/authentication,
  collections, shared reporting, Workspace and their source/dependencies/assets/tests/deployment.
- PostgreSQL stores tenant metadata; object storage stores immutable Document bytes.
- No project `.agent-factory/workspace/`, launcher, port file or shell copy.
  Non-authoritative installation/connection cache may use `~/.agent-factory/`
  outside repositories.
- Legacy `db.sqlite` is non-authoritative, never a new-work route.
  Create no local `db.sqlite`, document/sync config or `.agent-factory/tool/` stores.
  Hosts/plugins/MCP/manifests/credential authorities retain their state.
- Read authenticated guides/schemas; report absent capability/account/permission honestly.

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
  [the core model](agent-factory-core.md#documents). MCP owns Human-facing
  publication assets.
- Retirement grants no deletion of Human data, source, credentials or backups.
  Cutover, destruction and unresolved conflicts retain exact Human authority.

## Ecosystem boundary

- Group files beneath `tests/` into purpose or component directories; follow
  [Testing Convention](testing.md#source-organization) for categories and collection.
- Follow each application's native layout; Agent Factory paths are not universal.
- [Python packaging layouts](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
  illustrate ecosystem-specific import/installation tradeoffs.
