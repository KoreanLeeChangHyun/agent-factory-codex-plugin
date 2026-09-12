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

- This Agent Factory plugin repository is the Provider. It has no active Original
  Document storage route. Evidence remains at its existing source or in temporary
  execution state; do not copy it into a repository Original-document tree.
- Store Provider Processed Documents under `<plugin-root>/docs/`. The root `/docs/`
  path is Git-ignored and contains no authoritative plugin contract.
- Store Provider Specifications only as maintained packages under
  `<plugin-root>/skills/`. `SKILL.md` and its owned `references/`, `scripts/` and
  `assets/` form the Specification package. Do not create parallel Provider
  Specifications under `docs/` or `.codex/skills/`.
- The Provider exposes only `agent` and `convention`; Client Project Skill naming
  does not rename these accepted Provider identities.

## Routing

For Client Original and Processed Documents, generated output outside this
Provider-specific placement, and optional Specification exports:

1. **Explicit destination:** follow the Human-supplied destination and format.
2. **Selected connected destination:** only when a Document capability is available,
   explicitly selected and authorized for the write, use its current contract and
   resolved destination. Connection or discovery alone grants no transmission authority.
3. **Local route:** otherwise write under `<project-root>/docs/` with a concise
   `[분류]-[이름]` (`<category>-<name>`) basename. Use the appropriate extension
   for a file or that basename as the directory for a multi-file package.

- The local route is complete standalone behavior, not an error fallback. A
  filename category never changes Document type or acceptance authority.
<!-- clause-id: specification.routing.canonical -->
- Client Specification projections are an exception to this general routing
  order: their canonical paths and formats are fixed by
  [Client Specification projections](#client-specification-projections). A
  Human-supplied alternative destination or format creates an additional export
  or a Processed Document; it does not replace either canonical projection. If the
  requested classification is unclear, resolve it with the Human before writing.
- Report failures after a connected destination was selected; do not silently
  choose another destination or create a second copy. This contract adds no
  automatic upload, migration or local Document service.
- Keep temporary execution artifacts in their run directories and maintained
  Provider instructions in their owning `skills/` packages.

## Formats

- Original uses its native or otherwise source-appropriate format.
- Processed defaults to Markdown and may use CSV or JSON when tabular or structured
  data makes one appropriate. A Processed Document is never a Project Skill.
- Only a Human-requested Specification becomes a Project Skill.

## Specification naming

- Use the Human-resolved lowercase `<category>-<name>` identity. Do not infer
  components or bulk-rename accepted identities.
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
  language at `docs/<category>-<name>.html`. These canonical locations override
  the general Document routing order; neither representation may be redirected,
  omitted or replaced by a single alternative file.

<!-- clause-id: specification.human.presentation -->
- The Human representation may add highlighting, diagrams and layout that improve
  comprehension. Presentation-only changes do not change Skill semantics. Text or
  relationships in a diagram are semantic when they alter requirements, rules,
  facts or design intent.

<!-- clause-id: specification.html.packaging -->
- Keep HTML self-contained by default. At 3,000 unminified source lines, review
  splitting; do not split solely because the count was reached. Prefer the
  structure an AI can read and modify reliably, considering DOM size, byte size and
  independently maintainable CSS, JavaScript, SVG or content sections. When
  splitting is warranted, use `docs/<category>-<name>/index.html` with local files.

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
| `counterpart` | Resolved locator for the other representation. |
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
  the Agent uses local file tools and the transaction below. When the Human selects
  an available MCP Document capability, that MCP server provides file access,
  version checks and transaction handling. The Provider plugin implements no
  separate synchronization service and requires neither an MCP-owned language
  model, language-neutral semantic model nor third canonical Specification.

<!-- clause-id: specification.sync.agent-language -->
- On a Human request, the Agent maps affected `clause-id` values, writes the English
  Skill and Human-language HTML in the Client, and checks semantic correspondence.
  Local tools provide standalone access; a selected MCP capability provides
  connected access.

<!-- clause-id: specification.sync.local-transaction -->
- In standalone mode, read and revalidate both current projections and their shared
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
  their embedded metadata. A selected MCP capability returns its structured
  conflict facts. In either mode, the Agent resolves conflicts through Interview in
  the current Human conversation. Do not overwrite either representation or
  advance `sync-base-revision` before the Human decides.

<!-- clause-id: specification.conflict.large -->
- For a conflict too large to compare safely in conversation, the Agent may create
  a Processed HTML comparison as supporting evidence. The conversation remains the
  decision surface and the comparison grants no Specification authority.
