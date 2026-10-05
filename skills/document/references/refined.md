# Refined writing

<a id="authority-and-scope"></a>

## 1. Authority and scope

- Apply the mandatory [Document core requirements](../SKILL.md).
- You MUST write in the Human's language, or their explicitly selected document
  language. This applies across languages; do not use a fixed default language.
- Refined is transformed, non-authoritative working knowledge. It retains
  `document-type: processed` for metadata and filter compatibility. Every AI-generated
  durable Document is Refined by default unless the Human explicitly requests a
  Specification (Skill document), except task progress and status records, which use
  [Progress](progress.md), and error or Human/AI judgment-difference records, which use
  [Lessons Learned](lessons-learned.md). A `SKILL.md` filename does not confer authority.
- Store the body at `docs/refined/<category>/<topic>/SKILL.md`, with optional `references/` for detailed Markdown and `assets/` for attachments under the shared package
  rules.
- Preserve actual provenance and source fidelity as applicable. Distinguish source
  evidence, observations, analysis and unresolved questions; do not present an inference
  as an accepted requirement.
- A comparison may support a Human decision without acquiring Specification authority.
  Do not require a progression from Original to Refined to Specification (Skill).
- Refined packages are discovered through the shared
  [catalog and search contract](host-sync.md#local-document-catalog-and-search); catalog
  presence does not activate them as Skills.

<a id="refined-categories"></a>

## 2. Refined categories

| Category | Meaning |
|---|---|
| `analysis` | Internal analysis. |
| `research` | Research and source-based investigation. |
| `interview` | Human interview evidence; follow the [Interview contract](../../convention/references/interview.md#completion-and-record). |
| `comparison` | Comparisons. |
| `history` | Historical decisions, discussions and superseded guidance; no current rule authority. |

- Keep readable topic names without repeating the category prefix. Preserve document IDs,
  language, authority, references, assets and actual provenance.
- Flat packages and legacy categories remain readable. Classify ambiguous `other-*` and
  `classification-*` packages from their bodies; never infer a category from the name alone.
- Preview and explicitly apply authorized moves using the [layout migration contract](host-sync.md#document-layout-migration).
- Use `summary` as a section when needed, not as a Refined category.
- Preserve existing `process-*` packages and links, whether in `docs/refined/` or legacy
  `docs/processed/`. Move or reclassify them only when the Human explicitly requests migration.
