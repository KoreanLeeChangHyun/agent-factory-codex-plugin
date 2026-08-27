# Project Skill Structure

## Project boundary

A Project Skill belongs to one project. It is the refined, AI-readable working
form of the specified project knowledge it contains. When it represents a
Specification, pair it with that Human-readable HTML, CSS, and JavaScript
document and keep the two representations semantically aligned. The
Specification's Korean-language requirement does not require the Project Skill
or its Markdown references to be Korean.

This plugin repository's `agent-factory-core` Human document is not paired with
a repository-local Project Skill: its AI-facing owner is the distributed
`<plugin-root>/skills/convention/` Skill. A separate consumer project uses
the Project Skill structure defined here.

Keep the plugin's distributed Skills and consumer-project Project Skills in
different locations:

- In the Agent Factory plugin repository itself, store the plugin's distributed
  Skills below `<plugin-root>/skills/`.
- In every separate project that uses the Agent Factory plugin, store that
  project's Project Skills below:

```text
<project-root>/.codex/skills/<project-skill>/
```

Do not create or mirror the Agent Factory plugin repository's own distributed
Skills below its `.codex/`. Use the consumer project's local `.codex/skills/`
convention consistently for Project Skills. Do not split or mirror Project
Skills into alternate repository locations. Do not create a physical `project/`
category directory between `.codex/skills/` and the Skill. The `skills/`
Activity may present a virtual `프로젝트 스킬` category, but the category does
not exist as a Skill or filesystem directory.

Each Project Skill follows the standard Skill structure:

```text
.codex/skills/<project-skill>/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── assets/
├── references/
│   └── *.md
└── scripts/
```

A Project Skill is one self-contained directory. Do not distribute one Project
Skill's files across multiple Skill directories. Use each location only for its
declared role:

- `SKILL.md` is the AI-readable entry point and instruction document.
- `agents/` contains Agent configuration as YAML files. Use `openai.yaml` for
  OpenAI-facing Skill metadata and dependencies.
- `assets/` contains reference material the Agent may inspect or reuse, such as
  source files, templates, samples, images, or data.
- `references/` contains the Project Skill's supporting AI-readable documents
  as Markdown files. Use the `.md` extension for every reference document.
- `scripts/` contains scripts the Agent may execute or reuse while applying the
  Project Skill.

Create an owned subdirectory when the Project Skill has content for that role.
Do not create empty optional directories, put Markdown reference documents in
`assets/`, or use `agents/` for non-YAML files.

Name a Project Skill in the canonical form `<category>-<name>`. Both `category`
and `name` use lowercase hyphen-case tokens; either component may contain
hyphens when it has multiple words. The complete Project Skill name uses only
lowercase letters, digits, and hyphens and remains under the Codex Skill name
limit. `category` classifies the Skill for discovery, while `name` identifies
the bounded project knowledge or capability within that category.

Use the complete `<category>-<name>` value unchanged for both the directory
name and the `name` field in `SKILL.md` frontmatter. These values must match
exactly.

For a new paired representation, use both the category and name supplied
by the Human or established unambiguously by accepted project evidence. Do not
invent either component. Preserve an existing pairing. When the category or
name is ambiguous, return that unresolved identity choice to the Human
instead of creating a competing or guessed pairing.

Preserve accepted Skill identities; this rule does not authorize bulk
renaming. `agent-factory-core` remains the Human document and Specification
identity, while its AI-facing distributed owner is `skills/convention/`; no
standalone `agent-factory-core` Skill remains. For newly named Skill
identities, apply `<category>-<name>` when the owning context requires the
two-part form; do not use this Project Skill reference to rename accepted
distributed Skills.

## Project information capabilities

A Project Skill may maintain these refined AI-readable references when its
project needs them:

- `references/diagrams.md` for source-backed text diagram definitions;
- `references/roadmap.md` for Human-directed work outcomes, ordering, and
  status;
- `references/issues.md` for traceable work problems and their evidence.

Use Markdown for Project Skill references. Prefer Mermaid fenced blocks for
diagrams so their source remains readable and versionable. Keep every diagram
relationship, roadmap priority, roadmap state, issue severity, and issue
disposition grounded in explicit Human instruction or inspected project
evidence.

AI may draft and maintain these files, but must not invent Human-owned priority,
deadline, owner, acceptance, issue closure, or risk acceptance. Review approval
does not itself mark roadmap work completed or close an issue.

Ground every other material claim in explicit Human instruction, accepted
project decisions, or inspected project evidence. Preserve source paths or
other provenance sufficient to inspect important claims. When the Project
Skill is a Specification view, reflect its claims, decisions, relationships,
and scope faithfully in the paired browser representation; do not make these
reference files a private source of contradictory or additional specified
facts.

## Storage boundary

A Project Skill is a refined Skill document for its owning project and, when
paired, the AI-facing representation of a Specification. Information and
document roles are logical and independent of physical storage. Under the
current/default local adapter, keep its files physically separate from:

- original or processed Explorer working material below
  `.agent-factory/explorer/`;
- the corresponding refined Human-facing HTML, CSS, and JavaScript view below
  `.agent-factory/information/refined/human/<specification-id>/`;
- operational Agent session state below `.agent-factory/agent/`.

An explicitly resolved alternative document store may be a project server,
external store, mounted filesystem, or another configured backend. Do not
silently choose, mirror, or migrate a backend, and do not weaken lifecycle
stage, provenance, authority, isolation, semantic alignment, accessibility, or
security. Backend configuration, identity, synchronization/conflict policy,
authentication, availability, and caching remain unresolved until decided.

Do not automatically promote an Explorer document into a Project Skill. Create
or update a Project Skill only for its owning project and refined content
boundary.

Physical separation does not permit semantic divergence between paired views.
When either paired representation changes, inspect the other and make the
smallest corresponding update needed to keep their specified knowledge
aligned.

## Skills Activity projection

Show discovered Project Skills in the Human-facing `skills/` Activity under a
virtual category. Mirror each actual Skill's existing filesystem hierarchy:

```text
프로젝트 스킬
└── <project-skill>
    ├── SKILL.md
    ├── agents
    │   └── openai.yaml
    └── references
        ├── diagrams.md
        ├── roadmap.md
        └── issues.md
```

Display only Project Skills and resources that actually exist. Do not hardcode
a Project Skill into the common Specification shell. Keep category and folder
rows collapsible and use actual SVG elements for every tree icon. Skills
Activity paths must resolve to files below the owning project's
`.codex/skills/`; do not copy Project Skill content into the Specification.

The Skills Activity projection is navigation, not the AI representation itself. A
Specification is incomplete without the actual paired Project Skill even when
the Skills Activity can link to some other Skill.

Every Human-facing refined Specification document must be rendered as HTML,
CSS, and JavaScript in its resolved document store. For the local adapter that
store is `.agent-factory/information/refined/human/`; shared UI remains below
`.agent-factory/specification/`. This Markdown file defines Skill guidance
only; it is not a Specification output.
