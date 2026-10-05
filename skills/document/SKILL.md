---
name: document
description: Write, revise, consolidate, convert, classify, store, catalog, search, or synchronize Agent Factory Documents using mandatory writing and single-source rules.
metadata:
  specification-id: document
---

# Agent Factory Document

- `<plugin-root>` is the installed Agent Factory plugin directory that contains `skills/`,
  `runtime/` and `scripts/`; it is two levels above this `SKILL.md`.

<a id="mandatory-compliance"></a>

## 1. Mandatory compliance

- You MUST apply this Skill and the relevant type guide. Before completion, check
  language, meaning, writing, metadata, links, assets and source ownership; fix in-scope
  violations or report unresolved conditions. Format and sync checks are insufficient.
- Preserve accepted decisions and unresolved choices. Do not invent requirements,
  provenance or approval. Conversion, consolidation and storage grant no extra
  authority.
- Keep the requested coherent document. Skill documents MUST be self-contained
  references for the current accepted state, not historical records. Keep change logs,
  past discussions and superseded decisions in Refined documents; keep task progress
  and status in Progress documents. Preserve source
  evidence in Original documents.
- After creating, modifying or deleting any package under `docs/skills/`,
  you MUST directly run the [synchronization script](references/host-sync.md#continuous-codex-synchronization) for that document's project and check its result
  before reporting completion.
  - Use the actual project root, inspect the CLI result, and resolve or report conflicts.
  - Never claim synchronization succeeded when the CLI fails or reports a conflict.

<a id="writing-guides"></a>

## 2. Writing guides

- `references/specification.md`: write accepted facts, rules and designs.
- `references/refined.md`: write refined analysis and working knowledge.
- `references/original.md`: preserve source evidence and metadata.
- [Progress writing](references/progress.md): record task progress, status and remaining work.
- [Lessons Learned writing](references/lessons-learned.md): record errors and judgment differences; consolidate lessons into Skill rules.
- For work contract content, use Convention's [work contract](../convention/references/work-contracts.md);
  this Skill continues to own durable document language, classification and storage.
- Read only the guides for the types involved. Use [Convention](../convention/SKILL.md) for shared development,
  themes, diagrams and interviews; [Agent](../agent/SKILL.md) for managed execution, not this Skill.

<a id="types-and-authority"></a>

## 3. Types and authority

| Type | Meaning |
|---|---|
| Original | Source-faithful metadata and links identifying external evidence. |
| Refined | Transformed, non-authoritative working knowledge. Uses the compatible `processed` metadata type. |
| Progress | Task progress, current status and remaining work; no Specification authority. |
| Lessons Learned | Error causes/solutions and Human/AI judgment differences with reflection; no Specification authority. |
| Specification (Skill document) | Project knowledge explicitly requested as a Specification by the Human. The names are synonymous. |

- Every AI-generated durable Document is Refined by default unless the Human
  explicitly requests a Specification, except task progress and status records, which
  use Progress, and error or Human/AI judgment-difference records, which use Lessons Learned.
  Generation, refinement, format and inferred
  approval grant no such authority. Resolve unclear classification before writing.
- These are the only types. Refined documents retain `document-type: processed` for compatibility, and
  Specification document means Skill document.
  `Original -> Refined -> Specification (Skill)` is optional provenance, never a required pipeline, maturity scale or
  promotion. Preserve actual relationships of any cardinality.

<a id="routing"></a>

## 4. Routing

- Use the [complete project directory map and storage boundaries](references/layout.md)
  when placing or reorganizing `docs/`, including artifact and runtime boundaries.

| Type | Canonical project package |
|---|---|
| Original | `<project-root>/docs/original/<category>[-<domain>]-<name>/` |
| Refined | `<project-root>/docs/refined/<category>/<topic>/` |
| Progress | `<project-root>/docs/progress/<contract-id>/progress.md` catalog index and the execution record in the bound `contract-v<N>.md` |
| Lessons Learned | `<project-root>/docs/lessons-learned/{errors,judgment-differences}/<readable-name>.md` |
| Specification (Skill document) | `<project-root>/docs/skills/<category>[-<domain>]-<name>/` |

<!-- clause-id: specification.routing.canonical -->
- Maintain one editable source. Local storage is complete standalone behavior, not an
  error fallback. Alternative destinations/formats are additional exports.
- Preserve existing Documents unless changes are authorized. Keep disposable execution
  scratch files in run directories. For standalone HTML, SVG, screenshots and other
  non-Document outputs, use Convention's [Artifacts contract](../convention/SKILL.md#artifacts).
- Preserve existing Skills outside managed synchronization. Writing a new document or
  running synchronization does not authorize rewriting, relocating or adopting them.
- Migrate existing documents or Skills into the project document structure only when
  the Human explicitly requests migration. Limit changes to that request, apply the
  relevant document type guide, and preserve source content and unresolved decisions.
  Back up affected content before replacing or moving it; a collision is not migration
  authority. After preparing the authorized `docs/skills/` source and resolving any
  destination collision within that authority, run synchronization and inspect its result.

<a id="document-package"></a>

## 5. Document package

- You MUST write Refined, Progress, Lessons Learned and Specification Documents in the Human's language, or their
  explicitly selected document language. Support any user language; never fix these
  Documents to Korean, English or the language of this guidance.
- Refined/Specification: one entry document `SKILL.md`, optional `references/` for
  detailed Markdown documents, and optional `assets/` for attachments; no `scripts/`
  or `agents/`. Contract Progress uses a `docs/progress/<contract-id>/progress.md`
  catalog index and an execution record in the bound `contract-v<N>.md`, with
  explicitly linked attachments beside them. Original contains one `metadata.yaml` with metadata and links
  only; it stores no copied source body or assets. Installed capability packages are
  outside this document format.
- Keep overview, essential guidance and links to detailed topics in `SKILL.md`.
  Split details into `references/*.md` by coherent topic when a document becomes hard
  to read or maintain; do not impose an arbitrary file-size threshold or duplicate content.
- Every reference document MUST be reachable from `SKILL.md` through explicit relative
  Markdown links. Every asset MUST be referenced by a relative link or image inclusion
  at its point of use in `SKILL.md` or a reachable reference document. Optional folders
  may be absent; existing files must not be left unlinked. A link does not require the
  reader to load every reference for every task.
- The entry document and its linked references form one canonical document package.
  References inherit its document type, language, authority and provenance; splitting
  files does not create a new Specification or an independent competing source.
- Preserve source text, quotes, code and identifiers in content-bearing Refined, Progress, Lessons Learned and
  Specification packages. For Original, preserve metadata and link strings exactly.
  Language choice alone permits no translation or conversion. `SKILL.md` does not
  activate Refined, Progress or Lessons Learned as a Skill.
- Lessons Learned uses a Markdown body and runtime-only machine metadata, with no
  `SKILL.md` or `assets/` wrapper. Follow its type guide for identity, status and history.
- Follow the mandatory [Document structure](#document-structure) for Markdown bodies.
- Body and assets are the editable source, including asset CSV/JSON. Store each diagram,
  system architecture, database/ERD or API design represented as JSON in a separate
  `assets/*.json` file. In `SKILL.md` or a linked reference document, reference it where used with a descriptive relative
  Markdown link such as `[System architecture](assets/system-architecture.json)`; do not
  embed or duplicate the JSON in the Markdown body. Put independent CSV datasets and
  needed images in `assets/` as separate files as well. Any display that expands a linked
  asset remains derived, not an editable peer.
- Do not assume a viewer or renderer is available. Follow [Diagrams](../convention/references/diagrams.md)
  for asset formats and readable text.

<a id="document-structure"></a>

## 6. Document structure

- Use three heading levels only: `# Title`, `## 1. Section`, `### 1.1. Subsection`. The title is
  unnumbered; section and subsection numbers include the trailing period. Split topics
  requiring deeper headings.
- Under sections or subsections, write only bulleted lists, numbered lists, blocks or
  tables. Do not place standalone prose paragraphs there.
- You MUST keep sentences in bulleted and numbered lists concise and precise, using
  technical-document style. State one point per sentence; split long explanations into
  separate items or nested lists. Avoid verbose phrasing.
- A numbered item may contain a bulleted list, and a bulleted item may contain a
  numbered list. Indent child lists to distinguish their nesting level.
- Write tables as Markdown tables.
- Keep ordinary code blocks and images in their native Markdown forms. Store structured
  design JSON as separate linked assets under the [Document package](#document-package)
  contract.

<a id="naming-and-metadata"></a>

## 7. Naming and metadata

- Refined uses the category hierarchy in its type guide; do not repeat category prefixes
  in topic names. Other packages use `<category>-<name>` or `<category>-<domain>-<name>` only for project-defined domains; brackets in routing
  denote optional text. Preserve resolved names and type-guide categories; never infer
  domains or bulk-rename accepted identities.
- For Markdown packages and Original, YAML metadata records `document-type`, `category`, `domain`, `name`, and
  applicable `language`/actual provenance. Undefined domain is `null`. Metadata
  grants no authority.

<a id="installed-capability-boundary"></a>

## 8. Installed capability boundary

- These document rules apply to project documents, not installed capability packages.
- Synchronize only the declared project roots; do not copy or rewrite installed Skills.

<a id="host-sync"></a>

## 9. Host export, synchronization and catalog

- Read [host-sync.md](references/host-sync.md) before exporting or synchronizing `docs/skills/`
  to `.codex/skills/`, `.claude/skills/` and `.agents/skills/`, or cataloging and searching project Documents.

<a id="boundaries"></a>

## 10. Boundaries

- This Skill provides local project document authoring, storage and synchronization.
- Document work does not authorize unrelated migration or deletion.
