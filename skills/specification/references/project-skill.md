# Project Skill Structure

## Project boundary

A Project Skill belongs to one project. It is the refined, AI-readable working
form of the specified project knowledge it contains. When it represents a
Specification, pair it with that Human-readable HTML, CSS, and JavaScript
document and keep the two representations semantically aligned. The
Specification's Korean-language requirement does not require the Project Skill
or its Markdown references to be Korean.

Store repository-scoped Project Skills under the owning project's Agent Factory
Project Skill location:

```text
<project-root>/.codex/skills/<project-skill>/
```

Use this project-local `.codex/skills/` convention consistently. Do not split or
mirror Project Skills into alternate repository locations. Do not create a
physical `project/` category directory between `.codex/skills/` and the Skill.
The Explorer may present a virtual `프로젝트 스킬` category, but the category
does not exist as a Skill or filesystem directory.

Each Project Skill follows the standard Skill structure:

```text
.codex/skills/<project-skill>/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
├── scripts/
└── assets/
```

Only `SKILL.md` is universally required. Include `agents/openai.yaml` when the
Skill needs UI metadata. Create `references/`, `scripts/`, and `assets/` only
when that individual Project Skill needs them. Do not create empty optional
directories.

Name a Project Skill in the explicit lowercase hyphen-case form
`<category>-<skill-title>`. Name its directory exactly after the `name` declared
in its `SKILL.md` frontmatter, so the directory name and frontmatter `name`
match exactly.

For a new paired representation, use both the category and skill title supplied
by the Human or established unambiguously by accepted project evidence. Do not
invent either component. Preserve an existing pairing. When the category or
skill title is ambiguous, return that unresolved identity choice to the Human
instead of creating a competing or guessed pairing.

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
paired, the AI-facing representation of a Specification. Keep its files
physically separate from:

- unrefined Markdown Inquiry working material below
  `.agent-factory/inquiries/`;
- the corresponding refined Human-facing HTML, CSS, and JavaScript view below
  `.agent-factory/specification/`;
- operational Agent session state below `.agent-factory/agent/`.

Do not automatically promote an Inquiry document into a Project Skill. Create
or update a Project Skill only for its owning project and refined content
boundary.

Physical separation does not permit semantic divergence between paired views.
When either paired representation changes, inspect the other and make the
smallest corresponding update needed to keep their specified knowledge
aligned.

## Explorer projection

Show discovered Project Skills in the Human-facing Specification Explorer under
a virtual category. Mirror each actual Skill's existing filesystem hierarchy:

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
rows collapsible and use actual SVG elements for every Explorer icon. Explorer
paths must resolve to files below the owning project's `.codex/skills/`; do
not copy Project Skill content into the Specification.

The Explorer projection is navigation, not the AI representation itself. A
Specification is incomplete without the actual paired Project Skill even when
the Explorer can link to some other Skill.

The Explorer and every other Human-facing Specification view must be rendered
as HTML, CSS, and JavaScript below `.agent-factory/specification/`. This
Markdown file defines Skill guidance only; it is not a Specification output.
