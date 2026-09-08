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

These Mermaid sources explain Agent Factory relationships. Use diagrams when they clarify a relationship. Keep any rendered diagram faithful to its own source and provide accessible fallback meaning.

## Document types

```mermaid
flowchart LR
    accTitle: Agent Factory Document types
    accDescr: Document is the neutral umbrella for Original, Processed, and Specification Documents; the conceptual ordering shows only optional provenance relationships that may be absent or have any cardinality.
    D[Document<br/>neutral umbrella]
    O[Original Document<br/>원본 문서<br/>source-faithful evidence and provenance]
    P[Processed Document<br/>가공 문서<br/>analysis, comparison, hypotheses, interviews]
    S[Specification<br/>명세 문서<br/>accepted reconciled project knowledge]
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
    accDescr: Gather, Tool, Explorer, Interview, Document, Convention, Agent, and Workspace have distinct inputs, outputs, execution, lifecycle, and authority relationships.
    Sources[Distributed cloud sources] --> Gather
    Authorities[Host, plugin, MCP,<br/>project manifest] --> Tool[Tool lifecycle control]
    Gather -->|declares capability, minimum scope,<br/>approval need, selection bounds| Tool
    Tool -->|connection readiness,<br/>actually granted scope| Gather
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
    Specification -. optional reference .-> HumanView[Human reference document]
    Specification -. informs .-> AIView[AI-facing Skill]
    Workspace[Human control tower] -->|navigates| HumanView
    Workspace -->|manages views of| Agent
    Convention -. cross-cutting constraints .-> Gather
    Convention -. cross-cutting constraints .-> Tool
    Convention -. cross-cutting constraints .-> Explorer
    Convention -. cross-cutting constraints .-> Interview
    Convention -. cross-cutting constraints .-> Document
    Convention -. cross-cutting constraints .-> Workspace
    Agent -. cross-cutting execution .-> Gather
    Tool -. capability readiness,<br/>not execution authority .-> Agent
    Agent -. cross-cutting execution .-> Explorer
    Agent -. cross-cutting execution .-> Interview
    Agent -. cross-cutting execution .-> Document
    Agent -. exposes managed state to .-> Workspace
    Tool -. creates no Activity .-> Workspace
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

## Skill and reference documents

```mermaid
flowchart LR
    accTitle: Independent Skill and reference maintenance
    accDescr: Accepted project knowledge informs AI instructions and optional Human references; each is maintained for its reader.
    Knowledge[Accepted project knowledge]
    AI[AI Skill instructions<br/>skills/skill-id/]
    Human[Optional Korean reference<br/>docs/specifications/skill-id/]
    Knowledge -->|Agent instructions| AI
    Knowledge -. reader-focused explanation .-> Human
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
    Workspace[MCP Workspace domain<br/>Human control tower]
    Workspace --> Activities[Activity Bar top-level order<br/>1 일정 · 2 에이전트 · 3 문서 · 4 외부연동 · 5 로그 · 6 테스트]
    Activities --> DocumentSidebar[문서 Sidebar<br/>원본 문서 · 가공 문서 · 명세 문서]
    DocumentSidebar -. finer view details and source integration unresolved .-> HumanDecision[Future Human decision]
    Activities -. Agents, logs and tests details unresolved .-> HumanDecision
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
    Distributed --> Core[One distributed Skill<br/>skills/skill-id/]
    Plugin -. optional independent reference .-> HumanReference[Korean reference documents<br/>docs/specifications/skill-id/]
    Consumer[Separate consumer project] --> ProjectSkill[Specification Project Skill<br/>&lt;project-root&gt;/.codex/skills/&lt;category&gt;-&lt;name&gt;/]
    Distributed -. never mirrored into this repository .-> NoCodex[No repository-local .codex/skills/]
```

## Storage-independent document roles

```mermaid
flowchart LR
    accTitle: Cloud Document authority and source packages
    accDescr: Cloud owns accepted published revisions; Git owns Skill authoring and local run data remains operational evidence.
    Git[Git Skill and optional reference authoring] --> Snapshot[Authorized publication content]
    Snapshot --> Cloud[Authenticated cloud Document publication]
    Cloud --> Revision[Accepted immutable revision]
    Cloud --> Types[Original, Processed, Specification: invariant types]
    Local[Local Agent run and outbox] -->|authorized required evidence upload| Cloud
    Legacy[Preserved legacy source data] -->|inventory, backup, verified import| Cloud
    Legacy -. no deletion authority from code retirement .-> Human[Human decision]
```

## Human-facing cloud Workspace

```mermaid
flowchart LR
    accTitle: Cloud Workspace projection and local execution authority
    accDescr: Six Activities project cloud domain state; local exec and loop own execution while cloud reporting never dispatches or completes it.
    Activity[Activity Bar: 일정, 에이전트, 문서, 외부연동, 로그, 테스트] --> Sidebar[Primary Sidebar] --> View[Workspace area]
    Documents[Authenticated cloud Document revisions] -->|isolated Human preview| View
    Integrations[Cloud connection and collection state] -->|owner-backed facts| View
    Planning[Cloud planning tasks: separate from background jobs] --> View
    Exec[Local exec.py process, session, run] --> Reports[Cloud shared reporting]
    Loop[Local loop.py transitions and END] -. retains sole graph authority .-> Exec
    Reports -->|projection, never execution control| View
    Runtime[Separate MCP application] -->|canonical shell; no project copy| View
    Unresolved[Human-owned undecided controls] -. remain unresolved .-> Sidebar
```
