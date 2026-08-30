# Diagrams

Use Mermaid source as the default maintained representation for diagrams. Use
Mermaid.js only as the Human-facing SVG renderer under the dependency and
runtime boundaries in `libraries.md`.

## Diagram type routing

- Read `diagrams/erd.md` for entity, attribute, key, relationship, and
  cardinality models.
- Read `diagrams/behavior.md` for game monster, NPC, and boss behavior patterns.
- Read `diagrams/sequence.md` for time-ordered interactions among actors or
  systems.

Choose one diagram type for the relationship being explained. Split a diagram
when it mixes data structure, decision behavior, and temporal interaction so
heavily that its primary reading direction becomes unclear. A diagram is a
projection of grounded knowledge; it does not by itself establish runtime
behavior, data authority, acceptance, or implementation completion.

Every authored diagram must include a concise `accTitle` and an `accDescr` that
communicates the important relationship without relying on color or geometry.
Keep labels stable and domain-specific, and keep the source readable in version
control.

## Agent Factory core sources

These Mermaid sources are the AI-readable equivalents of the important visual
relationships rendered with semantic HTML and inline SVG in the paired Korean
browser document. Keep labels and relationships aligned when either
representation changes.

## Document types

```mermaid
flowchart LR
    accTitle: Agent Factory Document types
    accDescr: Document is the neutral umbrella for Original, Processed, and Specification Documents; the conceptual ordering shows only optional provenance relationships that may be absent or have any cardinality.
    D[Document<br/>neutral umbrella]
    O[Original Document<br/>원본문서<br/>source-faithful evidence and provenance]
    P[Processed Document<br/>가공문서<br/>analysis, comparison, hypotheses, interviews]
    S[Specification<br/>스펙 문서<br/>accepted reconciled project knowledge]
    D --> O
    D --> P
    D --> S
    O -. possible derivation or evidence .-> P
    P -. possible derivation or evidence .-> S
    O -. possible derivation or evidence .-> S
```

## Core capability topology

```mermaid
flowchart LR
    accTitle: Agent Factory core capability topology
    accDescr: Gather, Explorer, Interview, Document, Convention, Agent, and Workspace have distinct inputs, outputs, execution, and authority relationships.
    Sources[Distributed cloud sources] --> Gather
    Gather -->|synchronizes| Original[Original Documents]
    WebCodeDocs[Web, code, documents] --> Explorer
    Original --> Explorer
    Explorer -->|produces or preserves| Original
    Explorer -->|produces| Processed[Processed Documents]
    Human[Human knowledge] --> Interview
    Interview -->|produces| Processed
    Document[Document<br/>defines all three types] --> Original
    Document --> Processed
    Document --> Specification[Specifications]
    Human -->|grounded decisions| Document
    Specification --> HumanView[Korean browser document]
    Specification --> AIView[English AI-facing Skill]
    Workspace[Human control tower] -->|navigates| HumanView
    Workspace -->|manages views of| Agent
    Convention -. cross-cutting constraints .-> Gather
    Convention -. cross-cutting constraints .-> Explorer
    Convention -. cross-cutting constraints .-> Interview
    Convention -. cross-cutting constraints .-> Document
    Convention -. cross-cutting constraints .-> Workspace
    Agent -. cross-cutting execution .-> Gather
    Agent -. cross-cutting execution .-> Explorer
    Agent -. cross-cutting execution .-> Interview
    Agent -. cross-cutting execution .-> Document
    Agent -. exposes managed state to .-> Workspace
```

## Agent engineering stack

```mermaid
flowchart TB
    accTitle: Agent engineering scope stack
    accDescr: Prompt, Context, Loop, Agent Graph, and Agentic Engineering form increasingly broad scopes from one turn to the complete operating lifecycle.
    Agentic[Agentic Engineering<br/>identity, authority, safety, evaluation,<br/>observability, governance]
    Graph[Agent Graph Engineering<br/>Agents, Humans, tasks, tools, state, evidence]
    Loop[Loop Engineering<br/>iteration, feedback, convergence, stop, recovery]
    Context[Context Engineering<br/>selection, assembly, provenance, isolation]
    Prompt[Prompt Engineering<br/>per-turn instructions and output contract]
    Agentic --> Graph --> Loop --> Context --> Prompt
```

## Paired representation alignment

```mermaid
flowchart LR
    accTitle: Specification pair semantic alignment
    accDescr: One Specification semantic body has faithful Human-facing Korean browser and AI-facing English Convention Skill representations that remain aligned.
    HumanView[Human-facing projection<br/>Korean HTML, CSS, JavaScript<br/>resolved document store]
    Core[One Specification semantic body<br/>decisions, relationships,<br/>observations, unresolved questions]
    AIView[AI-facing projection<br/>English distributed Convention Skill<br/>skills/convention/]
    Core --> HumanView
    Core --> AIView
    HumanView <-. semantic alignment .-> AIView
```

## Current implementation relationships

```mermaid
flowchart LR
    accTitle: Current Agent Factory execution relationships
    accDescr: Main delegates Work, Verification returns pass or fail, and evidenced Human skip intent is applied only after current Work completes without starting another Verification.
    Explorer[Explorer<br/>accepted capability]
    ExplorerConvention[Convention reference<br/>semantic and authority boundaries]
    Legacy[Preserved legacy Inquery data<br/>document/processed/legacy-inquery]
    Work[Managed Work<br/>applies Explorer when needed]
    Explorer --> ExplorerConvention
    Explorer --> Work
    Work -. does not migrate or delete .-> Legacy
    Interview[Interview<br/>accepted capability]
    InterviewConvention[Convention reference<br/>semantic and authority boundaries]
    Main[Main<br/>Human interface, Interview,<br/>orchestration and integration]
    Verification[Managed Verification<br/>pass or fail]
    Interview --> InterviewConvention
    Interview --> Main
    Main --> Work
    Work --> SkipDecision{Current Work complete<br/>and evidenced Human skip pending?}
    Human[Human] -. records evidenced control-plane intent;<br/>not a transition or completion .-> SkipIntent[Human-only skip intent]
    SkipIntent -. evaluated only after current<br/>initial or revision Work completes .-> SkipDecision
    SkipDecision -->|no| Verification
    SkipDecision -->|yes: start no next or additional Verification| End
    Verification -->|fail| Work
    Verification -->|pass| End[END]
    Workspace[Workspace Skill<br/>Human control tower]
    Workspace --> Activities[Activity Bar top-level order<br/>1 일정 · 2 에이전트 · 3 문서 · 4 로그 · 5 테스트]
    Activities -. sidebar, source, controls,<br/>and nesting remain undecided .-> HumanDecision[Future Human decision]
```

## Project Skill naming

```mermaid
flowchart LR
    accTitle: Project Skill naming identity
    accDescr: Category and name form one Project Skill identity that exactly matches its owning directory and SKILL.md frontmatter name.
    Category[category<br/>discovery classification]
    Separator["-"]
    Name[name<br/>bounded knowledge or capability]
    SkillName[Project Skill name<br/>&lt;category&gt;-&lt;name&gt;]
    Directory[Owning-context directory<br/>exactly &lt;category&gt;-&lt;name&gt;]
    Frontmatter[SKILL.md frontmatter<br/>name: &lt;category&gt;-&lt;name&gt;]
    Category --> SkillName
    Separator --> SkillName
    Name --> SkillName
    SkillName --> Directory
    SkillName --> Frontmatter
```

This relationship applies to newly named Skill identities where the owning
context requires the two-part form. Existing accepted identities are
preserved; it does not authorize bulk renaming.

## Skill ownership

```mermaid
flowchart LR
    accTitle: Distributed and Project Skill ownership
    accDescr: The plugin owns distributed Skills under skills while separate consumer projects own Specification Project Skills directly under their own .codex skills root.
    Plugin[Agent Factory plugin repository] --> Distributed[Distributed plugin Skills<br/>&lt;plugin-root&gt;/skills/]
    Distributed --> Core[Convention owns Agent Factory core<br/>skills/convention/]
    Consumer[Separate consumer project] --> ProjectSkill[Specification Project Skill<br/>&lt;project-root&gt;/.codex/skills/&lt;category&gt;-&lt;name&gt;/]
    Distributed -. never mirrored into this repository .-> NoCodex[No repository-local .codex/skills/]
```

## Storage-independent document roles

```mermaid
flowchart LR
    accTitle: Storage-independent Document roles
    accDescr: Logical Document types and roles may use the local adapter or an explicitly resolved alternative while every adapter preserves the same authority and safety requirements.
    Roles[Logical Document types<br/>and document roles]
    Roles --> Local[Current/default local adapter<br/>.agent-factory/document/{original, processed, specification}]
    Roles --> Alternative[Explicitly resolved alternative<br/>project server, external store,<br/>mounted filesystem, configured backend]
    Requirements[Provenance, authority, isolation,<br/>alignment, accessibility, security]
    Requirements -. required for every adapter .-> Local
    Requirements -. required for every adapter .-> Alternative
    Alternative -. integration policy unresolved .-> Decisions[Configuration, identity, sync/conflicts,<br/>authentication, availability, caching]
```

## Human-facing Workspace shell and launcher

```mermaid
flowchart LR
    accTitle: Human-facing Workspace shell and launcher
    accDescr: The Activity Bar contains only 일정, 에이전트, 문서, 로그, and 테스트 in that order; Primary Sidebar details remain undecided; a non-visible read-only utility projects only the project and classified Original and Processed Document trees without defining an Activity or nesting, while temporary Explorer material remains only in its producing Agent run.
    Activity[Activity Bar<br/>1 일정 · 2 에이전트 · 3 문서 · 4 로그 · 5 테스트] --> Sidebar[Primary Sidebar<br/>details Human-owned and undecided] --> Workspace[Workspace]
    Evidence[Classified durable Original and Processed Documents<br/>.agent-factory/document/] -. read-only metadata .-> DiscoveryUtility[Non-visible read-only discovery utility<br/>.agent-factory/workspace/explorer/]
    Project[Project tree<br/>sensitive control and runtime paths omitted] -. read-only metadata .-> DiscoveryUtility
    DiscoveryUtility -. defines no Activity or nesting .-> Workspace
    Temporary[Temporary Explorer material] --> RunLocal[Producing managed Agent run only]
    Asset[skills/workspace/assets/workspace.sh] -->|local copy once| Root[&lt;project-root&gt;/workspace.sh]
    Existing[Existing root workspace.sh] -. preserved even under force .-> Root
    Remote[Server-hosted Workspace] -->|selected host or adapter| Browser[Human browser]
    Root -. not required remotely .-> Remote
```
