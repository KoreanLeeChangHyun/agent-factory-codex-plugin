# Agent Factory Core Model

## Authority and identity

The Human-established Specification identity is `agent-factory-core`, based on
“Agent-Factory 코어 개념들.” Its paired AI-facing owner is now the distributed
`convention` Skill. The
canonical refined body has two faithful projections:

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
observations are separately attributed. The Human decision to implement
Interview as a distributed Skill comes from
`.agent-factory/agent/interview-skill-work-request.md`. The engineering synthesis at
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

The superseding Human decisions that this repository owns plugin Skills only
below `skills/`, has no `.codex/skills/` store, and treats document storage as
adapter-resolved rather than intrinsically `.agent-factory/` come from
`.agent-factory/agent/project-skill-naming-work-20260828/runs/run-20260827T184536518402Z-9b6f2283/request.md`.

The final consolidation decision—keep six public Skills, make Convention the
AI-facing owner of Agent Factory core, use the three-stage local information
tree, migrate Human refined and legacy processed documents, and retain
storage-backend independence—comes from
`.agent-factory/agent/project-skill-naming-work-20260828/runs/run-20260827T185448822401Z-ef49909a/request.md`.

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
identities: this rule does not authorize bulk renaming. The distributed
accepted distributed Skill identities remain unchanged. The durable Agent
Factory core rules are consolidated into `skills/convention/`. Separate
consumer projects may use the rule for
their refined Project Skills at
`<project-root>/.codex/skills/<category>-<name>/`; this plugin repository has no
repository-local `.codex/skills/` store.

## Storage-independent document roles

Information classes and document roles are logical concepts independent of
physical storage. `.agent-factory/` is the current/default local work and
document adapter, not a universal canonical location. An explicitly resolved
alternative may be a project server, external document store, mounted
filesystem, or another configured backend.

Changing the adapter does not weaken lifecycle stage, provenance, authority,
isolation, semantic alignment, accessibility, or security requirements. Never
silently mirror, migrate, or select a canonical backend. Backend
configuration, identity, synchronization and conflict policy, authentication,
availability, and caching remain unresolved Human or implementation decisions.
Current local scripts and runtime paths are observed local implementations;
they do not prove remote or server adapters exist.

## Human-facing Specification shell and launcher

Human-facing Specifications use a developer-familiar VS Code-shaped shell
whose primary spatial relationship is `Activity Bar -> Primary Sidebar ->
Workspace`. The reusable shell is packaged below
`skills/specification/assets/browser/` and installed in the project at
`.agent-factory/specification/common/`.

For the local adapter, the reusable launcher source is
`skills/specification/assets/spec.sh`; its
project-installed copy is the ordinary file `<project-root>/spec.sh`. The
installation contract is copy-once: initialization preserves an existing root
launcher, including when force is requested. The accepted shell and launcher
decision comes from
`.agent-factory/agent/project-skill-naming-work-20260828/runs/run-20260827T183901489117Z-e71747f6/request.md`.
A server-hosted Specification is exposed by its selected host or adapter and is
not required to use `spec.sh` remotely.

## Information lifecycle

The lifecycle is:

`original information -> processed information -> refined information`

### Original information

Source-faithful evidence with inspectable provenance. Fidelity to the source,
source identity, and collection context must be retained. Original does not
mean inferior or untrusted; it identifies evidence before project-level
transformation and acceptance.

### Processed information

Transformations that are not yet accepted as trusted refined project truth.
This includes analysis, comparison, hypotheses, research results, interview
results, and other derived material. Processed information can be useful and
well-supported without having Specification authority.

### Refined information

Accepted and reconciled project knowledge managed by Specification. Refinement
resolves relevant conflicts, preserves important provenance, and records
accepted decisions, requirements, relationships, and honest unresolved state.

## Core capability topology

### Gather

Gather collects all project-needed information scattered across Google Drive,
OneDrive, Slack, Notion, Discord, and similar cloud sources. It preserves that
material as original information, including source fidelity, identity, and
provenance. It does not reconcile evidence or promote it to refined truth.

### Explorer

Explorer explores all project-needed information by analyzing and researching
the web, code, and documents. It may consume original or processed information
and may produce original or processed information. It does not independently
accept refined project truth.

### Interview

Interview reduces the information gap between AI and Humans through interviews
and produces processed information. Its distributed Skill is Human-facing and
conducted adaptively by the Main Agent in the current conversation; it does not
independently promote results to refined project truth. Main may pause or
sequence the Interview while a managed Explorer gathers necessary background,
then resume the Human conversation while keeping Human statements, Explorer
evidence, and Main interpretation distinct. Explorer never interviews or
impersonates the Human.

### Specification

Specification consumes original and processed inputs together with accepted
Human decisions. It reconciles them into one semantic body of refined
information and manages two faithful projections: a Human-facing browser
document in the Human's convenient language, currently Korean, and an
AI-facing English Skill. Visual diagrams, graphs, flows, and tables are
preferred in the Human projection when they improve understanding.

### Convention

Convention records constraints AI must follow while working and acts as a weak
harness. It is a cross-cutting control layer across the entire information
lifecycle rather than another information stage.

### Agent

Agent is the AI Agent execution domain. It spans the lifecycle and incorporates
Prompt Engineering, Context Engineering, Loop Engineering, Agent Graph
Engineering, and Agentic Engineering. It is an execution layer, not a fourth
information stage. Main owns Human interaction, Interview, orchestration, and
integration but no executable task work. Managed Explorer performs research,
Work implements, Review independently reviews, and Verification runs only
explicitly Human-authorized checks. Recovery is likewise delegated to an
appropriate bounded managed role.

## Responsibility matrix

| Capability | Principal inputs | Produces or manages | Boundary |
| --- | --- | --- | --- |
| Gather | Distributed cloud sources | Original | Preserve fidelity and provenance; do not refine |
| Explorer | Web, code, documents, original/processed material | Original and processed | Explore, analyze, and research; do not accept refined truth |
| Interview | Human knowledge and questions | Processed | Reduce the AI-Human information gap through an adaptive Main-Agent conversation; do not independently refine |
| Specification | Original, processed, and accepted Human decisions | Refined | Reconcile and manage the paired projections |
| Convention | Human-defined working constraints | Cross-cutting control | Weak harness across all stages |
| Agent | Role, authority, context, tools, state | Cross-cutting execution | Main interfaces and orchestrates; managed roles execute research, Work, Review, authorized Verification, and recovery |

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

- `.codex-plugin/plugin.json` describes six focused Agent Factory Skills and
  the present plugin interface covers Gather, Explorer, Interview, Convention,
  Agent, and Specification. Convention owns the consolidated core. This is current
  plugin-surface evidence, not a
  decision that those Skills replace the accepted core capability topology.
- `skills/explorer/SKILL.md` implements Explorer as a provenance-preserving
  temporary workspace and resumable managed Explorer Agent contract. It may
  preserve original information and produce processed information, but cannot
  accept refined project truth.
- `skills/interview/SKILL.md` implements Interview as a distributed,
  Human-facing Skill that conducts an adaptive interview in the current Main
  Agent conversation and produces processed information by default. Main can
  sequence a managed Explorer between Interview questions without letting
  Explorer impersonate the Human.
- `skills/gather/SKILL.md` already establishes source-faithful gathering;
  `skills/specification/SKILL.md` establishes paired Human/AI refined
  representations; and `skills/agent/SKILL.md` establishes managed Agent
  execution and role boundaries. These are present implementation foundations,
  not proof that the entire accepted core topology is complete.

## Unresolved architecture decisions

1. Roadmap priority, deadline, owner, acceptance status, risk acceptance, and
   completion state remain Human-owned and unspecified.

## Representation-alignment checklist

When changing either projection, compare both and preserve:

- all three information stages and their authority boundaries;
- all six capabilities and their inputs, outputs, and cross-cutting roles;
- all five Agent engineering layers and their scopes;
- current six-Skill metadata and implemented Explorer and Interview Skills as
  observations rather than target-topology or completion claims;
- the Main-owned Interview and orchestration topology, including Explorer
  sequencing and separate managed Verification, plus unspecified Human-owned
  planning/status fields;
- provenance for accepted decisions and repository observations;
- the `<category>-<name>` identity contract, its owning-context scope, exact
  directory/frontmatter match, and no-bulk-renaming boundary;
- the VS Code-shaped Activity Bar, Primary Sidebar, and Workspace relationship,
  plus the local packaged-to-root copy-once `spec.sh` launcher contract;
- the distributed-plugin versus consumer-Project-Skill ownership split and the
  storage-independent document model with unresolved backend integration.
