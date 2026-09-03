# Agent Factory Core Model

## Authority and identity

Agent Factory has exactly six public distributed Skills—`agent`, `convention`,
`document`, `gather`, `tool`, and `workspace`—and eight core capabilities: those
six plus Explorer and Interview. Explorer and Interview are Convention-owned
capabilities applied by Agent roles, not public Skills or extra Agent nodes.

Each Specification is one accepted semantic body with exactly one resolved
AI-facing Skill and exactly one resolved Human-facing Korean browser document
under the same stable identity. Concrete locations are adapter-resolved; an
external backend may use different locators while preserving the one-to-one
pair. Both representations preserve the same source order, hierarchy, meaning,
identity, and provenance; reciprocal metadata alone does not prove alignment. A
one-sided change is incomplete and unacceptable. Do not report it as completed;
partial, stale, reordered, duplicated, summarized, or mistranslated pairs fail
closed as well.

This repository's `convention` pair is:

```text
skills/convention/
.agent-factory/document/specification/convention/
```

Do not create a repository-local `.codex/skills/` mirror. Navigation, tables,
and diagrams may supplement but never replace or repeat the complete Human
translation.

## Project Skill naming

An ordinary consumer-project pair uses one Human-resolved lowercase hyphen-case
`<category>-<title>` identity for the Skill name, AI directory, and Human
Specification directory:

```text
<project-root>/.codex/skills/<category>-<title>/
<project-root>/.agent-factory/document/specification/<category>-<title>/
```

Do not infer either component, bulk-rename accepted identities, or treat these
local paths as a universal backend. This plugin is the explicit single-name
identity exception. An explicitly resolved external adapter may use different
locators while preserving the same one-to-one pair.

## Documents and storage

`Document` covers exactly three storage-independent types:

- Original (`원본 문서`) is source-faithful evidence in a native or
  source-appropriate form.
- Processed (`가공 문서`) is transformed, non-authoritative working knowledge.
- Specification (`명세 문서`) is accepted and reconciled project knowledge with
  the synchronized Human/AI pair above.

`Original -> Processed -> Specification` expresses only a possible evidence or
derivation relationship. It is not a pipeline, state machine, maturity scale,
required transition, completeness claim, or one-to-one mapping. Relationships
may have any cardinality or be absent; record provenance only for relationships
that exist. Refined is not a fourth type.

The current/default `.agent-factory/` adapter keeps each Document as one direct
package below its type root. Active Processed Documents and Human
Specifications share a portable `index.html`, `styles.css`, and `app.js`
browser-package shape, but shared format grants no shared authority or AI pair.
Preserved `legacy-inquery-*` packages remain inactive Processed evidence rather
than a format precedent.

The local type roots are `.agent-factory/document/original/` and
`.agent-factory/document/processed/` for durable Documents, while temporary
execution-only material remains in the producing managed Agent run. Workspace
has no project-local runtime or projection directory. The separate Agent
Factory MCP application provides tenant-scoped projections without copying a
browser shell, launcher, port state, or Workspace-owned data into a consumer
project.

An explicitly resolved backend may replace a local document root without
weakening identity, provenance, authority, isolation, semantic alignment,
accessibility, or security. Never silently choose, mirror, migrate, or designate
a backend as canonical. Backend identity, synchronization, conflict policy,
authentication, availability, and caching remain unresolved until accepted.

## Adapter boundary

Document adapter initialization and physical migration belong to the public
`document` Skill and remain separate from semantic classification,
transformation, reconciliation, and acceptance. Physical migration preserves
`documentType`, identity, provenance, authority, and Specification pairing.

LLM output may advise or author but is never executable. A deterministic
manager may act only from a closed, versioned, allowlisted plan/IR after current
state and required Human authority are revalidated. Stale plans, path escape,
symlinks, unresolved conflicts, unsupported operations, type promotion,
unauthorized destructive behavior, and integrity mismatches fail closed.
Specification pairs publish as one recoverable group.

## Capability ownership

- Gather selects and synchronizes bounded external sources into Original
  Documents while preserving fidelity, identity, provenance, destination, and
  read-only intent.
- Tool manages logical discovery, lifecycle, connection, scope, health, and
  capability metadata while each host, plugin, MCP server, project manifest, or
  provider remains authoritative. It stores no secrets and executes no Agent or
  Gather work.
- Explorer performs bounded evidence exploration for Work and may create
  Original or Processed evidence. It does not interview Humans or accept
  Specification truth.
- Interview is adaptive elicitation conducted by Main in the Human conversation.
  It produces Processed knowledge by default and cannot grant authority or
  acceptance.
- Document owns the three Document types and semantic work on resolved targets.
- Convention owns this core model and cross-cutting rules.
- Agent owns the `Main -> Work -> Verification` execution graph, capability
  binding, runtime receipts, and the local catalog.
- Workspace is the Human control tower and projects only owner-backed state.

For connector-backed collection, Gather declares the capability, exact source
bound, resolved destination, minimum requested scope, and any Human or
administrator approval. Tool resolves connection state and reports the actual
granted scope without escalation. Existing provider-specific authentication in
Gather remains an observed coupling until a concrete replacement interface is
implemented and separately authorized.

Tool never escalates scope automatically and creates no `.agent-factory/tool/`
root. Workspace, not Tool, owns the `외부연동` Activity projection. Google Drive
and OneDrive provider scripts retain their observed authentication coupling
until an authorized replacement exists.

## Agent graph and engineering layers

Main interviews the Human, resolves authority, decomposes and delegates bounded
work, integrates verified results, and owns authorized narrow Git publication.
Work executes but does not verify or commit. Verification independently checks
the latest Work result, never fixes it, and returns failures to the same Work
session. The graph ends only after Verification passes or an evidenced Human
skip is applied after the current Work completes.

Main stages only paths bound to that result and never infers push, amend, force,
history rewrite, reset, restore, or delete authority from a commit request.
Human-owned priority, deadline, owner, acceptance, risk acceptance, and
completion remain unresolved until explicitly decided.

Human skip intent must record the Human actor, authorization reference, and
decision evidence before the next Verification starts. The record is not a
graph transition or completion. It takes effect only after the current initial
or revision Work completes, starts no next or additional Verification, and
reaches END. Non-Human skip attempts fail closed.

Agent engineering expands through five nested scopes:

1. Prompt Engineering shapes one model interaction.
2. Context Engineering assembles its bounded evidence and tool context.
3. Loop Engineering governs iteration, feedback, stopping, and recovery.
4. Agent Graph Engineering coordinates Humans, Agents, tasks, tools, state, and
   evidence.
5. Agentic Engineering governs the complete lifecycle, safety, evaluation,
   observability, and governance.

## Catalog and Workspace

Agent owns the rebuildable, non-authoritative local catalog at
`<project-root>/.agent-factory/db.sqlite`, including schema, initialization,
rebuild, inspection, search, publication, and recovery. Workspace never operates
the database and may present only Agent-provided read-only results.

Workspace uses `작업 표시줄 -> 기본 사이드바 -> 작업 영역` and exactly six
top-level Activities in this order: 일정, 에이전트, 문서, 외부연동, 로그, 테스트.
The `외부연동` sidebar has ordered purpose groups `웹·리서치`, `문서·파일`,
`메일·메시지`, `일정·회의`, `지식·업무관리`, `개발·운영`, and
`데이터·비즈니스`.
The Document sidebar uses `원본 문서`, `가공 문서`, and `명세 문서`; they do
not rename logical types, identifiers, metadata, or paths. Its detailed
information architecture belongs to `skills/workspace/references/activities.md`;
browser, tab, split, launcher, publication, and security behavior belongs to
`skills/workspace/references/interface.md`. Unresolved live integrations,
Original source/query behavior, mutation authority, and Activity detail must not
be invented.

The Agent Factory MCP application owns the Workspace FastAPI runtime, MCP
transport, discovery routes, deployment adapters, tests, and canonical browser
assets under its `static/workspace/` package. The plugin retains the Workspace
Skill and Human Specification contract; target projects retain their owning
Documents, Skills, and read-only projections without receiving a browser-shell
copy or root launcher.

## Decision provenance and current state

The exact six-Skill decision is recorded in
`.agent-factory/agent/six-skill-core-sync-work-20260830/runs/run-20260830T103238358728Z-5e61ab5d/request.md`.
The current consolidated representation is established by
`skills/convention/references/agent-factory-core.md`.

The active contracts above consolidate Human decisions from managed run requests
for the core model, Inquery retirement, Main orchestration, Document
types and roots, Project Skill naming, six public Skills, Workspace activities
and document browsing, adapter migration, catalog ownership and search, and Git
publication. The detailed provenance remains inspectable under
`.agent-factory/agent/*/runs/*/request.md`; the owning Specifications retain the
exact operational rules.

Observed implementation currently includes the six distributed Skills, the
three-role Agent runtime, Convention-owned Explorer and Interview references,
provider Gather scripts, stateless Tool inspection, synchronized Human/AI
Specification packages, the Workspace shell, and the Agent-owned catalog
manager. Observation does not prove full acceptance, completion, or a remote
backend.

## Unresolved architecture decisions

The following remain unresolved unless their owning Specification records a
later accepted decision:

- roadmap priority, deadline, owner, acceptance, completion, and risk acceptance;
- Original Overview content, live source/query integration, synchronization
  trigger and status, metadata-mutation authority and persistence, External
  Integration category navigation and child-source behavior, and the other four
  unresolved Activities' sidebar architecture. The other four unresolved
  Activity sidebars and capabilities remain Human-owned and unresolved. The
  decided Original table uses
  global and per-column filtering, link/provider-cell behavior, and Human column
  resizing/reordering, with ordered columns `문서 분류`, `출처`, `태그`,
  `문서 이름`, `확장자`, and `수정 일자`;
- Tool registry/state storage and concrete host/plugin/MCP/provider adapters;
- the Document adapter manager/API, plan schema, journal, identity/hash,
  approval, conflict, cutover, backend-capability, alignment, and recovery
  implementation.

## Representation-alignment checklist

When either representation changes, verify its complete ordered source manifest
and independently compare the Human and AI bodies for bilingual meaning. Use
each owning Specification for domain detail instead of copying that detail into
this core reference. Fail closed on missing, stale, reordered, duplicated, or
semantically mismatched coverage.
