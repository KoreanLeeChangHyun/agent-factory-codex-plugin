# Specification Document

## Semantic model

Treat a Specification as one refined, trustworthy body of project knowledge
with two faithful representations:

- the Human view is local HTML, CSS, and JavaScript below
  `<project-root>/.agent-factory/specification/`;
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
<project-root>/.agent-factory/specification/
```

Use this minimum browser structure for a project-specific Specification:

```text
.agent-factory/specification/<specification-id>/
├── index.html
├── styles.css
├── app.js
└── assets/
```

Create `assets/` only when the Specification needs additional local resources.
Use actual SVG for user-facing icons. Do not use Markdown or JSON as the
canonical Human-facing Specification document.

## New-document authoring workflow

1. Resolve a stable `specification-id` from an explicit Human-provided identity
   or unambiguous, accepted project evidence. Use lowercase hyphen-case. Do not
   infer an identity from tentative language, raw notes, or an unresolved
   naming choice; return that Human-owned decision when no stable identity is
   available.
2. Confirm that
   `<project-root>/.agent-factory/specification/<specification-id>/` does not
   exist. Only for a new target, copy the complete packaged template from
   `assets/document/` into that directory. Scaffolding is copy-once: never use
   the template to overwrite, reset, or merge over an existing Specification.
3. Inspect the accepted Human decisions, relevant project evidence, and any
   refined Inquiry or Gather output. Resolve important provenance before
   drafting. Raw working notes, collection logs, and unassessed excerpts are
   inputs to refine, not trusted Specification truth to paste into the result.
4. Adapt the template to the actual body of knowledge. Remove, reorder, split,
   or extend the baseline sections when that makes the document clearer. The
   template is a flexible starting point, not a rigid schema.
5. Replace or remove every element marked `data-template-placeholder` and every
   `[[...]]` token. A document with any marked template placeholder remaining is
   scaffolding, not a refined Specification.
6. Create or update the paired
   `<project-root>/.agents/skills/<project-skill>/` representation and compare
   the two representations for semantic alignment. Decisions, requirements,
   scope, evidence, relationships, and unresolved state must agree even though
   their presentation differs.
7. Keep the Human document directly readable from its `index.html`, then hand
   testing to the Human under the applicable Agent contract.

## Knowledge and provenance rules

Write each statement in the right epistemic category:

- **Accepted decisions** record choices the Human made or explicitly accepted.
  Do not convert recommendations or implementation observations into decisions.
- **Requirements** state grounded constraints or outcomes and identify their
  source. Do not manufacture priority, acceptance, ownership, or completion.
- **Observed evidence** describes what inspection established and includes an
  inspectable source location, artifact, or Human statement. Keep inference
  distinguishable from direct observation.
- **Unresolved questions** remain visibly unresolved until the Human decides
  them. Do not silently fill gaps or phrase uncertainty as accepted state.

Use provenance near the claim it supports. Prefer durable repository-relative
paths, artifact identifiers, or a concise attribution to an explicit Human
decision. Refine Inquiry and Gather evidence before inclusion: reconcile
conflicts, assess relevance, and summarize the supported conclusion without
promoting raw collection material as truth.

## Document boundaries and quality rules

Keep shared browser-shell responsibilities in
`.agent-factory/specification/common/`. Keep each Specification's content in
its own `<specification-id>/` directory, and keep optional document-specific
local resources in `<specification-id>/assets/`. Do not copy project facts into
the common shell or place one document's private resources in `common/`.

Preserve semantic HTML, keyboard access, visible focus, readable contrast, and
responsive behavior. Use only local relative dependencies; the document must
remain readable without JavaScript, with JavaScript limited to progressive
interaction. Use actual SVG for every user-facing icon—never icon-like Unicode,
CSS shapes, icon fonts, raster images, or external icon libraries. Keep the
entry-point links as `./styles.css` and `./app.js`.

Before treating an authored document as refined, account for every placeholder,
support every factual claim with provenance, separate accepted and unresolved
state, and ensure the paired Project Skill says the same thing. These are
authoring quality rules, not permission for a Work Agent to run tests or other
verification.

## Common interface

Reuse the common shell below `.agent-factory/specification/common/`. Preserve
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
`.agent-factory/specification/` to use Markdown instead of HTML, CSS, and
JavaScript.

Read `project-skill.md` for the required location and structure of the paired
AI-facing representation.
