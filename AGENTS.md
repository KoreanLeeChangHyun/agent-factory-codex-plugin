<agent-factory>
Always load and comply with Agent Factory skills.

Use the six public Skills by responsibility: `agent` owns Agent execution,
Work/Verification capability binding, authority, orchestration, and receipts;
`convention` owns Agent rules, shared safety, least privilege, and approval
conventions; `document` defines and maintains Original, Processed, and
Specification Documents; `gather` owns bounded read-only external source
synchronization and its Original Document output; `tool` owns the logical
lifecycle/control contract for Agent-usable external tools and connectors; and
`workspace` is the Human control tower for managing Agents, documents, and the
project. Explorer and Interview remain capabilities, not separate public
Skills.

Treat Main as the Human-facing adaptive Interview, orchestration, and result
integration layer. Main performs no Work or Verification directly. Route every
bounded task, including research and implementation, to Work and route
independent checking to Verification unless the Human skips it. A failed
Verification returns to the same Work Agent; a pass or Human skip ends the
graph. Explorer is a Convention-owned capability applied within Work, not a
separate Agent role, and never impersonates or interviews the Human.

After an independent Verification pass, or after an evidenced Human skip is
applied following Work completion, Main promptly performs an authorized Git
commit itself as narrow result integration/publication. Do not delegate a
separate commit Work turn. Main inspects and stages only the exact paths bound
to the verified or skipped result and excludes unrelated dirty changes. Work
and Verification never commit. Commit authority does not imply push, amend,
force, history rewrite, or any other repository publication or mutation.

This repository is the Agent Factory plugin. Store this plugin's distributed
Skills below `<plugin-root>/skills/`; do not create or mirror them below this
repository's `.codex/`.

For every separate project that uses this plugin, store that project's
Project Skills below `<project-root>/.codex/skills/`. Keep each Project Skill in
one self-contained directory with `SKILL.md`, YAML Agent configuration in
`agents/`, reference material in `assets/`, Markdown documents in `references/`,
and Agent-usable scripts in `scripts/`.

Use this project-local structure as the current/default local adapter, not as a
universal document-storage requirement:

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

Use the exact `db.sqlite` path for the current/default local adapter's shared,
rebuildable, non-authoritative catalog/read model across Agent execution
structure and Documents. It does not own or replace the authoritative files or
stores it projects. Agent owns its maintained schema asset at
`skills/agent/assets/schema/catalog.sql` and standard-library manager at
`skills/agent/scripts/catalog.py`, including explicit initialization,
rebuild, read-only status inspection, bounded FTS5 Agent and Document search,
publication/recovery safety, and schema evolution. The database and SQLite
runtime sidecars are local generated artifacts and must not be committed. Rebuild
projects authorized Agent metadata plus local Document metadata and capped
allowlisted textual representations, publishes atomically after integrity
checks, and remains independent from Agent execution; it does not add runtime
dual writes, an HTTP/general query API, a watcher, semantic/vector search, a
search UI, or external-backend ingestion.
Workspace may only present Agent-provided read-only results; it does not own,
initialize, rebuild, inspect, or execute searches against the catalog.

Keep operational Agent runtime state in `agent/`. Keep temporary execution-only
Explorer material in the producing managed Agent run. Classify durable Explorer
evidence as an Original or Processed Document under `document/`. Keep Gather
configuration in `document/sync.json`. Use `document/` for
the three Document types: Original, Processed, and Specification. Their
conceptual ordering is `Original -> Processed -> Specification`, but each arrow
is only a possible derivation or evidence relationship. The types are not a
mandatory pipeline, state machine, required transition, maturity scale, or
one-to-one mapping. A Document may remain in one type; relationships may be
absent or have any cardinality. Preserve inspectable provenance when a
relationship exists without inferring completeness or automatic promotion.
Original Documents may retain diverse source-native formats;
preserve source fidelity, identity, provenance, collection context, and a
native or source-appropriate form instead of imposing a canonical file format.
In this local adapter, active Processed Documents are Markdown (`.md`), while
Processed remains a logical, storage-independent Document type. Store locally
materialized Human-facing Specifications below `document/specification/`.
Every immediate child of `document/original/`, `document/processed/`, or
`document/specification/` is exactly one Document package named by its stable
Document identity. Package-internal files and directories are allowed, but do
not add producer, category, or legacy wrapper layers between a type root and a
Document package. Preserved legacy Inquery packages use explicit
`legacy-inquery-<legacy-id>` identities directly below `document/processed/`;
their legacy status is provenance/status metadata, never a fourth Document
type or a wrapper directory, and they are not active targets.
Within the local adapter's `workspace/`, `common/` owns the shared browser
shell, `.agent-factory/workspace/explorer/` owns an internal read-only
File/Project metadata projection, and `skills/` owns internal read-only Skill
navigation. These stores define neither an Activity nor nesting under one of
the five Activities. The Explorer projection discovers and displays the project
and classified Document trees without copying or becoming the canonical owner
of either; temporary Explorer material remains in its producing managed Agent
run.
Workspace reads Human-facing Specifications from `document/specification/` rather
than owning a document directory.

A Specification is accepted and reconciled project knowledge represented as
one semantic body by exactly one resolved AI-facing Skill representation and
exactly one resolved Human-facing Korean HTML, CSS, and JavaScript
representation. Both representations use the same stable identity and must
remain semantically synchronized; a one-sided change is incomplete and
unacceptable. If both representations cannot be synchronized, do not report
the change or run as completed. Their concrete locators are adapter-resolved,
not universally required directories. Under the current/default local adapter,
the representations are one Skill directory and one Human-facing
Specification directory. In this plugin repository, pair each distributed
`skills/<skill-id>/` with
`.agent-factory/document/specification/<skill-id>/`; do not create or mirror
`.codex/skills/` here. In an ordinary consumer project using the local adapter,
both paired directories use the exact lowercase hyphen-case
`<category>-<title>` identity: `.codex/skills/<category>-<title>/` pairs with
`.agent-factory/document/specification/<category>-<title>/`. This plugin is the
explicit exception whose existing single-name distributed Skill and
Specification IDs remain `agent`, `convention`, `document`, `gather`, `tool`,
and `workspace`. An explicitly resolved external backend may use different
locators while preserving the one-to-one pair and stable identity. Organize
each Korean Human view for readability rather than mechanically mirroring the
Skill hierarchy, and map material sections to exact paths within its paired
Skill. Do not create a standalone representation or an aggregate Specification
for multiple Skills.

Original, Processed, and Specification Document types and document roles are
logical and storage-independent. Do not introduce Refined as a fourth active
type or combine the three active type names.
An explicitly resolved alternative store, such as a project server, external
document store, mounted filesystem, or configured backend, may replace the
local document adapter while preserving provenance, authority, isolation,
semantic alignment, accessibility, and security. Do not silently choose,
mirror, or migrate a backend. Keep operational Agent runtime state under the
declared local runtime contract unless separately changed. Do not put Project
Skills or gathered source collections below `.agent-factory/`; Gather uses its
resolved destination outside this work root.

Do not create `.agent-factory/tool/` or silently select a Tool registry or
state backend. Tool preserves the authority of each host, plugin, MCP server,
project manifest, or explicitly selected provider and records only logical
lifecycle metadata, never credentials or tokens. Gather declares connector
capability, minimum permission scope, Human-approval need, and selection bounds;
Tool must not escalate scope. Until concrete Tool connection/token and Gather
capability/scope interfaces exist, keep the observed Google Drive and OneDrive
authentication implementation in Gather and treat migration as unresolved.
</agent-factory>
