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
│   └── sync.json
└── workspace/
│   ├── common/
│   ├── explorer/
│   └── skills/
```

## Ownership

- `db.sqlite` is the exact current/default local path for the Agent-owned,
  project-wide, rebuildable, non-authoritative catalog/read model across Agent
  execution structure and Documents. It does not replace or move any owning
  file or store. The database and its SQLite runtime sidecars are local
  generated artifacts and must not be committed.
- `agent/` owns operational Agent sessions and run records.
- Temporary execution-only Explorer material belongs to its producing managed
  Agent run. Durable Explorer evidence is classified as an Original or
  Processed Document; Explorer has no standalone storage root.
- `document/` owns the local adapter roots for the three loosely related
  active Document types: Original, Processed, and Specification. Preserve
  Original Documents in diverse native or
  source-appropriate formats. Write active Processed Documents as Markdown
  (`.md`) under this local adapter. Every immediate child directory of each
  type root is exactly one Document package with a stable identity; internal
  files and directories belong to that package, and producer/category/legacy
  wrapper layers are not allowed. Preserved historical Inquery packages use
  direct `document/processed/legacy-inquery-<legacy-id>/` identities, remain
  Processed, and express legacy only through status/provenance metadata. Do not
  use them as active targets or format precedents. Put locally materialized Human-facing
  Specifications in `document/specification/`. The roots do
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

Keep plugin distributed Skills below `<plugin-root>/skills/`. Under this
current/default local adapter, in an ordinary consumer project keep the paired
Project Skill and Human Specification directories under the exact same
lowercase hyphen-case identity:
`<project-root>/.codex/skills/<category>-<title>/` and
`<project-root>/.agent-factory/document/specification/<category>-<title>/`.
This plugin is the explicit exception whose accepted single-name pairs remain
unchanged. Neither Skill root belongs below
`.agent-factory/`, and Gather writes source collections only to its explicitly
resolved destination outside this work root.

In this plugin repository, every `skills/<skill-id>/` directory has exactly one
Human-facing `.agent-factory/document/specification/<skill-id>/` pair. Each is
linked through reciprocal metadata and reorganized for Human readability with
exact source mappings inside that Skill; it neither copies the tree nor creates
a repository-local `.codex/skills/` mirror.

This layout is a local adapter, not a universal storage requirement. An
explicitly selected project server or external document store may replace a
document root while preserving provenance, authority, isolation, semantic
alignment, accessibility, and security. Do not silently choose, mirror, or
migrate a backend. Keep Agent runtime state under the declared local runtime
contract unless that contract is separately changed.

Agent owns the catalog schema, manager, and complete operational contract under
`skills/agent/`. Convention records only that cross-cutting ownership boundary;
the detailed command, safety, search, and indexing rules belong to the Agent
Specification.

Directory layouts outside this Agent Factory adapter remain technology- and
distribution-specific. For example, Python's official packaging guide presents
`src` and flat layouts as alternatives with different import and installation
tradeoffs rather than one universal tree. Follow the owning ecosystem's
official layout guidance instead of projecting this adapter onto application
source code:

- [Python Packaging User Guide: src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
