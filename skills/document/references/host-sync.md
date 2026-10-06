# Host Export, Synchronization and Catalog

- `<plugin-root>` is the installed Agent Factory plugin directory (two levels above `SKILL.md`).

<a id="explicit-codex-export"></a>

## 1. Explicit host export

| Source | Derived destination |
|---|---|
| `docs/skills/` | `.codex/skills/` (Codex), `.claude/skills/` (Claude Code) and `.agents/skills/` (Antigravity) |

- Only `docs/skills/` is projected. `docs/original/`, `docs/refined/`, `docs/progress/` and `docs/lessons-learned/` remain canonical
  project storage; they require no host export or synchronization. Existing
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

## 2. Agent-invoked host synchronization

- Run `python3 <plugin-root>/scripts/sync_documents.py --project-root <project-root>`
  after creating, modifying or deleting `docs/skills/` packages, using their actual project root.
  Inspect the result; resolve or report conflicts before claiming synchronization succeeded.
- The plugin bundles no automatic hooks. Human edits synchronize only on a subsequent
  explicit invocation; this CLI is not a watcher. The legacy `--hook` entry is removed.
- `docs/skills/` supplies only owned output under `.codex/skills/`, `.claude/skills/` and
  `.agents/skills/`. Each host directory keeps its own `.document-sync/manifest.json` of managed
  paths, directories and SHA-256 hashes. Every run updates all three together: all hosts are
  checked first, and a conflict in any host changes none of them, so the copies never diverge.
  `--check` reports outdated or conflicting hosts without changing anything (exit 1 if any).
  Unrelated destination packages and files are preserved.
- A new package may be created only when its destination does not exist. Existing unowned
  packages conflict even when byte-identical; legacy mirrors and explicit exports are never
  automatically adopted. Missing manifests grant no ownership; malformed manifests fail closed.
- Before any document mutation, all packages are checked for conflicts. Independent edits,
  additions, deletions or type changes in managed packages block the entire invocation.
  Ordinary synchronization does not authorize replacing these edits or adopting unowned files.
- When the Human authorizes recovery using `docs/skills/` as authoritative, invoke the same
  command with `--reconcile`. It backs up affected output and existing control records under
  `<host-directory>/.document-sync/backups/` before rebuilding output and ownership. Inspect the returned
  backup path. Missing or corrupt ownership can recover source-named packages; unrelated
  packages remain untouched. Valid ownership and journals also identify obsolete managed
  packages. Destination-only edits within affected packages are preserved in the backup.
- Legacy explicit exports do not create ownership records. Use synchronization for ongoing
  maintenance; importing a legacy export requires the explicit recovery authorization above.
- Removing a source package removes only its unchanged owned output. An empty source root
  removes only unchanged managed packages; a missing source root is a no-op.
  Other `.codex` content is untouched.
- Symlinks, unsupported files and unsafe manifest paths are rejected. The OS lock at
  `.codex/.document-sync/lock` excludes concurrent sync processes and releases on forced exit.
  Keep its file in place. A legacy lock directory requires confirming no old writer is running
  before manual removal.
- Writes are atomic per file, not across the tree. `pending.json` records previous and planned
  hashes before mutations. Interrupted writes retain this journal and block automatic retry,
  including adoption of partial output. Authorized `--reconcile` validates the journal,
  backs up partial output and finishes synchronization without manually clearing records.
  Invalid journals still require restoring a trusted record; do not delete them to bypass
  a conflict. Source changes during copying leave a recoverable journal instead of success.
- Keep source, destination and state trees stable during invocation. The lock coordinates this
  CLI, not editors or hostile concurrent filesystem writers. Hashes track content and directory
  shape, not permission or timestamp edits. Relative links and file bytes remain unchanged.
- CLI errors return nonzero with an actionable JSON error; report synchronization as incomplete.

<a id="local-document-catalog-and-search"></a>

## 3. Local document catalog and search

- Codex discovers Specification (Skill) packages through its Skill catalog. Original, Refined, Progress and
  Lessons Learned packages use the separate local Document catalog supplied by this Skill.
- Run `<plugin-root>/scripts/catalog_documents.py --project-root <project-root>` to emit a current JSON
  catalog of canonical `docs/original/`, `docs/refined/`, `docs/progress/` and
  `docs/lessons-learned/`, plus legacy `docs/processed/` and root `progress/`. It reads the
  packages on demand and writes no generated index into the project.
- Canonical `docs/progress/<contract-id>/` entries expose the contract ID, latest version, each
  version's task IDs, `progress.md` and explicitly linked attachments. Missing or
  unlinked attachments, filename/metadata mismatches, duplicate canonical/legacy
  identities and the same contract ID in both locations are errors; catalog and search never select one conflicting copy silently.
- Run `<plugin-root>/scripts/search_documents.py --project-root <project-root> --query <text>` to search
  catalog metadata, Original links, Refined/Progress Markdown (including detailed
  Markdown under `references/`) and Lessons Learned Markdown joined with runtime metadata.
  Optional `--type`, `--category`, `--scope` and `--limit` filters narrow results.
- Catalog and search accept `--documents-root <physical-workspace-containing-docs>` while
  `--project-root` retains runtime identity. New category hierarchies and legacy layouts
  are both discovered; duplicate identities fail instead of choosing a copy.
- Search includes every versioned contract and supported text attachment. The `refined`
  type filter is an alias for the compatible `processed` metadata type; both filters
  return canonical Refined and legacy Processed records.
- Catalog and search are read-only discovery operations. They do not activate a
  Refined, Progress or Lessons Learned Document as a Skill, change document authority or index `docs/skills/`.
- Search defaults to the compatible `--match all` (all query substrings, case-insensitive).
  Explicit `--match any` explores partial lexical matches, prioritizing term coverage before
  frequency; it performs no translation or semantic authority inference. `--offset` pages
  through `totalCount` with `nextOffset`, without changing the existing default page size.
- Results add `documentId`, dependency SHA-256 hashes, a package `revision` and matching
  source paths/ATX section anchors. These identify exact sources for caller-side reuse;
  no persistent cache, automatic deduplication or new editable index is created.
- Use the same search CLI with `--read-path <project-relative-path>` instead of `--query`
  to read canonical Document text, or an explicitly selected `docs/skills/` entry/reference.
  `--anchor <HTML-id-or-heading-slug>` selects a section including its children;
  missing/ambiguous anchors fail instead of guessing. Fenced headings are ignored.
  The response retains complete entry guidance, source metadata and dependency hashes.
- Supply the returned `--revision <hash>` when reading to reject stale sources after
  body, reference, attachment or projected status changes. Hashes are rebuilt live;
  no timestamp-only cache can hide edits. There is no atomic multi-file snapshot against
  concurrent editors. A selected section is a discovery aid: read linked mandatory rules,
  decisions and exceptions before acting. Search rank never selects execution authority.
- Managed document-dependent requests can supply `exec.py submit/send --document-context-file <json>`;
  delegated task entries can instead carry the same `documentContext` object. Both are
  captured per request and consumed by `runs/attempt.py` before the existing provider turn.
  They are retrieval requirements, not execution approval, Skill activation or persistent session settings.
- The object accepts `query`, exact `scope`, explicit `allowPartial`/`discoverScopes` booleans,
  and `required`/`selections` lists of `{path, anchor?, revision?}` canonical sources.
  Supply mandatory rules, Human decisions and exceptions in `required` independently of
  query ranking. A conflicting task/CLI object is rejected. With no object, normal requests
  perform no extra Document reads. Empty objects and unsafe paths are rejected.
- Retrieval searches all pages with `all`, tries `any` only on a miss with `allowPartial`,
  and explores other scopes only on a miss with `discoverScopes`. Cross-scope results retain
  scope/status and `discoveryOnly`; discovery never grants applicability or authority.
  Narrow matching sections retain complete entry text. Explicit mandatory/exception links
  are followed recursively; ordinary references stay unloaded and listed as unassessed.
  The cue recognizer is conservative, not a semantic completeness proof. Unselected sections,
  external links and unclear dependencies stay visible; resolve required gaps by canonical
  reading before acting. Missing required sources and stale explicit revisions block preparation.
- Run status exposes `documentContext` and per-attempt `documentContextAttempts`: search
  misses/failures, requeries, repeated path reads, sections, revisions, hashes, read latencies,
  snapshot file bytes and delivered JSON bytes. Snapshot bytes exclude catalog parsing I/O;
  `catalogReadBytes`, model input tokens, token estimates and document-cache counters are
  unavailable (`null`). `modelUsageJoin` links the same run/attempt to existing `usageAttempts`
  and `tokenUsage`; reported provider usage is not attributed to individual Document tokens.
  No extra model call, persistent cache or copied editable source is created.
- Reject malformed metadata, duplicate identities, links, unsupported package content
  and symlinks instead of silently omitting them from discovery.


<a id="document-layout-migration"></a>

## 4. Document layout migration

- Run `python3 <plugin-root>/scripts/migrate_document_paths.py --project-root <original-project>
  --documents-root <physical-workspace-containing-docs> --storage-layout` for a read-only
  dry-run. Inspect `moves`, `conflicts`, `unclassified`, `excluded` and `languages`.
- A physical workspace contains `docs/`; for a docs repository worktree at
  `<worktree-workspace>/docs`, pass `<worktree-workspace>` as `--documents-root`.
  Runtime identity remains the original registered project, not that temporary worktree.
- Select lesson body language explicitly with `--language <tag>` when it differs from
  legacy record language. The source language and quoted original text remain preserved;
  this does not translate historical prose or change Refined package languages. Without
  this option, document languages are retained. Dry-run separates source/body language counts.
- For ambiguous Refined packages, inspect the body and supply `--classifications <json>`
  mapping project-relative source package paths to `analysis`, `research`, `interview`,
  `comparison` or `history`. Classification changes metadata only, preserves prior category
  evidence and never rewrites historical content into current rules.
- Preserve pre-existing dirty/untracked content with repeated `--exclude-path <relative-path>`.
  Excluding a member preserves its whole moving package. Review incoming links in excluded
  content separately; migration never changes those files.
- Only explicit migration authorization permits apply and source retirement. Add
  `--apply --backup-dir <authorized-outside-workspace-backup>` after resolving conflicts
  and unclassified packages. The backup holds exact source/target bytes, hashes and mapping.
- Backups may use an existing run's storage below its `agents/<agent>/runs/<run>/`
  directory, or another authorized location outside the physical document workspace.
  Runtime control and lesson metadata directories are not backup destinations.
- Verify all output hashes and complete lesson history round trips before removing old files.
  Attachments and empty package directories are preserved. Local Markdown links in entries,
  references and incoming project documents follow moved targets.
- Retry with the same backup after a partial failure. The manifest permits only its original
  and expected bytes; changed sources, independently edited targets, duplicate identities
  and existing unowned destinations require reconciliation, never silent replacement.
- After apply, run catalog and scoped search with the same two roots, inspect language,
  body meaning, links and history, and retain the backup as restoration evidence.
  Refined never needs host synchronization. Synchronize only affected Specification sources
  through the existing host contract; this migration does not authorize host overwrite.
- Without `--storage-layout`, the existing contract-listed `--operations` preview/backup/apply
  interface remains available; `--documents-root` selects its physical file workspace too.
  No separate README catalog, database or document system is created.
- Scribe uses the guard's own `<plugin-root>/scripts/migrate_document_paths.py` for authorized
  contract-listed moves. Pass literal captured `--project-root` and `--documents-root`, plus
  `--operations <CSV>` inside `docs/` or the current run. Each selected source and destination
  must remain inside the captured document write root; symlinks and overlapping endpoints fail.
- Preview returns source and expected destination SHA-256 hashes, including intentional link
  adjustments. Run `--backup`, then `--apply` with the same
  `--backup-dir <current-run>/document-backups/<name>`. Apply requires the completed matching
  manifest and verified bytes. Re-run preview with that backup to check completed moves.
  Backup data cannot replace run control records, use another run or escape through symlinks.
- Scribe's CLI checks its captured scope again at execution; a hook decision does not bind
  mutable CSV contents. Arbitrary shell/code execution and `--storage-layout` remain forbidden
  for Scribe. These capabilities grant no new migration, directory creation or draft acceptance
  authority. Storage-layout changes that update runtime lesson metadata use an authorized Work.
