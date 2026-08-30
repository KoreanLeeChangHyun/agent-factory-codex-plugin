# Agent Factory Core Model

## Authority and identity

The Human-established Specification identity is `agent-factory-core`, based on
“Agent-Factory 코어 개념들.” Its paired AI-facing owner is now the distributed
`convention` Skill. The
canonical Specification body has two faithful projections:

- Human-facing Korean HTML, CSS, and JavaScript in the current local adapter:
  `.agent-factory/document/specification/human/agent-factory-core/`
- AI-facing English distributed plugin Skill: `skills/convention/`

These projections may use different presentation forms, but they must contain
the same decisions, relationships, current implementation observations, and
unresolved questions. Neither projection may privately add or omit specified
knowledge.

The accepted decisions and required semantic model below come from the Human's
delegated core Specification request at
`.agent-factory/agent/agent-factory-core-spec-work/runs/run-20260827T171518255940Z-9be41ed7/request.md`. Repository
observations are separately attributed. The earlier Human decision to implement
Interview as a distributed Skill came from
`.agent-factory/agent/interview-skill-work/runs/run-20260827T174030938939Z-d3e6f56f/request.md` and is superseded by the
five-public-Skill decision below. The engineering synthesis at
`.agent-factory/document/processed/legacy-inquery/agent-factory-engineering-synthesis-20260828/synthesis.md`
is supporting, non-canonical evidence only.

The Human decision to retire the distributed `inquery` Skill and managed
Inquiry role, assign evidence exploration to Explorer, and retain adaptive
Human-facing elicitation in Interview comes from
`.agent-factory/agent/inquery-retirement-split-work/runs/run-20260827T180810962479Z-6077b043/request.md`.
Legacy Inquery contents are preserved as processed historical project data at
`.agent-factory/document/processed/legacy-inquery/`.

The Human decision that Main is the Human-facing Interview, orchestration, and
integration layer; delegates research, implementation, independent review,
verification, and recovery; and never executes those tasks directly comes from
`.agent-factory/agent/main-interface-orchestration-work/runs/run-20260827T185954481797Z-83e4ca60/request.md`.

The Human decision that project-scoped Project Skills use the canonical
`<category>-<name>` identity comes from
`.agent-factory/agent/project-skill-naming-work-20260828/runs/run-20260827T183744485278Z-1d60a54e/request.md`.

The Human decisions that original information retains diverse source-native
formats, active processed documents use Markdown under the current/default
local adapter, and refined paired representations have a mandatory fail-closed
synchronization contract come from
`.agent-factory/agent/lifecycle-format-implementation-work-20260830/runs/run-20260829T155842596703Z-31b14ca9/request.md`.

The superseding Human decisions that this repository owns plugin Skills only
below `skills/`, has no `.codex/skills/` store, and treats document storage as
adapter-resolved rather than intrinsically `.agent-factory/` come from
`.agent-factory/agent/project-skill-naming-work-20260828/runs/run-20260827T184536518402Z-9b6f2283/request.md`.

The earlier consolidation decision—keep six public Skills, make Convention the
AI-facing owner of Agent Factory core, use the three-stage local information
tree, migrate Human refined and legacy processed documents, and retain
storage-backend independence—comes from
`.agent-factory/agent/project-skill-naming-work-20260828/runs/run-20260827T185448822401Z-ef49909a/request.md`.

The superseding contracts keep Explorer and Interview as distinct core
capabilities without independent public Skill entry points. The five-public-
Skill decision and Explorer's capability boundary are recorded in
`.agent-factory/agent/document-types-work/runs/run-20260830T070110807574Z-61393ff6/request.md`.
Main's Interview conduct and delegation of research are recorded in
`.agent-factory/agent/main-interface-orchestration-work/runs/run-20260827T185954481797Z-83e4ca60/request.md`,
while the exact Convention-reference links applied by Main and Work are
recorded in
`.agent-factory/agent/convention-prompt-link-work/runs/run-20260830T040515493151Z-713220d2/request.md`.

The Workspace control-tower contract makes `workspace` the Human-facing surface
for project oversight without transferring canonical ownership or execution
from the underlying domains. Its accepted scope and owner-mediated boundary
are recorded in
`.agent-factory/agent/workspace-work/runs/run-20260830T084555205214Z-18e640b1/request.md`.

The expanded Workspace decision defines six control-tower oversight areas:
Roadmap, Schedule, Agent Orchestration, Documents, Logs, and Test Center.
Oversight means source-backed visibility, health/status presentation, anomaly
and attention signaling, drill-down, and clearly authorized owner-mediated
control handoff. Workspace does not become the canonical owner or executor of
roadmap/schedule data, Agent runtime state, Documents, logs, or tests. Missing
source contracts remain visibly unconfigured instead of being represented by
fabricated status. This decision comes from
`.agent-factory/agent/workspace-work/runs/run-20260830T084555205214Z-18e640b1/request.md`.

The final Workspace Activity redirect supersedes that six-area navigation.
The Activity Bar has exactly five top-level items, in order and labeled 일정,
에이전트, 문서, 로그, 테스트. Roadmap, Explorer/File Explorer,
Planning/Specification, Project Skills, overview/dashboard, and aliases are
not top-level items. The Human has not yet decided any Activity's Primary
Sidebar information architecture, detailed capabilities, hierarchy, controls,
metrics, or source contract, so none may be inferred or nested. Workspace
retains its observation/control-routing boundary and does not own or execute
schedule data, Agent runtime state, Documents, logs, or tests. This decision
comes from
`.agent-factory/agent/workspace-work/runs/run-20260830T090533619149Z-bfd9f5fa/request.md`.

The Workspace publication decision requires its browser code in two forms:
reusable installation sources below `skills/workspace/assets/browser/` and the
current project's installed publication below
`.agent-factory/workspace/common/`. The packaged `index.html`, `styles.css`,
and `app.js` are the installation source, while `common/` is the materialized
project copy; both forms must exist and remain byte-identical. A missing,
one-sided, semantically divergent, or byte-divergent change is incomplete.
`serve.py init` materializes the packaged files under the existing safe
preflight and force contract. This decision comes from
`.agent-factory/agent/workspace-work/runs/run-20260830T092305700450Z-683ed85d/request.md`.

The superseding Human decision renames the public `specification` Skill to
`document` and introduced an earlier three-type terminology that the final
redirect below replaces. The relationship was already loose rather than a
mandatory pipeline or transition system. The five public distributed
Skills are now `gather`, `convention`, `agent`, `document`, and `workspace`.
This decision comes from
`.agent-factory/agent/document-types-work/runs/run-20260830T070110807574Z-61393ff6/request.md`.

The final Human redirect supersedes those three type names while preserving
the public `document` Skill identity. The active types are Original,
Processed, and Specification. Their conceptual ordering is
`Original -> Processed -> Specification`, with each arrow expressing only a
possible derivation or evidence relationship. Specification is the accepted
and reconciled project-knowledge type with the mandatory faithful Human/AI
pair; Refined is not a fourth active type. This decision comes from
`.agent-factory/agent/document-types-work/runs/run-20260830T072849765327Z-1f535f3f/request.md`.

The final local-adapter root decision permits exactly the `agent/`, `document/`,
and `workspace/` top-level responsibility directories. `document/` contains
`original/`, `processed/`, and `specification/`; Gather configuration is
`document/sync.json`. Explorer has no standalone storage domain: durable
evidence is classified as Original or Processed, while temporary
execution-only material remains in the producing managed Agent run. The
Workspace `explorer/` path remains a read-only projection. This decision comes
from `.agent-factory/agent/document-root-migration-work/runs/run-20260830T085419496276Z-66baeaeb/request.md`.

The Human-approved local catalog decision reserves the exact path
`<project-root>/.agent-factory/db.sqlite` for one project-wide SQLite
catalog/read model spanning Agent execution structure and Documents. The
catalog is initially rebuildable and non-authoritative. The active bounded
implementation is schema-only: no database instance, scanner, rebuild/index
job, runtime dual write, Workspace screen or API, search behavior, or external
backend ingestion is authorized. This decision comes from
`.agent-factory/agent/shared-db-work/runs/run-20260830T085102207719Z-c11abc11/request.md`.

## Project Skill naming

For a newly named Skill identity whose owning context requires the two-part
form, `category` classifies the Skill for discovery and `name` identifies its
bounded knowledge or capability.
Both components use lowercase hyphen-case tokens, so a multiword component may
itself contain hyphens. The complete `<category>-<name>` value uses lowercase
letters, digits, and hyphens, remains under the Codex Skill name limit, and
must exactly match both the Skill directory and the `name` field in `SKILL.md`
frontmatter.

Neither component may be inferred when Human instruction or unambiguous
accepted project evidence does not supply it. Preserve accepted Skill
identities: this rule does not authorize bulk renaming. Explorer and Interview
retain their accepted capability identities without retaining public Skill
identities. The durable Agent Factory core rules are consolidated into
`skills/convention/`. Separate
consumer projects may use the rule for
their Specification Project Skills at
`<project-root>/.codex/skills/<category>-<name>/`; this plugin repository has no
repository-local `.codex/skills/` store.

## Storage-independent Document types and roles

Document types and document roles are logical concepts independent of
physical storage. `.agent-factory/` is the current/default local work and
document adapter, not a universal canonical location. An explicitly resolved
alternative may be a project server, external document store, mounted
filesystem, or another configured backend.

Changing the adapter does not weaken Document type, provenance, authority,
isolation, semantic alignment, accessibility, or security requirements. Never
silently mirror, migrate, or select a canonical backend. Backend
configuration, identity, synchronization and conflict policy, authentication,
availability, and caching remain unresolved Human or implementation decisions.
Current local scripts and runtime paths are observed local implementations;
they do not prove remote or server adapters exist.

## Shared local catalog

The current/default local adapter reserves
`<project-root>/.agent-factory/db.sqlite` as a project-wide SQLite catalog/read
model for later Workspace queries across Agent execution structure and
Documents. It is shared only as a projection boundary: Workspace gains no
Agent or Document semantics from displaying it, and the catalog creates no new
public Skill or Agent role.

The catalog is rebuildable and non-authoritative. Agent runtime files,
Document bodies and representations, relationship/provenance evidence, Gather
configuration, Project Skills, and faithful Specification pairs remain in
their existing resolved authoritative stores. Large bodies, event streams,
requests, results, receipts, heartbeats, and containment or recovery evidence
do not belong in SQLite. Paths, hashes, bounded summaries, statuses, and
relationships may be projected only when an inspectable source provides them;
unknown and legacy values remain explicit, and absent relations are never
inferred.

Workspace owns the maintained standard-library SQLite DDL at
`skills/workspace/assets/schema/catalog.sql`. Its initial normalized schema
covers schema metadata/migrations, Agents and resumable sessions, runs/turns,
Work/Verification loops, graph/dispatch relationships, Documents and their
storage-independent types, representations, provenance/derivation
relationships, Agent-Document relationships, and Specification pair status.
The DDL is an idempotent schema foundation only. Database initialization,
scanners, rebuild/index jobs, runtime/database dual writes, screens, APIs,
navigation, and search remain outside this bounded implementation.

Do not commit `db.sqlite` or its SQLite runtime sidecars. Do not make Agent
execution depend on catalog freshness or availability, and do not silently
select, mirror, migrate, or ingest an external backend.

## Human-facing Workspace shell and launcher

Workspace uses a developer-familiar VS Code-shaped Human control-tower shell
whose primary spatial relationship is `Activity Bar -> Primary Sidebar ->
Workspace`. The reusable shell is packaged below
`skills/workspace/assets/browser/` and installed in the project at
`.agent-factory/workspace/common/`. Its `index.html`, `styles.css`, and
`app.js` must exist in both forms and remain byte-identical. The packaged files
are the reusable installation source and the local files are the materialized
publication, not an independent canonical source. `serve.py init` creates or,
when safely forced, replaces the local copies from the package without
weakening preflight, path-containment, symlink, atomic-copy, or launcher rules.

For the local adapter, the reusable launcher source is
`skills/workspace/assets/workspace.sh`; its
project-installed copy is the ordinary file `<project-root>/workspace.sh`. The
installation contract is copy-once: initialization preserves an existing root
launcher, including when force is requested. The original shell and launcher
decision is recorded in
`.agent-factory/agent/project-skill-naming-work-20260828/runs/run-20260827T183901489117Z-e71747f6/request.md`;
the current Workspace ownership and location are observed in
`skills/workspace/SKILL.md` and `skills/workspace/references/interface.md`.
A server-hosted Workspace
is exposed by its selected host or adapter and is not required to use
`workspace.sh` remotely.

## Document model

`Document` is the neutral umbrella for three active logical types: Original,
Processed, and Specification. Their conceptual ordering is
`Original -> Processed -> Specification`, but each arrow expresses only a
possible derivation or evidence relationship. The ordering is not a mandatory
pipeline, state machine, required transition, one-to-one mapping, completeness
claim, or automatic promotion mechanism. A Document may remain in one type
without producing another. Relationships may be absent, one-to-many,
many-to-one, or many-to-many. Preserve inspectable provenance for relationships
that actually exist. Refined is not a fourth active type, and the three active
type names are never combined.

### Original Document (원본문서)

Source-faithful evidence with inspectable provenance. Fidelity to the source,
source identity, and collection context must be retained in the native or
source-appropriate form. Original Documents may have diverse formats; do not
impose one canonical file format. Original does not mean inferior, incomplete,
or untrusted and implies no required successor.

### Processed Document (가공문서)

Analysis, comparison, hypotheses, research results, interview results, and
other transformations. A Processed Document may be useful and well-supported,
but it remains non-authoritative working knowledge and implies no required
Specification. Processed remains a logical, storage-independent
type. Under the current/default local adapter, active Processed Documents are
Markdown (`.md`). Preserved legacy material under
`document/processed/legacy-inquery/` is not an active target or format
precedent.

### Specification (스펙 문서)

Accepted and reconciled project knowledge that preserves important provenance,
records honest unresolved state, and defines requirements, constraints, or a
normative project model. A Specification is one semantic body with two faithful
representations: an AI-facing Skill and a Human-facing Korean HTML, CSS, and
JavaScript document. The pair must always remain semantically synchronized. A
one-sided change is incomplete and unacceptable; if synchronization cannot be
achieved, the change or run must not be reported as completed.

## Core capability topology

### Gather

Gather synchronizes project-needed external Documents scattered across Google Drive,
OneDrive, Slack, Notion, Discord, and similar cloud sources. It preserves that
material as Original Documents, including source fidelity, identity, and
provenance. It does not define the other Document types or promote evidence to
Specification truth.

### Explorer

Explorer explores all project-needed information by analyzing and researching
the web, code, and Documents. It may consume Original or Processed Documents
and may produce Original or Processed Documents. It does not independently
accept or reconcile Specification truth.

### Interview

Interview reduces the information gap between AI and Humans through interviews
and produces Processed Documents. It is conducted adaptively by the Main
Agent in the current conversation rather than exposed as a public Skill or
managed Exec role; it does not independently promote results to Specification
truth. Main may pause or
  sequence the Interview while Work applies Explorer to gather necessary background,
then resume the Human conversation while keeping Human statements, Explorer
evidence, and Main interpretation distinct. Explorer never interviews or
impersonates the Human.

### Document

Document defines Original, Processed, and Specification Documents and their distinct
contracts. Gather retains ownership of external synchronization. Document work
may maintain a Document in only one type or preserve inspectable derivation and
evidence relationships of any cardinality. Document enforces every
Specification's faithful Human-facing Korean browser and AI-facing Skill pair.
Visual diagrams, graphs, flows, and
tables are preferred in the Human projection when they improve understanding.

### Convention

Convention records constraints AI must follow while working and acts as a weak
harness. It is a cross-cutting control layer across all Document types rather
than another Document type.

### Agent

Agent is the AI Agent execution domain. It spans work on all Document types and incorporates
Prompt Engineering, Context Engineering, Loop Engineering, Agent Graph
Engineering, and Agentic Engineering. It is an execution layer, not a fourth
Document type. Main owns Human interaction, Interview, orchestration, and
integration but performs neither Work nor Verification. Work performs every
bounded task, including Explorer research and implementation. Verification
independently returns pass or fail unless the Human skips it; failure returns
to the same Work Agent. A skip is Human-only, evidenced control-plane intent,
not a graph transition or completion. It may be recorded before the next
Verification starts, is applied only after the current initial or revision Work
completes, starts no next or additional Verification, and then reaches END.
Verification pass also reaches END.

### Workspace

Workspace is the Human-facing project control tower with exactly five
top-level Activities in this order: 일정, 에이전트, 문서, 로그, 테스트. No
other top-level item or alias is allowed. Only these broad categories are
decided; every Activity's Primary Sidebar information architecture, detailed
capabilities, hierarchy, controls, metrics, and source contract remain
Human-owned and undecided. The packaged browser therefore presents explicit
awaiting-definition states rather than project data or inferred structure.
Workspace does not become the canonical owner or executor of schedule data,
Agent runtime records, Documents, logs, or tests, and any future mutation must
use the owner's explicit authority contract. Workspace is a cross-cutting
Human management surface rather than another Document type. In the local
adapter, durable Explorer evidence is
classified below `.agent-factory/document/original/` or
`.agent-factory/document/processed/`, while temporary execution-only material
remains in the producing managed Agent run.
The internal read-only `.agent-factory/workspace/explorer/` File/Project
metadata projection and `.agent-factory/workspace/skills/` Skill-navigation
projection define neither a top-level Activity nor nesting under one of the
five. The Explorer projection may show classified durable Document metadata;
temporary Explorer material stays only in its producing managed Agent run.

## Responsibility matrix

| Capability | Principal inputs | Produces or manages | Boundary |
| --- | --- | --- | --- |
| Gather | Distributed cloud sources | Original Documents | Synchronize external Documents while preserving fidelity and provenance; do not define other types |
| Explorer | Web, code, Documents, Original/Processed material | Original and Processed Documents | Explore, analyze, and research; do not accept or reconcile Specification truth |
| Interview | Human knowledge and questions | Processed Documents | Reduce the AI-Human information gap through an adaptive Main-Agent conversation; do not independently create Specification truth |
| Document | Documents and grounded Human decisions | Original, Processed, and Specification Documents | Define all three types, preserve optional provenance relationships, and pair every Specification |
| Convention | Human-defined working constraints | Cross-cutting control | Weak harness across all Document types |
| Agent | Role, authority, context, tools, state | Cross-cutting execution | Main orchestrates, Work performs bounded tasks, and Verification independently checks unless the Human skips it |
| Workspace | Future owner-resolved schedule, Agent, Document, log, and test sources | Five-category Human control tower | Exactly five ordered top-level Activities; sidebar architecture and detailed capabilities remain undecided; never own or execute projected state |

## Agent engineering stack

The layers are related scopes, not competing names:

1. **Prompt Engineering** defines per-turn instructions and the output
   contract.
2. **Context Engineering** selects and assembles turn inputs while preserving
   provenance and isolation.
3. **Loop Engineering** defines iteration, feedback, convergence, stop, and
   recovery behavior.
4. **Agent Graph Engineering** defines relationships among Agents, Humans,
   tasks, tools, state, and evidence.
5. **Agentic Engineering** governs lifecycle-wide identity, authority, safety,
   evaluation, observability, and governance.

The nested presentation in the Human document communicates increasing scope:
Prompt is per turn; Context forms the turn's evidence boundary; Loop governs
repeated turns; Agent Graph connects actors and artifacts; Agentic Engineering
governs the complete operating lifecycle.

## Observed current implementation

These are observations, not accepted completion claims or replacements for the
target conceptual model:

- `.codex-plugin/plugin.json` describes five public Agent Factory Skills:
  Gather, Convention, Agent, Document, and Workspace. This public discovery
  surface does not replace the accepted seven-capability topology.
- `skills/convention/references/explorer.md` and
  `skills/convention/references/interview.md` own the durable semantic,
  information, provenance, and authority boundaries for Explorer and Interview.
- `skills/agent/SKILL.md` implements exactly the Main -> Work -> Verification
  graph. Work applies Explorer as a bounded evidence task, while Main applies
  Interview in the Human conversation. Neither capability has an independent
  public Skill entry point or Agent role.
- `skills/gather/SKILL.md` establishes source-faithful external synchronization;
  `skills/document/SKILL.md` establishes all three Document types and paired
  Human/AI Specifications; and `skills/agent/SKILL.md` establishes
  managed Agent execution and role boundaries. These are present implementation foundations,
  not proof that the entire accepted core topology is complete.
- `skills/workspace/SKILL.md` owns the Human control tower, with packaged UI and
  launcher assets below `skills/workspace/` and local materialization below
  `.agent-factory/workspace/`. Its packaged shell exposes exactly 일정,
  에이전트, 문서, 로그, 테스트 as top-level navigation, in that order, with
  explicit awaiting-definition views. It exposes no other top-level Activity
  and does not infer sidebar structure or live integration from existing
  discovery utilities. The packaged and materialized `index.html`,
  `styles.css`, and `app.js` are maintained byte-identically, with the package
  serving as the reusable installation source.
- `skills/workspace/assets/schema/catalog.sql` is the maintained schema-only
  foundation for the approved local catalog. No `.agent-factory/db.sqlite`
  artifact or catalog population behavior is part of this implementation.

## Unresolved architecture decisions

1. Roadmap priority, deadline, owner, acceptance status, risk acceptance, and
   completion state remain Human-owned and unspecified.
2. The five Activities' Primary Sidebar information architecture, detailed
   capabilities, hierarchy, controls, metrics, and source contracts remain
   unresolved. The Agent runtime has an owning local contract, but the
   Workspace redirect does not define its projection.
   Catalog initialization, population/rebuild, freshness, sanitized query/API,
   search, and dual-write behavior also remain unimplemented.

## Representation-alignment checklist

When changing either projection, compare both and preserve:

- all three loosely related Document types, optional relationship
  cardinalities, and authority boundaries;
- all seven capabilities and their inputs, outputs, and cross-cutting roles;
- all five Agent engineering layers and their scopes;
- the five-public-Skill discovery surface and the separate seven-capability
  topology, including Convention-owned semantics and Agent-owned execution;
- the Main-owned Interview and orchestration topology, including Work-applied
  Explorer and the Main -> Work -> Verification graph, plus unspecified
  Human-owned planning/status fields and the Human-only evidenced skip intent
  that applies after current Work completion without starting another
  Verification;
- provenance for accepted decisions and repository observations;
- the `<category>-<name>` identity contract, its owning-context scope, exact
  directory/frontmatter match, and no-bulk-renaming boundary;
- the Workspace-owned VS Code-shaped Activity Bar, Primary Sidebar, and main
  Workspace relationship; exactly five ordered top-level items labeled 일정,
  에이전트, 문서, 로그, 테스트; undecided sidebar/capability details; no
  aliases or inferred nesting; the owner-mediated boundary; and the local
  byte-identical packaged-browser-to-materialized-common publication contract,
  plus the packaged-to-root copy-once `workspace.sh` launcher contract;
- the distributed-plugin versus consumer-Project-Skill ownership split and the
  storage-independent document model with unresolved backend integration;
- the exact `.agent-factory/db.sqlite` local catalog path, its rebuildable and
  non-authoritative scope, Workspace-owned schema asset, authoritative-store
  boundaries, explicit unknown/legacy handling, no inferred relationships, and
  schema-only exclusions for creation/population/UI/API/search/dual writes;
- diverse native/source-appropriate Original formats, the local-adapter
  Markdown contract for active Processed Documents, and the exclusion of
  preserved legacy Inquery material as an active target or precedent;
- the mandatory fail-closed synchronization contract for every Specification
  Human/AI pair.
