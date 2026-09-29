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
  Markdown under `references/`) and Lessons Learned JSON. Optional `--type`,
  `--category` and `--limit` filters narrow results.
- Search includes every versioned contract and supported text attachment. The `refined`
  type filter is an alias for the compatible `processed` metadata type; both filters
  return canonical Refined and legacy Processed records.
- Catalog and search are read-only discovery operations. They do not activate a
  Refined, Progress or Lessons Learned Document as a Skill, change document authority or index `docs/skills/`.
- Reject malformed metadata, duplicate identities, links, unsupported package content
  and symlinks instead of silently omitting them from discovery.
