# Recommended Directory Structure

Use this structure as Agent Factory's current/default local adapter:

```text
<project-root>/.agent-factory/
├── db.sqlite
├── agent/
│   └── <agent-id>/
│       ├── session.json
│       └── runs/
│           └── <run-id>/
├── document/
│   ├── original/
│   ├── processed/
│   ├── specification/
│   │   └── human/
│   └── sync.json
└── workspace/
│   ├── common/
│   ├── explorer/
│   └── skills/
```

## Ownership

- `db.sqlite` is the exact current/default local path for the project-wide,
  rebuildable, non-authoritative catalog/read model used by later Workspace
  queries across Agent execution structure and Documents. It does not replace
  or move any owning file or store. The database and its SQLite runtime
  sidecars are local generated artifacts and must not be committed.
- `agent/` owns operational Agent sessions and run records.
- Temporary execution-only Explorer material belongs to its producing managed
  Agent run. Durable Explorer evidence is classified as an Original or
  Processed Document; Explorer has no standalone storage root.
- `document/` owns the local adapter roots for the three loosely related
  active Document types: Original, Processed, and Specification. Preserve
  Original Documents in diverse native or
  source-appropriate formats. Write active Processed Documents as Markdown
  (`.md`) under this local adapter, but
  do not use preserved `document/processed/legacy-inquery/` material as an
  active target or format precedent. Put locally materialized Human-facing
  Specifications in `document/specification/human/`. The roots do
  not impose a pipeline, transition sequence, maturity scale, or mapping
  cardinality among Documents.
- `workspace/` owns the local Human control-tower projection. `common/` holds
  the shared browser shell, `.agent-factory/workspace/explorer/` holds the
  internal read-only File/Project metadata projection, and `skills/` holds
  internal read-only Project Skill navigation. These stores define neither an
  Activity nor nesting under one of the five Activities. The Explorer
  projection discovers the project and classified Document trees without
  copying or owning either; temporary Explorer material remains in its
  producing managed Agent run.
- `document/sync.json` holds Gather configuration, not gathered source collections.
- Tool has no current/default local-adapter responsibility directory. Do not
  create `.agent-factory/tool/`; each host, plugin, MCP server, project
  manifest, or explicitly selected provider remains authoritative, and Tool
  registry/state storage is unresolved.

Keep plugin distributed Skills below `<plugin-root>/skills/`. In a separate
consumer project, keep Project Skills below
`<project-root>/.codex/skills/<category>-<name>/`. Neither belongs below
`.agent-factory/`, and Gather writes source collections only to its explicitly
resolved destination outside this work root.

This layout is a local adapter, not a universal storage requirement. An
explicitly selected project server or external document store may replace a
document root while preserving provenance, authority, isolation, semantic
alignment, accessibility, and security. Do not silently choose, mirror, or
migrate a backend. Keep Agent runtime state under the declared local runtime
contract unless that contract is separately changed.

The maintained schema foundation for the local catalog is
`skills/workspace/assets/schema/catalog.sql`. It models only projection
metadata and relationships that authoritative local sources actually expose;
it is not permission to scan, rebuild, dual-write, or ingest an external
backend.

Directory layouts outside this Agent Factory adapter remain technology- and
distribution-specific. For example, Python's official packaging guide presents
`src` and flat layouts as alternatives with different import and installation
tradeoffs rather than one universal tree. Follow the owning ecosystem's
official layout guidance instead of projecting this adapter onto application
source code:

- [Python Packaging User Guide: src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
