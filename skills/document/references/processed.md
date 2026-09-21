# Processed writing

<a id="authority-and-scope"></a>

## 1. Authority and scope

- Apply the mandatory [Document core requirements](../SKILL.md).
- You MUST write in the Human's language, or their explicitly selected document
  language. This applies across languages; do not use a fixed default language.
- Processed is transformed, non-authoritative working knowledge. Every AI-generated
  durable Document is Processed by default unless the Human explicitly requests a
  Specification, except task progress and status records, which use
  [Progress](progress.md), and error or Human/AI judgment-difference records, which use
  [Lessons Learned](lessons-learned.md). A `SKILL.md` filename does not confer authority.
- Store the body at `docs/processed/<category>[-<domain>]-<name>/SKILL.md`, with optional `assets/` under the shared package
  rules.
- Preserve actual provenance and source fidelity as applicable. Distinguish source
  evidence, observations, analysis and unresolved questions; do not present an inference
  as an accepted requirement.
- A comparison may support a Human decision without acquiring Specification authority.
  Do not require a progression from Original to Processed to Specification.
- Processed packages are discovered through the shared
  [catalog and search contract](../SKILL.md#local-document-catalog-and-search); catalog
  presence does not activate them as Skills.

<a id="processed-categories"></a>

## 2. Processed categories

| Category | Meaning |
|---|---|
| `interview` | Human interview evidence; follow the [Interview writing contract](../../convention/references/interview.md#completion-and-record). |
| `research` | Research. |
| `analyze` | Internal analysis. |
| `websearch` | Web search evidence. |
| `process` | Legacy progress and status records; use Progress for new records. |
| `classification` | Original source classification. |
| `other` | Other processed knowledge. |
| `extraction` | Extracted content. |
| `comparison` | Comparisons. |

- Use `summary` as a section when needed, not as a Processed category.
- Preserve existing `docs/processed/process-*` packages and links. Move or reclassify
  them only when the Human explicitly requests migration.
