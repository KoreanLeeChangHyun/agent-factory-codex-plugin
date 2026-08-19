# Specification Document

## Semantic model

Treat a Specification as one refined, trustworthy body of project knowledge
with two faithful representations:

- the Human view is local HTML, CSS, and JavaScript below
  `<project-root>/.agent-factory/specifications/`;
- the AI view is a standard project-scoped Codex Skill below
  `<project-root>/.agents/skills/<project-skill>/`.

Create and maintain both representations for a Specification. Keep their
claims, decisions, relationships, and scope aligned. Do not let either view
silently add, omit, or contradict specified knowledge in the other. The
AI-facing Skill is the machine-readable working form of the Specification; an
Explorer link to a Skill, or an unrelated optional Project Skill, does not
satisfy this requirement.

Use only explicit Human instruction, accepted project decisions, or inspected
project evidence as the basis for claims. Preserve source locations or other
provenance sufficient to inspect important claims in both representations.
Represent unknown or undecided information honestly. Do not invent Human-owned
priority, deadline, owner, acceptance, risk acceptance, or completion state.

When changing either representation, inspect its counterpart and update both
as needed to preserve semantic alignment. When inspecting or verifying, report
unsupported, missing, stale, or contradictory claims without treating the
review itself as authorization to edit them.

## Output format

Create every actual Specification document as refined HTML, CSS, and
JavaScript for Human viewing in a browser. Store Specification output below:

```text
<project-root>/.agent-factory/specifications/
```

Use this minimum browser structure for a project-specific Specification:

```text
.agent-factory/specifications/<specification-id>/
├── index.html
├── styles.css
├── app.js
└── assets/
```

Create `assets/` only when the Specification needs additional local resources.
Use actual SVG for user-facing icons. Do not use Markdown or JSON as the
canonical Human-facing Specification document.

## Common interface

Reuse the common shell below `.agent-factory/specifications/common/`. Preserve
its Activity Bar, resizable Primary Sidebar with the required Explorer, and
project-specific Workspace. Use VS Code as the visual reference for layout
density and Explorer behavior.

Keep common layout, interaction, and visual tokens in the common HTML, CSS, and
JavaScript. Keep the actual Explorer entries and Workspace content specific to
the project or Specification, except for explicitly required common entries.

## Browser boundary

The Specification is the rendered browser application itself. It must remain
usable from its HTML entry point with local CSS, JavaScript, and assets. Do not
require an AI to interpret a Markdown or JSON package before a Human can view
the Specification.

Refine working material before incorporating it. Do not treat raw Inquiry
notes, a draft, a conversation transcript, or an operational log as a
Specification merely because it is rendered in the browser.

## Skill-instruction distinction

Files below `skills/specification/references/` are Markdown instructions for
the Specification Skill. They are not Specification documents. This Markdown
instruction format does not permit actual Specification output below
`.agent-factory/specifications/` to use Markdown instead of HTML, CSS, and
JavaScript.

Read `project-skill.md` for the required location and structure of the paired
AI-facing representation.
