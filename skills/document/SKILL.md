---
name: document
description: Write, revise, consolidate, convert, classify, store, or synchronize Agent Factory Documents using mandatory writing and single-source rules.
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
- After creating or updating any package under `docs/original/`, `docs/processed/` or `docs/skills/`,
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
| Original | Source-faithful evidence in a source-appropriate format. |
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

| Type | Canonical Client package |
|---|---|
| Original | `<project-root>/docs/original/<category>[-<domain>]-<name>/` |
| Processed | `<project-root>/docs/processed/<category>[-<domain>]-<name>/` |
| Skill document | `<project-root>/docs/skills/<category>[-<domain>]-<name>/` |

<!-- clause-id: specification.routing.canonical -->
- Maintain one editable source. Local storage is complete standalone behavior, not an
  error fallback. Alternative destinations/formats are additional exports.
- Preserve existing Documents unless changes are authorized. Keep temporary artifacts in
  run directories and Provider instructions in their owning `skills/` packages.

<a id="document-package"></a>

## 5. Document package

- You MUST write Processed and Specification Documents in the Human's language, or their
  explicitly selected document language. Support any user language; never fix these
  Documents to Korean, English or the language of this guidance.
- Processed/Specification: one `SKILL.md` plus optional `assets/`; no `references/`,
  `scripts/` or `agents/`. Original retains its native/source-appropriate format;
  Provider Skills are exempt.
- Preserve source text, quotes, code and identifiers. Language choice alone permits no
  translation or conversion. `SKILL.md` does not activate Processed as a Skill.
- Follow the mandatory [Document structure](#document-structure) for the body.
- Body and assets are the editable source, including asset CSV/JSON. Put independent CSV
  datasets, Archify diagram JSON and needed images in `assets/`; link relatively where
  used. Displays expand assets in place and remain derived, not editable peers.
- Viewer, Archify rendering and ERD are unimplemented follow-up work; no external
  installation is authorized. See [Diagrams](../convention/references/diagrams.md).

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
- Represent blocks such as code blocks, images and diagrams as JSON.

<a id="naming-and-metadata"></a>

## 7. Naming and metadata

- Use `<category>-<name>` or `<category>-<domain>-<name>` only for project-defined domains; brackets in routing
  denote optional text. Preserve resolved names and type-guide categories; never infer
  domains or bulk-rename accepted identities.
- YAML metadata records `document-type`, `category`, `domain`, `name`, and
  applicable `language`/actual provenance. Undefined domain is `null`. Metadata
  grants no authority.

<a id="provider-placement"></a>

## 8. Provider placement

- Provider execution guidance stays in English under `<plugin-root>/skills/`, with `agent`,
  `convention`, `document`, YAML metadata and owned package components intact.
- Do not create parallel Provider Specifications under `docs/skills/` or `.codex/skills/`, or
  migrate Provider Skills as Client Documents.
- Human-requested durable Provider Original/Processed use the Client roots with the
  plugin as project root; Provider Processed remains non-authoritative and Git-ignored.
  Otherwise retain evidence at its source or in temporary state.

<a id="explicit-codex-export"></a>

## 9. Explicit Codex export

| Source | Derived destination |
|---|---|
| `docs/original/` | `.codex/original/` |
| `docs/processed/` | `.codex/processed/` |
| `docs/skills/` | `.codex/skills/` |

- Run `scripts/export_documents.py --project-root <project-root>` to preview; add `--apply` to copy. Missing type roots are empty
  inputs; children must be packages, with `SKILL.md` for Processed/Specification.
  Provider Skills are excluded.
- Preserve names, bytes, assets, empty directories and metadata. Identical copies stay
  unchanged; preflight rejects conflicts, symlinks and unsupported files. Export never
  overwrites, merges or deletes and does not continuously synchronize.
- Keep trees stable; links are copied verbatim, so review external package links.
  Multi-package copying is not atomic; inspect partial copies/errors before retrying.

<a id="continuous-codex-synchronization"></a>

## 10. Continuous Codex synchronization

- `docs` is authoritative: `original`, `processed` and `skills` map to the same
  directory names under `.codex`. Overwrite differing destination content and remove
  destination-only files/directories within each active mapped root. Do not merge or
  protect independent edits in these derived directories.
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
  absolute `cwd`, never an ancestor. It is not a watcher; outside edits wait for
  the next event. Hooks require trust; source edits do not update installed plugins.
- Hook errors emit `systemMessage` without blocking/re-triggering Stop; CLI errors return
  nonzero. See the [hook contract](https://learn.chatgpt.com/docs/hooks).

<a id="boundaries"></a>

## 11. Boundaries

- This Skill implements local document operations, not a cloud receiver, cloud
  migration, upload or MCP service. Connected operations require an available,
  authorized capability. The following contracts describe future implementation.

<a id="future-connected-storage-and-migration"></a>

## 12. Future connected storage and migration

<!-- clause-id: document.future-mcp.cutover -->
- The cloud Document MCP receiver and migration system described here does not yet
  exist.
  - Actual cutover requires that future capability, an available authorized Agent
    Factory cloud Document MCP connection, and an explicitly resolved target
    workspace/project destination.
  - A connection without that destination fails closed; never infer an upload target.
- Before cutover, enumerate the complete bounded inventory under `<project-root>/docs/original/`,
  `<project-root>/docs/processed/`, and `<project-root>/docs/skills/`. Migrate every existing local Document while preserving
  type, identity, provenance, content-presence, and each Document's single source,
  assets and existing derivation provenance. Use stable idempotency identifiers and
  verify receiver acknowledgements, integrity, and source-to-destination mappings.
- Report cutover only after the complete bounded inventory succeeds. Partial or
  ambiguous failure remains pending and retains recoverable local data; retry must be
  idempotent and no automatic deletion is permitted.
- After verified cutover, subsequent durable Documents use the resolved MCP destination
  as authoritative storage under its then-current authenticated contract. Do not
  silently fall back to local authoritative storage after that destination has been
  selected; report failures instead.

<a id="dual-storage-mode"></a>

### 12.1. Dual-storage mode

<!-- clause-id: document.future-mcp.dual-storage -->
- If the Human explicitly requests both canonical local storage and the future cloud
  Document MCP storage, use dual-storage mode. This is a future contract only: the cloud
  receiver, migration system, and dual-storage execution path are not currently
  implemented.
- For every create or update, first mutate the authoritative MCP Document at its
  resolved target using the expected revision/CAS and idempotency contract.
  - Only after its acknowledgement succeeds, fetch the committed MCP revision and
    synchronize the received content and metadata to the canonical local package.
  - Derive the local projection from that MCP-confirmed revision, never independently
    from proposed input.
- Never write local first, perform concurrent bidirectional writes, or silently merge
  divergent local and MCP state. If the MCP mutation fails or its outcome is ambiguous,
  do not mutate the local projection.
- If the MCP mutation succeeds but local projection fails, MCP remains authoritative and
  local is explicitly stale and pending retry. Retry projection from that same MCP
  revision without replaying the MCP mutation.
- For Processed and Specification, project the MCP-confirmed revision to the canonical
  user-language `SKILL.md` and optional `assets/` package. Any display or Skill
  exposure derives from that same source, never a separately edited pair.
- Initial cutover into dual-storage mode imports each local Document to MCP, confirms
  its committed revision, and then re-projects that confirmed MCP state to local.
  Conflicting pre-existing MCP and local revisions require Human resolution; never
  choose authority by timestamps.
