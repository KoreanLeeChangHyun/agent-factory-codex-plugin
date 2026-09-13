# Documents

## Types and authority

- **Original / 원본 문서:** source-faithful evidence in its native or otherwise
  appropriate format.
- **Processed / 가공 문서:** transformed, non-authoritative working knowledge.
- **Specification / 명세 문서:** project knowledge the Human explicitly requests
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

- This Agent Factory plugin repository is the Provider. When the Human requests a
  durable Provider Original or Processed Document, use the same type-specific
  package roots below with `<plugin-root>` as the project root. Otherwise evidence
  remains at its existing source or in temporary execution state.
- Provider Processed Documents under `<plugin-root>/docs/processed/` remain
  non-authoritative and Git-ignored.
- Store Provider Specifications only as maintained packages under
  `<plugin-root>/skills/`. `SKILL.md` and its owned `references/`, `scripts/` and
  `assets/` form the Specification package. Do not create parallel Provider
  Specifications under `docs/specification/` or `.codex/skills/` and do not migrate
  these distributed packages as Client Documents.
- The Provider exposes only `agent` and `convention`; Client Project Skill naming
  does not rename these accepted Provider identities.

## Routing

In the currently implemented plugin-only mode, durable Client Documents use one
package directory under exactly one of these local roots:

| Type | Canonical package |
|---|---|
| Original | `<project-root>/docs/original/<category>-<name>/` |
| Processed | `<project-root>/docs/processed/<category>-<name>/` |
| Specification | `<project-root>/docs/specification/<category>-<name>/` |

- The local route is complete standalone behavior, not an error fallback. Use a
  concise lowercase `<category>-<name>` package identity. A category never changes
  Document type or acceptance authority.
- A Human-supplied alternative destination or format creates an additional export;
  it does not replace canonical local storage or either Specification projection.
<!-- clause-id: specification.routing.canonical -->
- Client Specification projections have the fixed paths and formats in
  [Client Specification projections](#client-specification-projections). If the
  requested classification is unclear, resolve it with the Human before writing.
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
  preserving type, identity, provenance, content-presence, and each Specification's
  HTML/Project Skill pairing. Use stable idempotency identifiers and verify receiver
  acknowledgements, integrity, and source-to-destination mappings.
- Report cutover only after the complete bounded inventory succeeds. Partial or
  ambiguous failure remains pending and retains recoverable local data; retry must
  be idempotent and no automatic deletion is permitted.
- After verified cutover, subsequent durable Documents use the resolved MCP
  destination as authoritative storage under its then-current authenticated
  contract. Do not silently fall back to local authoritative storage after that
  destination has been selected; report failures instead.

#### Dual-storage mode

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
- For a Specification, project the MCP-confirmed revision to its local
  Human-language HTML and English Project Skill pair using the existing atomic pair
  transaction and shared semantic metadata.
- Initial cutover into dual-storage mode imports each local Document to MCP,
  confirms its committed revision, and then re-projects that confirmed MCP state to
  local. Conflicting pre-existing MCP and local revisions require Human resolution;
  never choose authority by timestamps.

## Formats

- Original uses its native or otherwise source-appropriate format.
- Processed defaults to Markdown and may use CSV or JSON when tabular or structured
  data makes one appropriate. Every AI-generated durable Document is Processed by
  default. Processed categories are open-ended and may include `interview`,
  `research`, and `analysis`. A Processed Document is never a Project Skill.
- Only a Human-requested Specification becomes a Project Skill.

## Specification naming

- Use the Human-resolved lowercase `<category>-<name>` identity. Do not infer
  components or bulk-rename accepted identities.
- Specification categories are limited to `info-*`, `rule-*`, and `design-*`.
- Use `info-*` for information Agents consult, `rule-*` for rules Agents must
  follow, and `design-*` for integrated planning intent and technical design.
- Keep planning intent and technical design together in one `design-*`
  Specification. Do not introduce `plan-*` or use `spec-*` as the Design category.
- `design-*` does not mean visual styling. Convention's `theme.md` owns interface
  themes, visual systems and presentation rules.

## Client Specification projections

<!-- clause-id: specification.projections.two -->
- A Client Specification has two synchronized representations with one identity
  and version: an English AI-facing Project Skill at
  `.codex/skills/<category>-<name>/` and a Human-facing HTML document in the Human's
  language at `docs/specification/<category>-<name>/index.html`. The HTML is inside
  the Specification package. Neither representation may be redirected, omitted or
  replaced by a single alternative file.

<!-- clause-id: specification.human.presentation -->
- The Human representation may add highlighting, diagrams and layout that improve
  comprehension. Presentation-only changes do not change Skill semantics. Text or
  relationships in a diagram are semantic when they alter requirements, rules,
  facts or design intent.

<!-- clause-id: specification.html.packaging -->
- Keep `index.html` self-contained by default. At 3,000 unminified source lines, review
  splitting; do not split solely because the count was reached. Prefer the
  structure an AI can read and modify reliably, considering DOM size, byte size and
  independently maintainable CSS, JavaScript, SVG or content sections. When
  splitting is warranted, keep local files in the same
  `docs/specification/<category>-<name>/` package.

## Embedded metadata

<!-- clause-id: specification.metadata.embedded -->
Embed equivalent metadata in Skill YAML frontmatter and the HTML document so each
representation remains self-identifying without an MCP connection.

| Field | Contract |
|---|---|
| `specification-id` | Stable shared Specification identity. |
| `specification-version` | Human-visible shared version. |
| `projection` | `ai` for Skill or `human` for HTML. |
| `language` | Representation language. |
| `counterpart` | Canonical locator for the other representation: the Skill uses `docs/specification/<category>-<name>/index.html`; the HTML uses `.codex/skills/<category>-<name>/`. |
| `semantic-revision` | Meaning revision represented by this file. |
| `sync-base-revision` | Last meaning revision committed to both representations. |
| `modified-at` | Actual representation modification time in RFC 3339 form. |

<!-- clause-id: specification.metadata.clause-id -->
- Give each semantic requirement, rule, fact or design statement a stable
  `clause-id` shared across translations. Layout-only elements need no semantic ID.

<!-- clause-id: specification.metadata.modified-at -->
- Use `modified-at` for chronology and Human inspection; never treat the newest
  timestamp as semantic authority.

## Synchronization

<!-- clause-id: specification.sync.ownership -->
- Synchronization follows the selected destination capability. In standalone mode,
  the Agent uses local file tools and the transaction below. Only after the future
  cloud receiver exists and the connected-storage cutover conditions succeed may
  its then-current contract provide authoritative storage, version checks and
  transaction handling. The Provider plugin implements no separate synchronization
  service and requires neither an MCP-owned language model, language-neutral
  semantic model nor third canonical Specification.

<!-- clause-id: specification.sync.agent-language -->
- On a Human request, the Agent maps affected `clause-id` values, writes the English
  Skill at `.codex/skills/<category>-<name>/` and the Human-language HTML at
  `docs/specification/<category>-<name>/index.html`, and checks semantic
  correspondence. Local tools provide the currently implemented standalone access.

<!-- clause-id: specification.sync.local-transaction -->
- In standalone mode, read and revalidate the Skill at
  `.codex/skills/<category>-<name>/` and HTML at
  `docs/specification/<category>-<name>/index.html` with their shared
  `sync-base-revision`; stage both complete replacements at temporary sibling paths
  on their target filesystems; validate metadata, `clause-id` coverage, links and
  semantic correspondence; then preserve recoverable originals and replace both
  projections. If either replacement fails, restore the preserved originals. If an
  interruption prevents rollback, retain the unchanged `sync-base-revision`, mark
  the pair as a partial failure or pending repair, and do not report synchronization
  complete. This is the standalone transaction contract and requires no MCP.

<!-- clause-id: specification.sync.atomic -->
- Stage both representations and commit a new shared semantic revision only after
  both updates succeed. Advance `sync-base-revision` in both projections only as
  part of those staged replacements. A one-sided write is a partial failure or
  pending repair, never completed synchronization.

<!-- clause-id: specification.sync.ambiguity -->
- Translation equivalence is an Agent judgment. If wording is ambiguous or the
  languages cannot be reconciled confidently, ask the Human instead of inferring
  acceptance or making MCP resolve meaning.

## Conflicts

<!-- clause-id: specification.conflict.definition -->
- A semantic conflict exists when both representations diverge from the same
  `sync-base-revision` for the same `clause-id`, or a partial/manual edit makes the
  intended shared meaning ambiguous. Propagate a one-sided unambiguous semantic
  change to its counterpart.

<!-- clause-id: specification.conflict.presentation -->
- Styling, highlighting, spacing and interaction changes are not conflicts unless
  they alter or conceal semantic content.

<!-- clause-id: specification.conflict.interview -->
- In standalone mode, the Agent derives conflict facts from both projections and
  their embedded metadata. A future connected capability may return structured
  conflict facts only after the cutover contract applies. In either mode, the Agent
  resolves conflicts through Interview in the current Human conversation. Do not
  overwrite either representation or advance `sync-base-revision` before the Human
  decides.

<!-- clause-id: specification.conflict.large -->
- For a conflict too large to compare safely in conversation, the Agent may create
  a Processed HTML comparison as supporting evidence. The conversation remains the
  decision surface and the comparison grants no Specification authority.
