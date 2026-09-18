---
name: document
description: Write, revise, consolidate, convert, classify, store, catalog, search, or synchronize Agent Factory Documents using mandatory writing and single-source rules.
metadata:
  specification-id: document
---

# Agent Factory Document

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
  past discussions and superseded decisions in Processed documents. Preserve source
  evidence in Original documents.
- After creating or updating any package under `docs/skills/`,
  you MUST directly run the [synchronization script](#continuous-codex-synchronization) for that document's project and check its result
  before reporting completion.
  - Hook configuration or an expected future hook run does not satisfy this requirement.
  - Report failed or conflicted synchronization as incomplete; do not claim completion.

<a id="writing-guides"></a>

## 2. Writing guides

- `references/specification.md`: write accepted facts, rules and designs.
- `references/processed.md`: write analysis and working knowledge.
- `references/original.md`: preserve source evidence and metadata.
- Read only the guides for the types involved. Use [Convention](../convention/SKILL.md) for shared development,
  themes, diagrams and interviews; [Agent](../agent/SKILL.md) for managed execution, not this Skill.

<a id="types-and-authority"></a>

## 3. Types and authority

| Type | Meaning |
|---|---|
| Original | Source-faithful metadata and links identifying external evidence. |
| Processed | Transformed, non-authoritative working knowledge. |
| Skill document (Specification) | Project knowledge explicitly requested as a Specification by the Human. |

- Every AI-generated durable Document is Processed by default unless the Human
  explicitly requests a Specification. Generation, refinement, format and inferred
  approval grant no such authority. Resolve unclear classification before writing.
- These are the only types; Refined and Specification categories add no type.
  `Original -> Processed -> Specification` is optional provenance, never a required pipeline, maturity scale or
  promotion. Preserve actual relationships of any cardinality.

<a id="routing"></a>

## 4. Routing

| Type | Canonical project package |
|---|---|
| Original | `<project-root>/docs/original/<category>[-<domain>]-<name>/` |
| Processed | `<project-root>/docs/processed/<category>[-<domain>]-<name>/` |
| Skill document | `<project-root>/docs/skills/<category>[-<domain>]-<name>/` |

<!-- clause-id: specification.routing.canonical -->
- Maintain one editable source. Local storage is complete standalone behavior, not an
  error fallback. Alternative destinations/formats are additional exports.
- Preserve existing Documents unless changes are authorized. Keep temporary artifacts in
  run directories.

<a id="document-package"></a>

## 5. Document package

- You MUST write Processed and Specification Documents in the Human's language, or their
  explicitly selected document language. Support any user language; never fix these
  Documents to Korean, English or the language of this guidance.
- Processed/Specification: one `SKILL.md` plus optional `assets/`; no `references/`,
  `scripts/` or `agents/`. Original contains one `metadata.yaml` with metadata and links
  only; it stores no copied source body or assets. Installed capability packages are
  outside this document format.
- Preserve source text, quotes, code and identifiers in content-bearing Processed and
  Specification packages. For Original, preserve metadata and link strings exactly.
  Language choice alone permits no translation or conversion. `SKILL.md` does not
  activate Processed as a Skill.
- Follow the mandatory [Document structure](#document-structure) for the body.
- Body and assets are the editable source, including asset CSV/JSON. Store each diagram,
  system architecture, database/ERD or API design represented as JSON in a separate
  `assets/*.json` file. In `SKILL.md`, reference it where used with a descriptive relative
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

- Use `<category>-<name>` or `<category>-<domain>-<name>` only for project-defined domains; brackets in routing
  denote optional text. Preserve resolved names and type-guide categories; never infer
  domains or bulk-rename accepted identities.
- YAML metadata records `document-type`, `category`, `domain`, `name`, and
  applicable `language`/actual provenance. Undefined domain is `null`. Metadata
  grants no authority.

<a id="installed-capability-boundary"></a>

## 8. Installed capability boundary

- These document rules apply to project documents, not installed capability packages.
- Synchronize only the declared project roots; do not copy or rewrite installed Skills.

<a id="explicit-codex-export"></a>

## 9. Explicit Codex export

| Source | Derived destination |
|---|---|
| `docs/skills/` | `.codex/skills/` |

- Only `docs/skills/` is projected. `docs/original/` and `docs/processed/` remain canonical
  project storage; they require no Codex export or synchronization. Existing
  `.codex/original/` and `.codex/processed/` content is left untouched.
- Run `scripts/export_documents.py --project-root <project-root>` to preview; add `--apply` to copy. A missing `docs/skills/` root is an empty
  input; children must be packages with `SKILL.md`.
  Installed capability packages are excluded.
- Preserve names, bytes, assets, empty directories and metadata. Identical copies stay
  unchanged; preflight rejects conflicts, symlinks and unsupported files. Export never
  overwrites, merges or deletes and does not continuously synchronize.
- Keep trees stable; links are copied verbatim, so review external package links.
  Multi-package copying is not atomic; inspect partial copies/errors before retrying.

<a id="continuous-codex-synchronization"></a>

## 10. Continuous Codex synchronization

- `docs/skills/` is authoritative for `.codex/skills/`, the only synchronized root.
  Overwrite differing destination content and remove destination-only files/directories
  within that active mapped root. Do not merge or protect independent edits there.
- A missing source root is skipped; an existing empty source root clears its mapped
  destination. Other `.codex` content, such as configuration and hooks, is untouched.
- Run `python3 <plugin-root>/skills/document/scripts/sync_documents.py --project-root <project-root>` using the document's actual project root. Inspect the result; rerun
  after further edits.
- Synchronization uses no recorded content hashes or conflict resolution. It compares
  current files, rejects symlinks/unsupported files and serializes runs with
  `.codex/.document-sync/lock`. Remove a stale lock only after confirming no sync is running.
- File writes are atomic; a multi-file sync is not. Hold source trees stable and rerun
  after I/O failures to finish. Relative links and metadata are copied unchanged.
- `hooks/hooks.json` invokes `--hook` on `PostToolUse` and `Stop` using the event's
  absolute `cwd`, never an ancestor. Projects without `docs/skills/` are a no-op.
  It is not a watcher; outside edits wait for
  the next event. Hooks require trust and an installed configuration.
- Hook errors emit `systemMessage` without blocking/re-triggering Stop; CLI errors return
  nonzero. See the [hook contract](https://learn.chatgpt.com/docs/hooks).

<a id="local-document-catalog-and-search"></a>

## 11. Local document catalog and search

- Codex discovers Specification packages through its Skill catalog. Original and
  Processed packages use the separate local Document catalog supplied by this Skill.
- Run `scripts/catalog_documents.py --project-root <project-root>` to emit a current JSON
  catalog of `docs/original/` and `docs/processed/`. It reads the canonical packages on
  demand and writes no generated index into the project.
- Run `scripts/search_documents.py --project-root <project-root> --query <text>` to search
  catalog metadata, Original links and Processed Markdown. Optional `--type`,
  `--category` and `--limit` filters narrow results.
- Catalog and search are read-only discovery operations. They do not activate a
  Processed Document as a Skill, change document authority or index `docs/skills/`.
- Reject malformed metadata, duplicate identities, links, unsupported package content
  and symlinks instead of silently omitting them from discovery.

<a id="boundaries"></a>

## 12. Boundaries

- This Skill provides local project document authoring, storage and synchronization.
- Document work does not authorize unrelated migration or deletion.
