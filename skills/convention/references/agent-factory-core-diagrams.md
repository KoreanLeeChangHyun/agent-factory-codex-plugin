# Agent Factory Core Diagrams

These Mermaid sources are the AI-readable equivalents of the important visual
relationships rendered with semantic HTML and inline SVG in the paired Korean
browser document. Keep labels and relationships aligned when either
representation changes.

## Information lifecycle

```mermaid
flowchart LR
    O[Original information<br/>source-faithful evidence and provenance]
    P[Processed information<br/>analysis, comparison, hypotheses, interviews]
    R[Refined information<br/>accepted reconciled project knowledge]
    O --> P --> R
```

## Core capability topology

```mermaid
flowchart LR
    Sources[Distributed cloud sources] --> Gather
    Gather -->|produces| Original[Original information]
    WebCodeDocs[Web, code, documents] --> Explorer
    Original --> Explorer
    Explorer -->|produces or preserves| Original
    Explorer -->|produces| Processed[Processed information]
    Human[Human knowledge] --> Interview
    Interview -->|produces| Processed
    Original --> Specification
    Processed --> Specification
    Human -->|accepted decisions| Specification
    Specification -->|manages| Refined[Refined semantic body]
    Refined --> HumanView[Korean browser document]
    Refined --> AIView[English AI-facing Skill]
    Convention -. cross-cutting constraints .-> Gather
    Convention -. cross-cutting constraints .-> Explorer
    Convention -. cross-cutting constraints .-> Interview
    Convention -. cross-cutting constraints .-> Specification
    Agent -. cross-cutting execution .-> Gather
    Agent -. cross-cutting execution .-> Explorer
    Agent -. cross-cutting execution .-> Interview
    Agent -. cross-cutting execution .-> Specification
```

## Agent engineering stack

```mermaid
flowchart TB
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
    HumanView[Human-facing projection<br/>Korean HTML, CSS, JavaScript<br/>resolved document store]
    Core[One refined semantic body<br/>decisions, relationships,<br/>observations, unresolved questions]
    AIView[AI-facing projection<br/>English distributed Convention Skill<br/>skills/convention/]
    Core --> HumanView
    Core --> AIView
    HumanView <-. semantic alignment .-> AIView
```

## Current implementation relationships

```mermaid
flowchart LR
    Explorer[Explorer<br/>accepted concept]
    ExplorerSkill[Distributed Explorer Skill<br/>observed managed implementation]
    Legacy[Preserved legacy Inquery data<br/>information/processed/legacy-inquery]
    Explorer --> ExplorerSkill
    ExplorerSkill -. does not migrate or delete .-> Legacy
    Interview[Interview<br/>accepted concept]
    InterviewSkill[Distributed Interview Skill<br/>observed implementation]
    Main[Main<br/>Human interface, Interview,<br/>orchestration and integration]
    ExplorerRole[Managed Explorer<br/>background evidence]
    Verification[Managed Verification<br/>Human-authorized checks]
    Interview --> InterviewSkill
    Main --> InterviewSkill
    Main -->|pause or sequence| ExplorerRole
    ExplorerRole -->|evidence, never Human impersonation| Main
    Main -->|exact Human authorization| Verification
```

## Project Skill naming

```mermaid
flowchart LR
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
    Plugin[Agent Factory plugin repository] --> Distributed[Distributed plugin Skills<br/>&lt;plugin-root&gt;/skills/]
    Distributed --> Core[Convention owns Agent Factory core<br/>skills/convention/]
    Consumer[Separate consumer project] --> ProjectSkill[Refined Project Skill<br/>&lt;project-root&gt;/.codex/skills/&lt;category&gt;-&lt;name&gt;/]
    Distributed -. never mirrored into this repository .-> NoCodex[No repository-local .codex/skills/]
```

## Storage-independent document roles

```mermaid
flowchart LR
    Roles[Logical information classes<br/>and document roles]
    Roles --> Local[Current/default local adapter<br/>.agent-factory/information/{original, processed, refined}]
    Roles --> Alternative[Explicitly resolved alternative<br/>project server, external store,<br/>mounted filesystem, configured backend]
    Requirements[Provenance, authority, isolation,<br/>alignment, accessibility, security]
    Requirements -. required for every adapter .-> Local
    Requirements -. required for every adapter .-> Alternative
    Alternative -. integration policy unresolved .-> Decisions[Configuration, identity, sync/conflicts,<br/>authentication, availability, caching]
```

## Human-facing Specification shell and launcher

```mermaid
flowchart LR
    Activity[Activity Bar] --> Sidebar[Primary Sidebar] --> Workspace[Workspace]
    Asset[skills/specification/assets/spec.sh] -->|local copy once| Root[&lt;project-root&gt;/spec.sh]
    Existing[Existing root spec.sh] -. preserved even under force .-> Root
    Remote[Server-hosted Specification] -->|selected host or adapter| Browser[Human browser]
    Root -. not required remotely .-> Remote
```
