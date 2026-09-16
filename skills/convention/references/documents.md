# Documents

## Types and authority

- **Original:** source-faithful evidence in its native or otherwise
  appropriate format.
- **Processed:** transformed, non-authoritative working knowledge.
- **Specification:** project knowledge the Human explicitly requests
  as a Specification. Agent generation, refinement, inferred approval or file
  format never independently grants this type.
- Original, Processed and Specification are the only storage-independent Document
  types. Specification categories add no top-level type, and Refined is not a
  fourth type.
- `Original -> Processed -> Specification` records optional evidence or derivation.
  It is never a required pipeline, state machine, maturity scale, promotion or
  completion rule. Relationships may be absent or have any cardinality; preserve
  actual provenance.

## Provider placement

- Maintain Provider execution Skill guidance in English, an explicit exception to
  the Human-language Document contract. Preserve the `agent` and `convention`
  identities, YAML metadata and execution package structure.
- This Agent Factory plugin repository is the Provider. When the Human requests a
  durable Provider Original or Processed Document, use the same type-specific
  package roots below with `<plugin-root>` as the project root. Otherwise evidence
  remains at its existing source or in temporary execution state.
- Provider Processed Documents under `<plugin-root>/docs/processed/` remain
  non-authoritative and Git-ignored.
- Store Provider Specifications only as maintained packages under
  `<plugin-root>/skills/`. These Provider execution Skills retain `SKILL.md` and their owned
  `references/`, `scripts/`, `agents/`, `assets/` and runtime structure; the
  Document package restrictions below do not apply to them. Do not create parallel Provider
  Specifications under `docs/specification/` or `.codex/skills/` and do not migrate
  these distributed packages as Client Documents.
- The Provider exposes only `agent` and `convention`; Client Project Skill naming
  does not rename these accepted Provider identities.

## Routing

- In the currently implemented plugin-only mode, durable Client Documents use one
  package directory under exactly one of these local roots:

| Type | Canonical package |
|---|---|
| Original | `<project-root>/docs/original/<category>[-<domain>]-<name>/` |
| Processed | `<project-root>/docs/processed/<category>[-<domain>]-<name>/` |
| Specification | `<project-root>/docs/specification/<category>[-<domain>]-<name>/` |

- The local route is complete standalone behavior, not an error fallback. Use a
  concise `<category>[-<domain>]-<name>` package identity under the naming
  contract below. A category never changes
  Document type or acceptance authority.
- A Human-supplied alternative destination or format creates an additional export;
  it does not replace the canonical single source.
<!-- clause-id: specification.routing.canonical -->
- Processed and Specification use the same [Document package](#document-package).
  If the requested classification is unclear, resolve it with the Human before writing.
- Preserve existing user Documents in place. This contract authorizes no movement,
  conversion, renaming or deletion of existing packages or historical projections.
- This plugin implements no cloud Document receiver, migration path, automatic
  upload or local MCP/Document service. The future connected route below is a
  contract for later implementation, not a claim about the current MCP repository.
- Keep temporary execution artifacts in their run directories and maintained
  Provider instructions in their owning `skills/` packages.

### Original packages

- Store source identity, provenance, fidelity, locators and whether source content
  is stored as package metadata by default.
- Store actual source data inside the same Original package only when the Human
  explicitly requests it. Record its presence and format without implying that a
  locator is embedded content.
- Preservation and migration requirements grant no destructive local cleanup rule.

### Future connected storage and migration

<!-- clause-id: document.future-mcp.cutover -->
- The cloud Document MCP receiver and migration system described here does not yet
  exist. Actual cutover requires that future capability, an available authorized
  Agent Factory cloud Document MCP connection, and an explicitly resolved target
  workspace/project destination. A connection without that destination fails
  closed; never infer an upload target.
- Before cutover, enumerate the complete bounded inventory under
  `<project-root>/docs/original/`, `<project-root>/docs/processed/`, and
  `<project-root>/docs/specification/`. Migrate every existing local Document while
  preserving type, identity, provenance, content-presence, and each Document's
  single source, assets and existing derivation provenance. Use stable idempotency identifiers and verify receiver
  acknowledgements, integrity, and source-to-destination mappings.
- Report cutover only after the complete bounded inventory succeeds. Partial or
  ambiguous failure remains pending and retains recoverable local data; retry must
  be idempotent and no automatic deletion is permitted.
- After verified cutover, subsequent durable Documents use the resolved MCP
  destination as authoritative storage under its then-current authenticated
  contract. Do not silently fall back to local authoritative storage after that
  destination has been selected; report failures instead.

### Dual-storage mode

<!-- clause-id: document.future-mcp.dual-storage -->
- If the Human explicitly requests both canonical local storage and the future
  cloud Document MCP storage, use dual-storage mode. This is a future contract
  only: the cloud receiver, migration system, and dual-storage execution path are
  not currently implemented.
- For every create or update, first mutate the authoritative MCP Document at its
  resolved target using the expected revision/CAS and idempotency contract. Only
  after its acknowledgement succeeds, fetch the committed MCP revision and
  synchronize the received content and metadata to the canonical local package.
  Derive the local projection from that MCP-confirmed revision, never independently
  from proposed input.
- Never write local first, perform concurrent bidirectional writes, or silently
  merge divergent local and MCP state. If the MCP mutation fails or its outcome is
  ambiguous, do not mutate the local projection.
- If the MCP mutation succeeds but local projection fails, MCP remains
  authoritative and local is explicitly stale and pending retry. Retry projection
  from that same MCP revision without replaying the MCP mutation.
- For Processed and Specification, project the MCP-confirmed revision to the
  canonical user-language `SKILL.md` and optional `assets/` package. Any display or
  Skill exposure derives from that same source, never a separately edited pair.
- Initial cutover into dual-storage mode imports each local Document to MCP,
  confirms its committed revision, and then re-projects that confirmed MCP state to
  local. Conflicting pre-existing MCP and local revisions require Human resolution;
  never choose authority by timestamps.

## Document package

- Original uses its native or otherwise source-appropriate format.
- Every AI-generated durable Document is Processed by default unless the Human
  explicitly requests a Specification. File format never grants that authority.
- Processed and Specification share one package structure: a single `SKILL.md`
  in the Human's language, plus optional `assets/`. Do not add `references/`,
  `scripts/` or `agents/` to Document packages; Provider execution Skills are exempt.
- Use the language the Human uses, or their explicitly selected language for the
  Document. Preserve source text, quotations, code and identifiers; language choice
  alone authorizes no translation or conversion of existing material.
- `SKILL.md` is the single source for the document body. The body and `assets/`
  together form the canonical editable package; asset CSV and JSON files are
  editable sources too. The filename does not make Processed an automatically
  active Skill or a Specification.
- Keep independent CSV datasets, Archify-based diagram JSON and necessary images
  in `assets/`. Write tables in the body as Markdown tables.
- Reference assets by relative path at the point where they belong in the body.
  The Human-facing viewer contract is to expand each referenced asset there and
  present the body and assets as one document. HTML or other displays are derived
  presentation, never a second editable source or a required translation.
- The viewer, Archify rendering integration and ERD support are follow-up
  implementation work. This contract does not claim they are implemented or
  authorize an external Archify installation. See [Diagrams](diagrams.md).
- Use H1/H2/H3 only and section numbering no deeper than `1` / `1.1`.
  Split deeper topics into separate Documents. Refine content into bullets and
  numbered lists; avoid unnecessary long prose. Code, tables and diagrams are allowed.

## Naming and metadata

- Use `<category>-<domain>-<name>` when the project defines the optional domain;
  otherwise use `<category>-<name>`. Routing uses `<category>[-<domain>]-<name>`
  to denote those alternatives; brackets are not literal directory characters.
- The project defines domains. Never infer a missing domain or bulk-rename accepted
  identities. Keep category tokens below and preserve the Human-resolved name.
- In `SKILL.md` YAML frontmatter metadata, explicitly record `document-type`,
  `category`, `domain` and `name`. Use `domain: null` when no domain is defined.
  Record `language` and actual provenance as applicable; metadata does not grant authority.
- Original package metadata also records category, optional domain and name without
  requiring conversion of its native source into `SKILL.md`.

### Specification naming

- Specification categories are limited to `info-*`, `rule-*`, and `design-*`.

| Category | Meaning |
|---|---|
| `info` | Describe facts in an informative, declarative form. |
| `rule` | State obligations and compliance requirements in a mandatory form. |
| `design` | Organize planning intent and implementation design in a design form. |

- Keep planning intent and implementation design together in `design` when they
  describe the same subject. Do not introduce `plan` or `spec` as Design categories.
- `design` is not limited to visual styling; [Theme](theme.md) owns presentation rules.

### Processed categories

| Category | Meaning |
|---|---|
| `interview` | Human interview evidence; follow the [Interview writing contract](interview.md#completion-and-record). |
| `research` | Research. |
| `analyze` | Internal analysis. |
| `websearch` | Web search evidence. |
| `process` | Progress and status. |
| `classification` | Original source classification. |
| `other` | Other processed knowledge. |
| `extraction` | Extracted content. |
| `comparison` | Comparisons. |

- Use `summary` as a section when needed, not as a Processed category.

## Derived Skill exposure and display

- Client Specifications remain canonical at
  `docs/specification/<category>[-<domain>]-<name>/SKILL.md`; Processed remains at
  `docs/processed/<category>[-<domain>]-<name>/SKILL.md`.
- When Specification discovery needs `.codex/skills/<category>[-<domain>]-<name>/`,
  expose a derivation of the same canonical source. It is not a separate editable
  original. Do not require an English Skill, translated HTML, counterpart metadata
  or a two-source synchronization transaction.
- Update meaning in the canonical source and regenerate any derived display or
  exposure as needed. Presentation may improve readability without changing or
  concealing meaning; a stale derivation grants no competing authority.
- Ambiguous requirements or conflicting accepted meaning require the Human's
  decision through Interview. Do not infer acceptance from timestamps or generated
  output. A Processed `comparison` package may support that decision without
  acquiring Specification authority.
