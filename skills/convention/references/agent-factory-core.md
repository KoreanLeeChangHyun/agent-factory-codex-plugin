# Agent Factory Core Model

## Authority and identity

The Human-established Specification identity is `agent-factory-core`, based on
“Agent-Factory 코어 개념들.” Its paired AI-facing owner is now the distributed
`convention` Skill. The
canonical Specification body has two faithful projections:

- Human-facing Korean HTML, CSS, and JavaScript in the current local adapter:
  `.agent-factory/information/refined/human/agent-factory-core/`
- AI-facing English distributed plugin Skill: `skills/convention/`

These projections may use different presentation forms, but they must contain
the same decisions, relationships, current implementation observations, and
unresolved questions. Neither projection may privately add or omit specified
knowledge.

The accepted decisions and required semantic model below come from the Human's
delegated core Specification request at
`.agent-factory/agent/agent-factory-core-spec-work-request.md`. Repository
observations are separately attributed. The earlier Human decision to implement
Interview as a distributed Skill came from
`.agent-factory/agent/interview-skill-work-request.md` and is superseded by the
four-public-Skill decision below. The engineering synthesis at
`.agent-factory/information/processed/legacy-inquery/agent-factory-engineering-synthesis-20260828/synthesis.md`
is supporting, non-canonical evidence only.

The Human decision to retire the distributed `inquery` Skill and managed
Inquiry role, assign evidence exploration to Explorer, and retain adaptive
Human-facing elicitation in Interview comes from
`.agent-factory/agent/inquery-retirement-split-work/runs/run-20260827T180810962479Z-6077b043/request.md`.
Legacy Inquery contents are preserved as processed historical project data at
`.agent-factory/information/processed/legacy-inquery/`.

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

The superseding Human decision keeps Explorer and Interview as distinct core
capabilities but removes their independent public Skill entry points. Agent
assigned Explorer execution and Main Interview conduct to Agent while
Convention owned their durable semantics and information/authority boundaries.
The plugin then
had four public distributed Skills: `gather`, `convention`, `agent`, and
`specification`. This decision comes from the current Human conversation and
is recorded in
`.agent-factory/agent/explorer-interview-skill-consolidation-work-request.md`.

The earlier Workspace decision introduced `workspace` as the Human control tower for
managing Agents, documents, and the project. The browser shell, navigation,
local serving, and root launcher move from Specification to Workspace;
the Skill then named Specification retained document definition and paired
semantic representations. The plugin then had five public distributed Skills:
`gather`, `convention`, `agent`, `specification`, and `workspace`. This decision
is recorded in `.agent-factory/agent/workspace-skill-work-request.md`.

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

## Human-facing Workspace shell and launcher

Workspace uses a developer-familiar VS Code-shaped Human control-tower shell
whose primary spatial relationship is `Activity Bar -> Primary Sidebar ->
Workspace`. The reusable shell is packaged below
`skills/workspace/assets/browser/` and installed in the project at
`.agent-factory/workspace/common/`.

For the local adapter, the reusable launcher source is
`skills/workspace/assets/workspace.sh`; its
project-installed copy is the ordinary file `<project-root>/workspace.sh`. The
installation contract is copy-once: initialization preserves an existing root
launcher, including when force is requested. The accepted shell and launcher
decision is superseded and relocated by
`.agent-factory/agent/workspace-skill-work-request.md`. A server-hosted Workspace
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
`information/processed/legacy-inquery/` is not an active target or format
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

Workspace is the Human-facing control tower for navigating and managing Agents,
documents, and project views. It projects existing state without becoming the
canonical owner of Agent runtime records, gathered sources, Explorer evidence,
Specifications, or Project Skills. It is a cross-cutting Human management
surface rather than another Document type. In the local adapter,
`.agent-factory/explorer/` is temporary Work/Explorer evidence storage, while
`.agent-factory/workspace/explorer/` is the read-only Workspace File/Project
Explorer Activity projection. The projection discovers the project and
temporary evidence trees without copying, editing, moving, deleting, or
assuming ownership of either.

## Responsibility matrix

| Capability | Principal inputs | Produces or manages | Boundary |
| --- | --- | --- | --- |
| Gather | Distributed cloud sources | Original Documents | Synchronize external Documents while preserving fidelity and provenance; do not define other types |
| Explorer | Web, code, Documents, Original/Processed material | Original and Processed Documents | Explore, analyze, and research; do not accept or reconcile Specification truth |
| Interview | Human knowledge and questions | Processed Documents | Reduce the AI-Human information gap through an adaptive Main-Agent conversation; do not independently create Specification truth |
| Document | Documents and grounded Human decisions | Original, Processed, and Specification Documents | Define all three types, preserve optional provenance relationships, and pair every Specification |
| Convention | Human-defined working constraints | Cross-cutting control | Weak harness across all Document types |
| Agent | Role, authority, context, tools, state | Cross-cutting execution | Main orchestrates, Work performs bounded tasks, and Verification independently checks unless the Human skips it |
| Workspace | Agents, documents, project views | Human control tower | Present and manage owned state without replacing its authority or storage |

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
  `.agent-factory/workspace/`. Its Explorer Activity keeps the project-tree
  projection separate from temporary Work/Explorer evidence stored below
  `.agent-factory/explorer/`.

## Unresolved architecture decisions

1. Roadmap priority, deadline, owner, acceptance status, risk acceptance, and
   completion state remain Human-owned and unspecified.

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
  Workspace relationship, plus the local packaged-to-root copy-once
  `workspace.sh` launcher contract;
- the distributed-plugin versus consumer-Project-Skill ownership split and the
  storage-independent document model with unresolved backend integration;
- diverse native/source-appropriate Original formats, the local-adapter
  Markdown contract for active Processed Documents, and the exclusion of
  preserved legacy Inquery material as an active target or precedent;
- the mandatory fail-closed synchronization contract for every Specification
  Human/AI pair.
