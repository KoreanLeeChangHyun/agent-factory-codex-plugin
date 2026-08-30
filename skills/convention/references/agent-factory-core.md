# Agent Factory Core Model

## Authority and identity

The Convention Specification identity is `convention`. Its canonical semantic
body has exactly one resolved AI-facing representation and exactly one resolved
Human-facing representation under that same stable identity. In the
current/default local adapter, those faithful projections are:

- Human-facing Korean HTML, CSS, and JavaScript in the current local adapter:
  `.agent-factory/document/specification/convention/`
- AI-facing distributed Skill and supporting resources: `skills/convention/`

These projections may use different presentation forms, but they must contain
the same decisions, relationships, current implementation observations, and
unresolved questions. Neither projection may privately add or omit specified
knowledge.

The concrete locators are adapter-resolved rather than universal directory
requirements. An explicitly resolved external backend may use different
locators while preserving the exact one-to-one pair, stable identity,
authority, and semantic alignment. The Human projection is organized around readable Korean topics, summaries,
tables, and flows rather than mechanically mirroring the Skill hierarchy.
Each material section maps to exact Skill/reference source paths. Reciprocal
HTML and Convention frontmatter locators establish identity and scope only;
they do not prove semantic alignment by hash or raw-copy equality. Do not
create or mirror `.codex/skills/` in this plugin repository. The other five
distributed Skills each have their own one-to-one Specification pair.

The accepted decisions and required semantic model below come from the Human's
delegated core Specification request at
`.agent-factory/agent/agent-factory-core-spec-work/runs/run-20260827T171518255940Z-9be41ed7/request.md`. Repository
observations are separately attributed. The earlier Human decision to implement
Interview as a distributed Skill came from
`.agent-factory/agent/interview-skill-work/runs/run-20260827T174030938939Z-d3e6f56f/request.md` and is superseded by the
former five-public-Skill decision and the latest six-Skill decision below. The engineering synthesis at
`.agent-factory/document/processed/legacy-inquery-agent-factory-engineering-synthesis-20260828/synthesis.md`
is supporting, non-canonical evidence only.

The Human decision to retire the distributed `inquery` Skill and managed
Inquiry role, assign evidence exploration to Explorer, and retain adaptive
Human-facing elicitation in Interview comes from
`.agent-factory/agent/inquery-retirement-split-work/runs/run-20260827T180810962479Z-6077b043/request.md`.
Legacy Inquery contents are preserved as direct Processed packages below
`.agent-factory/document/processed/`; each stable identity starts with the
non-path identity prefix `legacy-inquery-`.

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

The earlier consolidation decision—keep six public Skills under a prior
identity set, make Convention the
AI-facing owner of Agent Factory core, use the three-stage local information
tree, migrate Human refined and legacy processed documents, and retain
storage-backend independence—comes from
`.agent-factory/agent/project-skill-naming-work-20260828/runs/run-20260827T185448822401Z-ef49909a/request.md`.

The current Human decision supersedes that aggregate pairing shape: each of
the six distributed Skill directories now has its own one-to-one Human
Specification directory under the same identity. Convention remains the owner
of shared core semantics, not the AI-side locator for the other five pairs.

The superseding contracts keep Explorer and Interview as distinct core
capabilities without independent public Skill entry points. The former five-
public-Skill decision and Explorer's capability boundary are recorded in
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
not top-level items. This decision comes from
`.agent-factory/agent/workspace-work/runs/run-20260830T090533619149Z-bfd9f5fa/request.md`.

The superseding Document Activity decision defines only its Primary Sidebar
and main-view shapes. It has three prominent, independently collapsible groups
in order: `원본문서`, `가공문서`, and `스펙문서`. Original has `개요` and
`문서검색`, with search selecting a semantic table shell. Processed and
Specification each have `개요` and consistent explorer/tree-shaped regions
reserved for actual Documents. The no-space `스펙문서` spelling is the UI
label and does not rename the Specification type. That decision initially left
overview details, table columns and behavior, and discovery/source integration
unresolved. The current Workspace contract has since fixed the Original search
view as a compact, tab-free Tabulator 6.5.2 table with global search,
per-column filters, resizing/reordering, and exact ordered columns `문서 분류`,
`출처`, `태그`, `문서 이름`, `확장자`, `수정 일자`; only document-name cells
link to the source Original, and provider cells use visible provider text with
decorative inline SVG. Overview content, live source/query integration,
synchronization and metadata-mutation contracts, and all four other Activity
sidebars and detailed capabilities remain unresolved. Workspace
retains its observation/control-routing boundary and does not own or execute
schedule data, Agent runtime state, Documents, logs, or tests. This decision
comes from
`.agent-factory/agent/workspace-document-work/runs/run-20260830T141127363791Z-f665d487/request.md`.

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

The three named files remain the core browser code. The packaged and
materialized forms also contain byte-identical `THIRD_PARTY_NOTICES.txt`
companion assets carrying required attribution and license text. `serve.py
init` installs that companion through the same asset-copy contract; the notice
is not a fourth browser-code file. This current companion-asset clarification
comes from
`.agent-factory/agent/document-consistency-completion-work-20260830/runs/run-20260830T123400206653Z-185e3f0e/request.md`.

The Human-accepted documentation-first contract for Document adapter
initialization, physical migration, and conditional LLM participation comes
from
`.agent-factory/agent/document-adapter-contract-docs-work/runs/run-20260830T135328504819Z-24544fc7/request.md`.
Its complete Document-owned operational design reference is
`skills/document/references/adapter.md`. The researched recommendations that
informed the Human direction remain evidence, not an independent source of
accepted product decisions.

The superseding Human decision renames the public `specification` Skill to
`document` and introduced an earlier three-type terminology that the final
redirect below replaces. The relationship was already loose rather than a
mandatory pipeline or transition system. It established the former five public
distributed Skills: `gather`, `convention`, `agent`, `document`, and `workspace`.
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

The latest Human decision removes the representation-only `human/` layer from
the local Specification tree. Each locally materialized Human-facing browser
document now lives directly at
`.agent-factory/document/specification/<specification-id>/`; its AI-facing
Skill remains in its separately owned Skill root. This physical flattening does
not weaken the mandatory semantic pair or create another Document type.

The earlier Human-approved local catalog decision reserved the exact path
`<project-root>/.agent-factory/db.sqlite` for one project-wide SQLite
catalog/read model spanning Agent execution structure and Documents. The
catalog remained rebuildable and non-authoritative. The initial decision comes from
`.agent-factory/agent/shared-db-work/runs/run-20260830T085102207719Z-c11abc11/request.md`.
The earlier adoption decision came from
`.agent-factory/agent/sqlite-adoption-work/runs/run-20260830T153751477078Z-57de39e2/request.md`.

The later Human decision implements bounded Agent and Document search over
that catalog. It authorizes FTS5 projections from Agent structural metadata and
safe bounded local Document text, plus read-only CLI search; it does not
authorize a Workspace search UI, HTTP/general query API, watcher, runtime dual
write, semantic/vector search, or external-backend ingestion. This decision
comes from `.agent-factory/agent/catalog-search-work/runs/run-20260830T155949742576Z-5bc8cccf/request.md`.

The latest Human decision assigns the complete catalog implementation and
table-management lifecycle to Agent and supersedes inferred Workspace
ownership and initialization. Workspace may only become a presentation
consumer of Agent-provided read-only results. This decision comes from
`.agent-factory/agent/catalog-owner-work/runs/run-20260830T174324574670Z-c5a8167b/request.md`.

The latest Human decision supersedes the former five-Skill discovery contract
with exactly six public distributed Skills in the consistent order `agent`,
`convention`, `document`, `gather`, `tool`, and `workspace`. Tool is the logical
control plane for Agent-usable external tool and connector lifecycle. Gather
remains independent and uses a Tool-prepared connector while retaining source
selection, destination, bounded read-only synchronization, source fidelity,
identity, provenance, and Original Document output. This decision is supplied
by the managed Human request at
`.agent-factory/agent/six-skill-core-sync-work-20260830/runs/run-20260830T103238358728Z-5e61ab5d/request.md`.

The Human decision that Main promptly performs Git commits directly, without a
separate commit Work turn, comes from
.agent-factory/agent/main-commit-convention-request.md. This is narrow result
integration/publication only after an independent Verification pass or an
evidenced Human skip applied following Work completion. It leaves Work and
Verification unable to commit, requires exact staging of only the bound result
paths while excluding unrelated dirty changes, and supplies no authority for
push, amend, force, history rewrite, or other repository mutation.

## Project Skill naming

For an ordinary consumer-project pair, `category` classifies the Skill for
discovery and `title` identifies its bounded knowledge or capability.
Both components use lowercase hyphen-case tokens, so a multiword component may
itself contain hyphens. The complete `<category>-<title>` value uses lowercase
letters, digits, and hyphens, remains under the Codex Skill name limit, and
must exactly match both resolved representations and the `name` field in
`SKILL.md` frontmatter. Under the current/default local adapter, it also
exactly matches the Project Skill and Human Specification directory names.

Neither component may be inferred when Human instruction or unambiguous
accepted project evidence does not supply it. Preserve accepted Skill
identities: this rule does not authorize bulk renaming. Explorer and Interview
retain their accepted capability identities without retaining public Skill
identities. The durable Agent Factory core rules are consolidated into
`skills/convention/`. Under the current/default local adapter, ordinary
consumer projects use the exact same lowercase hyphen-case
`<category>-<title>` identity for both representation directories:
`<project-root>/.codex/skills/<category>-<title>/` and
`<project-root>/.agent-factory/document/specification/<category>-<title>/`.
This plugin is the explicit exception whose accepted single-name distributed
Skill and Specification identities remain unchanged; it has no repository-local
`.codex/skills/` store. An explicitly resolved external backend may use
different locators while preserving the same identity and one-to-one pair.

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

The exact `<project-root>/.agent-factory/db.sqlite` path and its complete
implementation lifecycle are Agent-owned. The catalog remains ignored,
rebuildable, non-authoritative, and independent of Agent execution; it cannot
replace authoritative Agent runtime or Document sources. Workspace performs no
catalog initialization, rebuild, inspection, or search execution and may only
present Agent-provided read-only results. The Agent
Specification owns all detailed command, schema, indexing, safety,
publication, and recovery rules.

## Human-facing Workspace shell and launcher

Workspace uses a developer-familiar VS Code-shaped Human control-tower shell
whose primary spatial relationship is `Activity Bar -> Primary Sidebar ->
Workspace`. The reusable shell is packaged below
`skills/workspace/assets/browser/` and installed in the project at
`.agent-factory/workspace/common/`. Its `index.html`, `styles.css`, and
`app.js` are the three core browser-code files and must exist in both forms and
remain byte-identical. The companion `THIRD_PARTY_NOTICES.txt` attribution and
license asset must likewise exist in both forms, be installed by `serve.py
init`, and remain byte-identical; it is not a fourth browser-code file. The
packaged files are the reusable installation source and the local files are
the materialized publication, not an independent canonical source. `serve.py
init` creates or, when safely forced, replaces the local copies from the
package without weakening preflight, path-containment, symlink, atomic-copy, or
launcher rules.

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
Markdown (`.md`). Every immediate type-root child directory is exactly one
Document package. Preserved historical Inquery packages use direct
`document/processed/legacy-inquery-<legacy-id>/` identities, remain Processed,
and record legacy only as status/provenance. They are not active targets or
format precedents.

### Specification (스펙 문서)

Accepted and reconciled project knowledge that preserves important provenance,
records honest unresolved state, and defines requirements, constraints, or a
normative project model. A Specification is one semantic body with exactly one
resolved AI-facing Skill representation and exactly one resolved Human-facing
Korean HTML, CSS, and JavaScript representation under the same stable identity.
Their concrete locators are adapter-resolved. The pair must always remain
semantically synchronized. A one-sided change is incomplete and unacceptable;
if synchronization cannot be achieved, the change or run must not be reported
as completed.

## Document adapter initialization and physical migration

Initialization and physical adapter/layout migration are capabilities inside
the public `document` Skill, not another public Skill or Agent role. Keep them
distinct from semantic Document work. Initialization deterministically and
idempotently establishes compatible physical structure for an explicitly
resolved adapter. Physical migration changes adapter, layout, locator, or
representation placement while preserving Document identity, provenance,
authority, pair binding, and `documentType`. It never performs or implies
`Original -> Processed -> Specification` promotion; classification,
transformation, reconciliation, and acceptance remain separately authorized
semantic Document work.

No LLM is required for initialization, and no LLM controls locks, hashes,
copying, moving, overwrite, delete, state transitions, commit, cutover,
integrity verdicts, or recovery. Within advisory/authoring Work, an LLM may
propose evidence-backed legacy classifications, provenance candidates,
difficult format transformations, semantic reconciliation, and synchronized
Specification drafts. Uncertainty remains `unknown` or `requiresDecision`.
Raw LLM output is non-executable.

Any proposal that may inform physical execution must be compiled and validated
by deterministic code into a closed, versioned plan/IR. It allowlists and binds
operations, contained paths, identities, immutable Document type,
preconditions, exact effects, validation, recovery, expiry/staleness, and
authority references. A deterministic manager may execute only that bounded
plan after revalidating current state and obtaining any required Human
authority. Stale plans, unknown operations or fields, executable free-form
content, path escape or symlinks, unresolved conflicts, missing provenance or
authority, type promotion, unsupported capabilities, unauthorized destructive
or cutover behavior, and integrity mismatches fail closed.

A Specification's Human and AI representations are one migration and
authoring group. Both must be staged and semantically aligned. A one-sided
result is incomplete. If the adapter cannot guarantee atomic pair publication,
the prior canonical authority remains in force and execution stops in a
recoverable staged state. Conceptual operations include initialize,
inspect/plan, migrate, integrity-check, and recover; these labels are not
accepted CLI spelling. A deterministic integrity-check provides evidence and
must not be confused with or replace the independent Agent Verification role.

The Agent graph remains unchanged. Main interviews, resolves authority,
orchestrates, and integrates without performing Work or Verification. Work may
perform LLM advisory/authoring and, under separate exact authority, invoke the
deterministic manager. Verification independently checks evidence; fail returns
to the same Work Agent, while pass or an evidenced Human skip ends the graph.

Gather continues to own external synchronization and `document/sync.json`;
Tool continues to own connector lifecycle without credentials or execution
authority; Agent continues to own capability binding, authority, and receipts;
Workspace may only project or route owner-backed control; and
`.agent-factory/db.sqlite` remains a rebuildable, non-authoritative catalog,
never a migration manifest or recovery source. The manager, proposal/IR
schemas, manifest and journal, command names, approval thresholds, backend
capability requirements, pair-alignment evidence, and recovery implementation
remain unimplemented or unresolved.

## Core capability topology

The accepted topology now contains eight capabilities. Six have public Skill
entry points; Explorer and Interview remain Convention-owned capabilities
applied through Agent roles.

### Gather

Gather synchronizes project-needed external Documents scattered across Google Drive,
OneDrive, Slack, Notion, Discord, and similar cloud sources. It preserves that
material as Original Documents, including source fidelity, identity, and
provenance. It does not define the other Document types or promote evidence to
Specification truth.

For connector-backed collection, Gather declares the capability, minimum
permission scope, Human-approval or administrator-consent need, and exact
selection bounds. It receives connection readiness and actually granted scope
through Tool without transferring synchronization or Original Document
ownership.

### Tool

Tool provides one logical lifecycle/control contract across Agent-usable
external tools and connectors such as Playwright, pytest, Office, Google Drive,
and OneDrive. It owns discovery/catalog metadata, install/update/remove routing,
connection and authentication lifecycle, opaque credential references,
requested and granted permission scopes, availability/health, enable/disable
state, and capability metadata.

Each host, plugin, MCP server, project manifest, or explicitly selected
provider remains authoritative. Tool stores no credential or token, does not
execute Agent work, does not own Gather synchronization, does not choose a
registry/state backend, and creates no `.agent-factory/tool/` root or Workspace
Activity. Current Google Drive and OneDrive provider scripts retain their
authentication/token-cache code as observed coupling until concrete Tool
connection/token and Gather capability/scope interfaces exist and migration is
separately authorized and verified. Tool never escalates scope automatically.

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
independently returns pass or fail unless a Human-only skip intent with an
authorization reference and decision evidence is applied; failure returns to
the same Work Agent. Recording skip intent before the next Verification starts
is not a graph transition or completion. It is applied only after the current
initial or revision Work completes, starts no next or additional Verification,
and then reaches END.
Verification pass also reaches END.
Tool may establish capability readiness, but Agent retains Work/Verification
capability binding, execution authority, dispatch, and execution receipts.
After pass or an evidenced Human skip applied after Work completion, Main may
promptly perform the authorized ordinary Git commit itself as narrow result
integration/publication. This does not add a graph node or delegate commit to
Work: Main stages only exact bound result paths, excludes unrelated dirty
changes, and infers no push, amend, force, or history-rewrite authority.

### Workspace

Workspace is the Human-facing project control tower with exactly five
top-level Activities in this order: 일정, 에이전트, 문서, 로그, 테스트. No
other top-level item or alias is allowed. The Document Primary Sidebar has the
decided ordered, independently collapsible `원본문서`, `가공문서`, and
`스펙문서` groups. Original provides overview and a compact, tab-free Tabulator
6.5.2 search view with global search, filters on all six exact ordered columns
(`문서 분류`, `출처`, `태그`, `문서 이름`, `확장자`, `수정 일자`),
responsive width distribution with narrow-view horizontal overflow, and Human
resizing and reordering. Only document-name cells link to source Originals;
provider cells combine visible provider text with decorative inline SVG.
Processed and Specification provide overview and consistent explorer/tree
regions for actual Documents. The UI label does not rename Specification.
Overview content, live source/query integration, synchronization and metadata
mutation, and the other four Activity sidebars and capabilities remain
Human-owned and unresolved. The packaged
browser presents explicit awaiting-definition or awaiting-connection states
rather than project data or inferred source behavior.
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
projection do not define a top-level Activity or authorize nesting under one
of the five. The Explorer projection may show classified durable Document metadata;
temporary Explorer material stays only in its producing managed Agent run.

## Responsibility matrix

| Capability | Principal inputs | Produces or manages | Boundary |
| --- | --- | --- | --- |
| Gather | Distributed cloud sources | Original Documents | Synchronize external Documents while preserving fidelity and provenance; do not define other types |
| Tool | Authoritative host, plugin, MCP, project-manifest, and provider metadata | Logical external tool/connector lifecycle control | Preserve provider authority; manage metadata, connection/scope/health/enablement without storing secrets, executing tasks, or owning Gather sync |
| Explorer | Web, code, Documents, Original/Processed material | Original and Processed Documents | Explore, analyze, and research; do not accept or reconcile Specification truth |
| Interview | Human knowledge and questions | Processed Documents | Reduce the AI-Human information gap through an adaptive Main-Agent conversation; do not independently create Specification truth |
| Document | Documents and grounded Human decisions | Original, Processed, and Specification Documents | Define all three types, preserve optional provenance relationships, and pair every Specification |
| Convention | Human-defined working constraints | Cross-cutting control | Weak harness across all Document types |
| Agent | Role, authority, context, Tool-prepared capabilities, state | Cross-cutting execution | Bind capabilities, authorize and receipt execution; Main orchestrates, Work performs bounded tasks, and Verification independently checks unless the Human skips it |
| Workspace | Future owner-resolved schedule, Agent, Document, log, and test sources | Five-category Human control tower | Exactly five ordered top-level Activities; the three-group Document sidebar, view shapes, and six-column Original search behavior are decided; overview/live integration/mutation contracts and the other four sidebars remain unresolved; never own or execute projected state |

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

- `.codex-plugin/plugin.json` describes six public Agent Factory Skills:
  Agent, Convention, Document, Gather, Tool, and Workspace. This public
  discovery surface does not replace the accepted eight-capability topology.
- `skills/convention/references/explorer.md` and
  `skills/convention/references/interview.md` own the durable semantic,
  information, provenance, and authority boundaries for Explorer and Interview.
- `skills/agent/SKILL.md` implements exactly the Main -> Work -> Verification
  graph. Work applies Explorer as a bounded evidence task, while Main applies
  Interview in the Human conversation. Neither capability has an independent
  public Skill entry point or Agent role.
- `skills/gather/SKILL.md` establishes source-faithful external synchronization;
  `skills/tool/SKILL.md` establishes the logical external tool/connector
  lifecycle boundary without implementing a registry or state backend;
  `skills/document/SKILL.md` establishes all three Document types and paired
  Human/AI Specifications; and `skills/agent/SKILL.md` establishes
  managed Agent execution and role boundaries. These are present implementation foundations,
  not proof that the entire accepted core topology is complete.
- `skills/workspace/SKILL.md` owns the Human control tower, with packaged UI and
  launcher assets below `skills/workspace/` and local materialization below
  `.agent-factory/workspace/`. Its packaged shell exposes exactly 일정,
  에이전트, 문서, 로그, 테스트 as top-level navigation, in that order, with
  the decided three-group Document sidebar and honest awaiting-definition or
  awaiting-connection details. It exposes no other top-level Activity and does
  not infer live integration from existing discovery utilities. The packaged
  and materialized `index.html`,
  `styles.css`, and `app.js` are maintained byte-identically, with the package
  serving as the reusable installation source.
- `skills/agent/assets/schema/catalog.sql` is the maintained schema and
  `skills/agent/scripts/catalog.py` is the implemented local manager. The
  current project materializes the ignored `.agent-factory/db.sqlite` artifact
  through explicit Agent-owned operations; Workspace initialization has no
  catalog side effect.

## Unresolved architecture decisions

1. Roadmap priority, deadline, owner, acceptance status, risk acceptance, and
   completion state remain Human-owned and unspecified.
2. The Document sidebar's three ordered groups and overview/table/tree view
   shapes are decided. Original search also has decided six-column ordering,
   global and per-column filtering, sorting, link/provider-cell behavior,
   responsive sizing, and Human column resizing/reordering. Its overview
   content, live source/query integration, synchronization trigger and status,
   metadata-mutation authority and persistence, and the other four Activities'
   sidebar architecture and detailed capabilities remain unresolved. The Agent
   runtime has an owning local contract, but the Workspace decision does not
   define its projection.
   Catalog search screens, HTTP/general query APIs, semantic/vector search,
   live-watcher, freshness automation, and dual-write behavior remain
   unimplemented; bounded read-only FTS5 CLI search is Agent-owned.
3. Tool registry/state storage and concrete host/plugin/MCP/project-manifest
   adapters remain unresolved. The Tool connection/token lifecycle interface,
   Gather capability/scope request interface, and migration of currently
   coupled Google Drive/OneDrive authentication code are not implemented.
4. The Document adapter manager/API and exact command names, proposal and
   compiled-IR schemas, manifest/registry/journal paths and formats, stable
   identity and hash rules, approval thresholds and evidence, conflict and
   cutover policy, backend capability/metadata requirements, Specification pair
   alignment evidence, and recovery implementation remain unresolved. The
   documentation-first contract does not claim any of them are implemented.

## Representation-alignment checklist

When changing either projection, compare both and preserve:

- all three loosely related Document types, optional relationship
  cardinalities, and authority boundaries;
- all eight capabilities and their inputs, outputs, and cross-cutting roles;
- all five Agent engineering layers and their scopes;
- the six-public-Skill discovery surface and the separate eight-capability
  topology, including Convention-owned semantics and Agent-owned execution;
- the Tool/Gather boundary: Tool lifecycle control and preserved provider
  authority; Gather-owned selection, destination, bounded read-only sync,
  fidelity, identity, provenance, and Original output; minimum requested versus
  granted scopes; no automatic escalation; no secrets, invented backend,
  `.agent-factory/tool/`, premature auth-code migration, or Tool Activity;
- the Main-owned Interview and orchestration topology, including Work-applied
  Explorer and the Main -> Work -> Verification graph, plus unspecified
  Human-owned planning/status fields and the Human-only evidenced skip intent
  that applies after current Work completion without starting another
  Verification; and Main-owned prompt direct commit publication after pass or
  evidenced skip, with exact result-only staging, no separate commit Work turn,
  no Work or Verification commit, and no inferred push, amend, force, or
  history rewrite;
- provenance for accepted decisions and repository observations;
- the ordinary consumer `<category>-<title>` pair identity contract, exactly
  one resolved AI/Human representation pair, current/local exact
  Skill/Specification directory match, external-locator allowance, plugin
  single-name exception, and no-bulk-renaming boundary;
- the Workspace-owned VS Code-shaped Activity Bar, Primary Sidebar, and main
  Workspace relationship; exactly five ordered top-level items labeled 일정,
  에이전트, 문서, 로그, 테스트; the ordered, independently collapsible
  `원본문서`, `가공문서`, `스펙문서` Document groups and their decided
  overview/table/tree shapes; exact six-column Original search order and
  behavior; exact no-space UI spelling without semantic type rename;
  unresolved overview/live source-query/sync/mutation contracts and other four
  sidebars; no aliases or inferred data behavior; the owner-mediated boundary;
  and the local
  byte-identical packaged-browser-to-materialized-common publication contract,
  including the three core browser-code files and the installed, byte-identical
  `THIRD_PARTY_NOTICES.txt` companion attribution/license asset,
  plus the packaged-to-root copy-once `workspace.sh` launcher contract;
- the distributed-plugin versus consumer-Project-Skill ownership split and the
  storage-independent document model with unresolved backend integration;
- the exact `.agent-factory/db.sqlite` local catalog path, its rebuildable and
  non-authoritative scope, Agent implementation ownership, Workspace's
  presentation-only no-operation boundary, and
  authoritative-store boundaries;
- diverse native/source-appropriate Original formats, the local-adapter
  Markdown contract for active Processed Documents, and the exclusion of
  preserved legacy Inquery material as an active target or precedent;
- the mandatory fail-closed synchronization contract for every Specification
  Human/AI pair;
- Document-owned initialization and physical migration as distinct from
  semantic work; invariant `documentType`; advisory-only, non-executable LLM
  proposals; closed versioned deterministic plan/IR; current-state and Human
  authority gates; fail-closed stale/path/conflict/provenance/type/destructive
  conditions; recoverable grouped Specification publication; unchanged
  Gather/Tool/Agent/Workspace/catalog authority; unchanged Main -> Work ->
  Verification graph; and honest documentation-first unresolved state.
