# Source, local runtime and cloud layout

## Distributable source and installation

Keep this plugin's two distributed Skills, `agent` and `convention`, under `<plugin-root>/skills/<id>/`, never a repository-local `.codex/` mirror. Optional Korean reference documents are maintained independently at `<plugin-root>/docs/specifications/<id>/`. Preserve the two single-name Skill identities. These are source packages, not consumer Document backend roots. Document, Gather, Tool, and Workspace are MCP application domains rather than plugin Skill directories.

An ordinary consumer's own Project Skill uses the accepted lowercase hyphen-case `<category>-<title>` identity under its `.codex/skills/`. Source-package, installed Skill and cloud immutable-revision locators are resolved separately. Git owns distributable authoring; cloud publication follows the selected application's current schema and authority. Do not hardcode the development sibling `../mcp` as an installed path.

## Local Agent runtime

```text
<runtime-home>/projects/<project-id>/agents/<agent-id>/
  session.json
  runs/<run-id>/
```

Agent owns operational sessions, run state, requests, results, receipts, heartbeat/events, local reporting outbox/acknowledgements and recovery. Keep existing exec/loop entry points, required support modules and extension path/layout compatibility. Temporary execution-only Explorer material stays in its producing run; Explorer has no standalone root. Credentials remain with their owning authority and never enter runtime evidence or source control.

Use existing shell/file tools for bounded local Git/tool inspection and prepare required evidence for authorized cloud upload. Do not add a local MCP/provider or Document service.

## Cloud-owned domains

The selected authenticated Agent Factory MCP application owns new Document persistence, metadata, immutable body revisions, index/search, connection/authentication and collection configuration, shared reporting and Workspace. PostgreSQL owns tenant metadata; object storage owns immutable Document bytes. Runtime source, dependency manifests, browser assets, deployment and tests belong to that application. Workspace creates no project-local `.agent-factory/workspace/`, launcher, port file or browser-shell copy. Non-authoritative client installation/connection cache may live below `~/.agent-factory/` outside repositories.

Do not create new local `db.sqlite`, document/sync configuration or `.agent-factory/tool/` stores. Actual hosts, plugins, MCP servers, package manifests and credential authorities retain their own state. Read advertised authenticated schemas/guides and fail honestly when the selected capability, account or permission is absent.

## Legacy source and migration

Retain old local `.agent-factory/document/{original,processed,specification}/`, `document/sync.json`, source collections, SQLite and sidecars as migration inputs until inventory, independent backup and verified import. Legacy direct package identity means one immediate child directory per Document; internal files/subdirectories belong to it and producer/category wrappers are not identities. Historical `processed/legacy-inquery-<legacy-id>/` remains inactive Processed evidence with legacy status/provenance, never another type or active workspace.

Original preserves diverse native/source-appropriate bytes. Active Processed uses a portable `index.html`, `styles.css`, `app.js` package; sharing that shape with Human Specifications grants no Specification authority. Physical migration preserves type, identity, provenance and recorded relationships; no roots imply a pipeline or promotion. Code/script retirement never authorizes deleting Human data, source, credentials or backups. Cutover, destructive actions and unresolved conflict policy retain exact Human authority.

## Ecosystem boundary

This ownership layout is not a universal application source tree. Follow each owning ecosystem's accepted layout and dependency guidance. Python packaging, for example, offers src and flat layouts with different import/installation tradeoffs: [Python Packaging User Guide](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/). Do not project Agent Factory runtime paths onto unrelated application code.
