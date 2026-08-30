---
name: convention
description: Apply Agent Factory's core model and cross-cutting conventions for project structure, development, testing, libraries, design, annotations, Document types, and Skill ownership.
metadata:
  specification-id: convention
  human-entry: .agent-factory/document/specification/convention/index.html
  ai-root: skills/convention/
---

# Agent Factory Convention

## Entry contract

Use this Skill whenever work designs, reviews, or explains Agent Factory core
concepts or applies its cross-cutting conventions, including Document types,
capability boundaries, Skill ownership and naming, document storage,
project structure, development, testing, libraries, design, or annotations. Read every
applicable reference before acting.

Agent Factory has exactly six public distributed Skills: `agent`,
`convention`, `document`, `gather`, `tool`, and `workspace`. Explorer and Interview remain core
capabilities rather than public Skill entry points. Convention owns their
durable semantics and the paired AI-facing core representation; Agent's Main
and Work roles apply them within the managed execution graph.

Treat Original, Processed, and Specification Documents as loosely related
logical types independent of storage. Their conceptual ordering is
`Original -> Processed -> Specification`, but the arrows express only possible
derivation or evidence relationships. They are not a mandatory pipeline, state
machine, required transition, maturity scale, or one-to-one mapping. A
Document may remain in one type, and relationships may be absent or have any
cardinality. Preserve inspectable provenance for actual derivation or evidence
relationships without inferring completeness, acceptance, authority, or
automatic promotion from a type name. Preserve Original Documents in a native
or source-appropriate form, including fidelity, identity, provenance, and
collection context; never impose one canonical original format. Under the
current/default `.agent-factory/` local adapter, active Processed Documents use
Markdown (`.md`), but that representation does not make the logical Processed
type storage-dependent. Each local type root contains Document packages
directly: one immediate child directory is one stable Document identity, with
package-internal files and subdirectories allowed and no producer/category or
legacy wrapper layer. Preserved `processed/legacy-inquery-<legacy-id>/`
packages remain Processed, with legacy expressed only as status/provenance, and
are not active targets or precedents. An explicitly resolved project server or
external backend may own any document root without weakening provenance,
authority, isolation, semantic alignment, accessibility, or security. Never
invent or silently select a backend.

A Specification is accepted and reconciled project knowledge represented as
one semantic body by exactly one resolved AI-facing Skill representation and
exactly one resolved Human-facing Korean HTML, CSS, and JavaScript
representation under the same stable identity. Always keep both
representations semantically synchronized. Their concrete locators are
adapter-resolved; local directories are not the universal contract. A
one-sided change is incomplete and unacceptable; if synchronization cannot be
achieved, the change or run must not be reported as completed.

This Skill's Human Specification is the Human-centered semantic representation
of `skills/convention/`. Preserve the reciprocal `convention` identity and
locators in this frontmatter and the paired HTML metadata. Organize the Human
document by readable topics rather than copying the Skill directory hierarchy,
and keep material sections traceable to exact Skill or reference sources.

Document adapter initialization and physical layout/backend migration remain
inside the public `document` Skill and are distinct from semantic Document
work. Physical migration preserves `documentType`; it never promotes Original,
Processed, or Specification. LLM participation is limited to non-executable
advisory/authoring proposals. A deterministic manager may act only from a
closed, versioned, allowlisted plan/IR after current-state revalidation and any
required Human authority. Specification representations form one publication
group; a one-sided change fails closed. Apply the complete Document-owned
contract in `skills/document/references/adapter.md` and the paired core model
in `references/agent-factory-core.md`.

Workspace is the Human-facing project control tower with exactly five
top-level Activities, in order: 일정, 에이전트, 문서, 로그, 테스트. Their
Document Primary Sidebar is decided as ordered, independently collapsible
`원본문서`, `가공문서`, and `스펙문서` groups: Original has overview and
table-shaped search views, while Processed and Specification have overview and
consistent explorer/tree-shaped areas for actual Documents. `스펙문서` is a
display label, not a semantic type rename. Finer Document view/source details
and the other four sidebar architectures and capabilities remain Human-owned
and unresolved. Workspace does not own or execute underlying state.
Its browser shell must exist as byte-identical packaged installation sources in
`skills/workspace/assets/browser/` and a materialized current-project copy in
`.agent-factory/workspace/common/`; the packaged assets are the installation
source, not a second runtime authority. The three core browser-code files are
`index.html`, `styles.css`, and `app.js`; the initializer also installs the
byte-identical companion `THIRD_PARTY_NOTICES.txt` attribution and license
asset, which is not a fourth browser-code file.

Tool is the logical control plane for Agent-usable external tool and connector
lifecycle. It owns discovery/catalog metadata, lifecycle routing,
connection/authentication state, opaque credential references,
requested/granted scopes, health, enablement, and capability metadata while
preserving each host, plugin, MCP server, or project manifest as authority. It
does not store credentials, execute Agent tasks, own Gather synchronization, or
create a sixth Workspace Activity. Convention owns shared least-privilege,
safety, and approval rules across these integrations.

Git commit is a narrow result-integration/publication action owned by Main,
not bounded Work or Verification. After independent Verification passes, or
after an evidenced Human skip is applied following Work completion, Main
promptly commits the authorized result directly instead of delegating a
separate commit Work turn. Main must inspect and stage only the exact paths
bound to that verified or skipped result and exclude unrelated dirty changes.
Work and Verification never commit. Commit authority does not authorize push,
amend, force, history rewrite, or any other repository publication or
mutation. Apply the detailed boundary in `references/development.md`.

The exact `<project-root>/.agent-factory/db.sqlite` local catalog and all of its
implementation lifecycle are Agent-owned. Workspace may only present
Agent-provided read-only results; it never owns, initializes, rebuilds,
inspects, or executes searches against the catalog. Preserve the catalog as an
ignored, rebuildable, non-authoritative projection that cannot replace any
owning Agent or Document source. Detailed catalog operations belong to Agent;
Convention carries only this cross-cutting ownership rule.

Keep distributed plugin Skills below `<plugin-root>/skills/`. Under the
current/default local adapter, ordinary consumer Project Skill and
Specification pairs use the exact same lowercase hyphen-case
`<category>-<title>` identity at
`<project-root>/.codex/skills/<category>-<title>/` and
`<project-root>/.agent-factory/document/specification/<category>-<title>/`.
This plugin is the explicit exception: preserve the accepted single-name
distributed Skill and Specification identities. An explicitly resolved
external backend may use different locators while preserving the one-to-one
pair and stable identity.

## Reference routing

- `references/agent-factory-core.md`: Apply the accepted Document model,
  capabilities, engineering stack, Skill ownership, storage-independent
  document roles, adapter initialization/migration boundary, and Specification
  paired representations.
- `references/directory-structure.md`: Apply the recommended local/default
  project layout and ownership boundaries.
- `references/development.md`: Apply shared implementation and maintenance
  conventions, including Main-owned narrow Git commit publication, while
  preserving the owning project's established patterns.
- `references/testing.md`: Apply focused test selection and execution scope
  whenever implementation, maintenance, or Verification work selects or runs
  tests.
- `references/explicit-human-input.md`: Apply the explicit-Human-input rule
  whenever requirements, choices, scope, authority, or acceptance criteria are
  absent or ambiguous; Main asks and waits, while delegated Agents report the
  unresolved question without impersonating or interviewing the Human.
- `references/libraries.md`: Select dependencies and formats using the
  recommended library policy.
- `references/design.md`: Apply shared Human-facing interface and document
  design conventions.
- `references/annotation.md`: Create or review comments, documentation
  comments, and traceable TODO annotations.
- `references/svg-icon.md`: Apply the detailed SVG-only icon convention when
  user-facing icons are involved.
- `references/diagrams.md`: Select and author ERD, game-behavior, and sequence
  diagrams, and keep AI-readable Mermaid sources aligned with Human-facing
  representations.
- `references/explorer.md`: Apply Explorer's information, provenance, and
  authority boundaries when defining or routing evidence exploration.
- `references/interview.md`: Apply Interview's information and Human-authority
  boundaries when Main conducts adaptive elicitation.

## Bootstrap assets

`assets/AGENTS.md` is the plugin-provided project instruction template.
`scripts/init_agents.py` copies it once to `<project-root>/AGENTS.md` and refuses
to overwrite any existing path. The plugin manifest itself does not inject
project files.
