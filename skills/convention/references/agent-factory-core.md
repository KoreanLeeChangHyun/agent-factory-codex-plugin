# Agent Factory Core Model

## Authority and identity

Agent Factory has exactly two public distributed Skills: `agent` and
`convention`. Document, Gather, Tool, and Workspace are domains of the selected
Agent Factory MCP application, not plugin Skills. Explorer and Interview are
Convention-owned capabilities applied by Agent roles, not public Skills or
extra Agent nodes.

AI Skills provide Agent instructions. Korean documents are independently
maintained references. Use current Skills and authenticated MCP schemas for
operational contracts. See `directory-structure.md` for source and runtime paths.

## Project Skill naming

An ordinary consumer Project Skill uses one Human-resolved lowercase hyphen-case `<category>-<title>` identity for its name. An installed Project Skill may live at `<project-root>/.codex/skills/<category>-<title>/`; historical local Human source packages at `.agent-factory/document/specification/<category>-<title>/` are migration inputs, not new consumer runtime roots. Cloud resolves the published Human revision locator.

Do not infer either component or bulk-rename accepted identities. This plugin is the explicit single-name identity exception. Preserve actual identity and provenance across source, installed and published locators.

## Documents and storage

`Document` covers exactly three storage-independent types:

- Original (`원본 문서`) is source-faithful evidence in a native or
  source-appropriate form.
- Processed (`가공 문서`) is transformed, non-authoritative working knowledge.
- Specification (`명세 문서`) is accepted and reconciled project knowledge.

`Original -> Processed -> Specification` expresses only a possible evidence or
derivation relationship. It is not a pipeline, state machine, maturity scale,
required transition, completeness claim, or one-to-one mapping. Relationships
may have any cardinality or be absent; record provenance only for relationships
that exist. Refined is not a fourth type.

Active Processed Documents and Human Specifications share a portable `index.html`, `styles.css`, `app.js` browser package, but shared format grants no shared authority. Historical `legacy-inquery-*` packages remain inactive Processed evidence.

The Human-selected cloud MCP application owns new Document persistence, search
and publication, connection/authentication and collection configuration, shared
reporting and Workspace. Git owns distributable Skill authoring and optional
local reference documents. Distinguish source-package, installed Skill and cloud revision locators while
preserving actual identity and provenance. Cloud owns its accepted revisions.

Local exec/loop, prompts and minimum runtime dependencies retain process/session/run and graph authority. Local run/outbox/recovery stays local; use existing shell/file tools for local inspection and authorized cloud tools for required durable evidence. Read advertised authenticated schemas/guides first. Missing capability/connection/tenant/scope fails honestly; do not create a local MCP/provider service or infer accounts. Keep legacy local data/configuration/catalog until inventory, independent backup and verified import. Local domain executables are retired after verified replacement. Code retirement never authorizes Human data deletion. Cloud choice is accepted; actual tenant/account/credential identities and unresolved destructive or conflict decisions remain Human-owned.

## Adapter boundary

Document adapter initialization and physical migration belong to the MCP
Document domain and remain separate from semantic classification,
transformation, reconciliation, and acceptance. Physical migration preserves
`documentType`, identity, provenance, authority, and recorded relationships.

LLM output may advise or author but is never executable. A deterministic
manager may act only from a closed, versioned, allowlisted plan/IR after current
state and required Human authority are revalidated. Stale plans, path escape,
symlinks, unresolved conflicts, unsupported operations, type promotion,
unauthorized destructive behavior, and integrity mismatches fail closed.
Publication follows the selected MCP application's current authenticated schema.

## Capability ownership

- The MCP Gather domain selects and synchronizes bounded external sources into
  Original Documents while preserving fidelity, identity, provenance,
  destination, and read-only intent.
- The MCP Tool domain manages logical discovery, lifecycle, connection, scope,
  health, and capability metadata while each host, plugin, MCP server, project
  manifest, or provider remains authoritative. It stores no secrets and does
  not grant Agent execution authority.
- Explorer performs bounded evidence exploration for Work and may create
  Original or Processed evidence. It does not interview Humans or accept
  Specification truth.
- Interview is adaptive elicitation conducted by Main in the Human conversation.
  It produces Processed knowledge by default and cannot grant authority or
  acceptance.
- The MCP Document domain owns operations on resolved Document targets.
- Convention owns this core model and cross-cutting rules.
- Agent owns the `Main -> Work -> Verification` execution graph, capability
  binding, local runtime facts, graph transitions and receipts.
- The MCP Workspace domain is the Human control tower and projects only
  owner-backed state.

For connector-backed collection, the MCP request declares the capability,
exact source bound, resolved destination, minimum requested scope, and any
Human or administrator approval. MCP integration tools resolve connection state
and report the actual granted scope without escalation. Provider executables
are retired and legacy token caches remain with their credential authority.
The MCP application never escalates scope automatically or creates a project
`.agent-factory/tool/`; actual providers and cloud credential authority retain
their state.

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

Cloud owns new catalog/search and shared reporting. Local `db.sqlite` is retained legacy non-authoritative data, never a new-work route. Reporting task state, process observations and planning tasks do not execute or complete local runs or the loop. Read each owner's schema and distinguish freshness, semantic result and graph END.

Workspace uses `작업 표시줄 -> 기본 사이드바 -> 작업 영역` and exactly six
top-level Activities in this order: 일정, 에이전트, 문서, 외부연동, 로그, 테스트.
The `외부연동` sidebar has ordered purpose groups `웹·리서치`, `문서·파일`,
`메일·메시지`, `일정·회의`, `지식·업무관리`, `개발·운영`, and
`데이터·비즈니스`.
The Document sidebar uses `원본 문서`, `가공 문서`, and `명세 문서`; they do
not rename logical types, identifiers, metadata, or paths. Detailed information
architecture, browser behavior, publication, and security belong to the current
authenticated MCP Workspace guides and schemas. Unresolved live integrations,
Original source/query behavior, mutation authority, and Activity detail must
not be invented.

The Agent Factory MCP application owns the Workspace FastAPI runtime, MCP
transport, discovery routes, deployment adapters, tests, and canonical browser
assets under its `static/workspace/` package. The plugin distributes no
Workspace Skill or Workspace Human Specification; consumer projects retain
their own Skill installation and local run data without receiving a Document
backend, browser-shell copy or root launcher.

## Decision provenance and current state

The Human decision on 2026-09-09 supersedes the historical six-Skill
distribution: the plugin now distributes only `agent` and `convention`, while
Document, Gather, Tool, and Workspace belong to the MCP application. The
current consolidated contract is this reference. Korean references are independently maintained.

The active contracts above consolidate Human decisions from managed run requests
for the core model, Inquery retirement, Main orchestration, Document
types and roots, Project Skill naming, two public Skills, Workspace activities
and document browsing, adapter migration, catalog ownership and search, and Git
publication. The detailed provenance remains inspectable under
`.agent-factory/agent/*/runs/*/request.md`; the owning Specifications retain the
exact operational rules.

The latest cloud migration request supersedes earlier unresolved-backend, local-catalog and provider-script routing. Source modules and guides in the sibling MCP application describe Document, integration and reporting capabilities; contract authoring does not attest registration, live accounts, deployment or complete migration steps 1–13.

## Unresolved architecture decisions

Do not invent roadmap priority, deadlines, owners, acceptance, completion or
risk acceptance. Current authenticated MCP resources own resolved Workspace
information architecture, common 작업 terminology, and planning import.
Agents/logs/tests sidebar detail, overview contents, and external-category
navigation remain Human-owned unless later explicitly resolved. Browser library
selection belongs to the cloud application's dependency policy.

Concrete tenant/account selection, credential authority, live connection, registration, deployment, data cutover/retention/deletion and unresolved conflicts still need their owning evidence or decision. A cloud implementation does not itself resolve every UI control, third-party host lifecycle or semantic acceptance.

## Skill maintenance

Check Skill metadata, routed references, owned runtime behavior and authority
boundaries. Read authenticated MCP resources for domain details instead of copying them
into this core reference.
