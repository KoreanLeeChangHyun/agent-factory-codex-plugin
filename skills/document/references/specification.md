# Specification writing

<a id="authority-and-scope"></a>

## 1. Authority and scope

- Apply [Document requirements](../SKILL.md). Only the Human's explicit request grants Specification authority;
  generation, format and inferred approval do not.
- You MUST write in the Human's language, or their explicitly selected document
  language. This applies across languages; do not use a fixed default language.
- A Skill document MUST present the current accepted state as a self-contained final
  reference. Readers must not reconstruct it from previous revisions.
- Do not include change logs, past discussions, superseded decisions, historical copies
  or narratives of how the document evolved. Keep such records in Processed documents
  and source evidence in Original documents.
- Integrate accepted changes into the current clauses. Preserve applicable meaning and
  explicitly unresolved choices without turning them into a decision history.

<a id="specification-naming"></a>

## 2. Specification naming

- Specification categories are limited to `info-*`, `rule-*`, and `design-*`.

| Category | How to write | Example |
|---|---|---|
| `info` | State known facts and their scope; distinguish observations from assumptions. | “The extension host owns session persistence.” |
| `rule` | State who or what must do what, under which condition; include accepted exceptions. | “When submitting an answer, the client must include the question ID.” |
| `design` | State the intended behavior, relevant flow and boundaries; include implementation design only where decided. | “Selecting an option sends its answer immediately, without confirmation.” |

- Keep planning intent and implementation design for the same subject in `design`; do
  not add `plan` or `spec` categories. Design includes behavior, not only
  styling.

<a id="writing-procedure"></a>

## 3. Writing procedure

1. Identify the subject, applicable scope, accepted content and unresolved decisions.
2. Group related content using the mandatory [Document structure](../SKILL.md#document-structure). Include only useful sections;
   do not create empty purpose, history, glossary or implementation sections.
3. Write one fact, obligation or design decision per item, using the category above.
   Retain conditions, exceptions and observable outcomes that affect interpretation.
4. Use Markdown tables for comparisons, numbered lists for ordered behavior and JSON for
   blocks. Indent mixed nested lists. Keep examples separate from requirements; examples
   must not introduce new rules.
5. Integrate revisions into the affected clauses and remove superseded duplication. Put
   unresolved choices in a clearly marked section only when they exist; never fill gaps
   with invented requirements or claim implementation completion.
6. Review coverage against the accepted content: no missing conditions, contradictory
   clauses, ambiguous subjects or new decisions. Resolve conflicting accepted meaning
   with the Human; a Processed comparison may support that decision without authority.

<a id="package-and-derived-copies"></a>

## 4. Package and derived copies

- Store the canonical body at `docs/skills/<category>[-<domain>]-<name>/SKILL.md`, with optional `assets/`. Follow the shared
  language, heading, metadata and asset rules.
- Update the canonical source and regenerate `.codex/skills/` or displays from it. Do not
  require an English translation, paired HTML, counterpart metadata or a two-source
  synchronization transaction. A stale copy gains no competing authority.
