# Specification Document

## Semantic model

Treat a Specification (스펙 문서) as accepted and reconciled project knowledge:
one trustworthy semantic body with two faithful representations whose document
store is explicitly resolved. Preserve important provenance and record honest
unresolved state without weakening the accepted decisions and requirements.

Every Specification must have its resolved paired Skill. Do not create
or keep a standalone Human-facing Specification without that pair. Create and
maintain both representations for a Specification. Keep their
claims, decisions, relationships, and scope aligned. Do not let either view
silently add, omit, or contradict specified knowledge in the other. The
AI-facing Skill is the machine-readable working form of the Specification; a
Skills Activity link, or an unrelated optional Project Skill, does not
satisfy this requirement.

Semantic synchronization is a mandatory, fail-closed completion condition.
Every change to either representation must include the faithful corresponding
change to the other representation. A one-sided change is incomplete and
unacceptable. If both representations cannot be synchronized, do not report
the change or run as completed.

Use only explicit Human instruction, accepted project decisions, or inspected
project evidence as the basis for claims. Preserve source locations or other
provenance sufficient to inspect important claims in both representations.
Represent unknown or undecided information honestly. Do not invent Human-owned
priority, deadline, owner, acceptance, risk acceptance, or completion state.

When changing either representation, inspect its counterpart and update both
as needed to preserve semantic alignment. When inspecting or verifying, report
unsupported, missing, stale, or contradictory claims without treating the
review itself as authorization to edit them.

## AI-facing representation

### Ownership boundary

The Agent Factory core is the exception within this plugin repository: its
AI-facing owner is the distributed `<plugin-root>/skills/convention/` Skill,
paired with the `agent-factory-core` Human document. Do not create a standalone
`agent-factory-core` Skill or mirror the plugin's distributed Skills below this
repository's `.codex/`.

A separate consumer project may use a project-scoped Project Skill as a
Specification's AI-facing representation. Keep it directly below the owning
project's Skill root:

```text
<project-root>/.codex/skills/<category>-<name>/
```

Do not split or mirror a Project Skill into alternate locations or create a
physical `project/` category directory. A Workspace Activity may display a
virtual `프로젝트 스킬` category, but that presentation is not a Skill or
filesystem directory.

### Project Skill structure

Each Project Skill is one self-contained directory:

```text
.codex/skills/<category>-<name>/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── assets/
├── references/
│   └── *.md
└── scripts/
```

- `SKILL.md` is the AI-readable entry point and instruction document.
- `agents/` contains Agent configuration as YAML files; use `openai.yaml` for
  OpenAI-facing metadata and dependencies.
- `assets/` contains reference material the Agent may inspect or reuse, such as
  source files, templates, samples, images, or data.
- `references/` contains the Project Skill's supporting AI-readable documents
  as Markdown files; use the `.md` extension.
- `scripts/` contains scripts the Agent may execute or reuse while applying the
  Project Skill.

Create an owned subdirectory only when the Project Skill has content for that
role. Do not create empty optional directories, put Markdown references in
`assets/`, or use `agents/` for non-YAML files.

### Project Skill identity

Name a Project Skill in the canonical form `<category>-<name>`. Both components
use lowercase hyphen-case tokens; a component may itself contain hyphens. The
complete name uses only lowercase letters, digits, and hyphens, remains under
the Codex Skill name limit, and exactly matches both the directory and the
`name` field in `SKILL.md` frontmatter. `category` classifies the Skill for
discovery, while `name` identifies the bounded project knowledge or capability.

Use the category and name supplied by the Human or established unambiguously by
accepted project evidence. Do not invent either component. Preserve an existing
pairing and accepted Skill identity; this rule does not authorize bulk
renaming. Return an ambiguous identity choice to the Human.

### Project references and authority

A Project Skill may maintain these AI-readable Specification references when
needed:

- `references/diagrams.md` for source-backed text diagram definitions;
- `references/roadmap.md` for Human-directed outcomes, ordering, and status;
- `references/issues.md` for traceable problems and their evidence.

Use Markdown for these references and prefer Mermaid fenced blocks for diagrams.
Ground every diagram relationship, roadmap priority or state, issue severity or
disposition, and other material claim in explicit Human instruction, accepted
project decisions, or inspected project evidence. Preserve source paths or
other provenance sufficient to inspect important claims.

AI may draft and maintain these files, but must not invent Human-owned priority,
deadline, owner, acceptance, issue closure, completion, or risk acceptance.
Review approval does not itself complete roadmap work or close an issue. The
references must faithfully reflect the paired browser Specification and must
not become a private source of additional or contradictory specified facts.

### Storage and Workspace projection

Under the current/default local adapter, keep a consumer Project Skill
physically separate from Original or Processed Explorer material below
`.agent-factory/explorer/`, its Human-facing Specification below
`.agent-factory/information/refined/human/<specification-id>/`, and operational
Agent state below `.agent-factory/agent/`. Do not automatically promote an
Explorer document into a Project Skill. The storage-independent adapter rules
below apply equally to the AI-facing representation.

The Workspace `skills/` Activity may discover and navigate actual Project
Skills below the owning project's `.codex/skills/`. This projection must not
copy, hardcode, or become the canonical owner of Project Skill content, and it
does not satisfy a missing paired representation.

Storage does not define the information class or document role. A project may
explicitly resolve a project server, external document store, mounted
filesystem, or another configured backend instead of the local adapter. Do not
silently choose, mirror, migrate, or designate a canonical backend. Preserve
Document type, provenance, authority, isolation, semantic alignment,
accessibility, and security across adapters. Backend configuration, identity,
synchronization and conflict policy, authentication, availability, and caching
remain unresolved until the Human or implementation contract decides them.

## Output format

Create every actual Specification document as HTML, CSS, and
JavaScript for Human viewing in a browser. For the current/default local
adapter, store Specification output below:

```text
<project-root>/.agent-factory/information/refined/human/
```

Use this minimum browser structure for a project-specific Specification:

```text
.agent-factory/information/refined/human/<specification-id>/
├── index.html
├── styles.css
├── app.js
└── assets/
```

Create `assets/` only when the Specification needs additional local resources.
Use actual SVG for user-facing icons. Do not use Markdown or JSON as the
canonical Human-facing Specification document.

Author every Human-facing Specification document in Korean. Korean is required
for prose, headings, labels, accessibility text, and authored explanatory
content. Preserve technical identifiers, code, paths, commands, proper nouns,
and source quotations in their original form when translation would reduce
accuracy. Apply that exception narrowly: it does not permit English scaffolding
or otherwise weaken the Korean-document requirement. This language rule applies
to the Human-readable Specification, not to the paired AI-readable Project
Skill or its Markdown references.

## New-document authoring workflow

1. Resolve a stable `specification-id` from an explicit Human-provided identity
   or unambiguous, accepted project evidence. Use lowercase hyphen-case. Do not
   infer an identity from tentative language, raw notes, or an unresolved
   naming choice; return that Human-owned decision when no stable identity is
   available.
2. Resolve the document adapter and paired-Skill owning context from explicit
   configuration or Human direction. Do not infer a remote backend or storage
   policy. For the local adapter, confirm that
   `<project-root>/.agent-factory/information/refined/human/<specification-id>/`
   does not exist. Only for a new target, copy the complete packaged template from
   `assets/document/` into that directory. Scaffolding is copy-once: never use
   the template to overwrite, reset, or merge over an existing Specification.
3. Inspect the accepted Human decisions, relevant project evidence, and any
   processed Explorer material or original Gather evidence accepted as input;
   Document work on a Specification reconciles those inputs into accepted
   knowledge. Resolve important provenance before
   drafting. Raw working notes, collection logs, and unassessed excerpts are
   inputs to reconcile, not trusted Specification truth to paste into the result.
4. Adapt the template to the actual body of knowledge. Remove, reorder, split,
   or extend the baseline sections when that makes the document clearer. The
   template is a flexible starting point, not a rigid schema.
5. Replace or remove every element marked `data-template-placeholder` and every
   `[[...]]` token. A document with any marked template placeholder remaining is
   scaffolding, not a Specification.
6. Create or update the resolved paired representation under the AI-facing
   ownership and identity contract above, and compare
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
decision. Refine Explorer and Gather evidence before inclusion: reconcile
conflicts, assess relevance, and summarize the supported conclusion without
promoting raw collection material as truth.

## Document boundaries and quality rules

For the local adapter, keep each Specification's content in its own
`.agent-factory/information/refined/human/<specification-id>/` directory and
optional document-specific resources in that document's `assets/`. Shared
browser-shell responsibilities belong to the Workspace capability at
`.agent-factory/workspace/common/`; do not copy project facts or one document's
private resources into that shell.

Preserve semantic HTML, keyboard access, visible focus, readable contrast, and
responsive behavior. Use only local relative dependencies; the document must
remain readable without JavaScript, with JavaScript limited to progressive
interaction. Use actual SVG for every user-facing icon—never icon-like Unicode,
CSS shapes, icon fonts, raster images, or external icon libraries. Keep the
entry-point links as `./styles.css` and `./app.js`.

Before treating an authored document as a Specification, account for every placeholder,
support every factual claim with provenance, separate accepted and unresolved
state, and ensure the paired Project Skill says the same thing. These are
authoring quality rules, not permission for a Work Agent to run tests or other
verification.

## Workspace projection

The Workspace control tower may discover and render a Specification through
Planning, but the document remains owned by Document in its resolved
document store. Workspace navigation does not refine content, supply a missing
paired Skill, or grant acceptance. Apply
`skills/workspace/references/interface.md` for shell and navigation behavior.

## Browser boundary

The Human-facing Specification is the rendered browser document itself, whether
opened directly or exposed through Workspace or another selected host. It must remain
usable from its HTML entry point with local CSS, JavaScript, and assets. Do not
require an AI to interpret a Markdown or JSON package before a Human can view
the Specification.

Reconcile working material before incorporating it. Do not treat raw Explorer
notes, a draft, a conversation transcript, or an operational log as a
Specification merely because it is rendered in the browser.

## Skill-instruction distinction

Files below `skills/document/references/` are Markdown instructions for the
Document Skill. They are not Specification documents. This Markdown
instruction format does not permit actual Specification output in the resolved
Human Specification document root to use Markdown instead of HTML, CSS, and
JavaScript.
