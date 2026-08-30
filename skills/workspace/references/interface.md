# Workspace Interface

## Human control tower

Workspace uses a developer-familiar VS Code-shaped shell whose primary spatial
relationship is `Activity Bar -> Primary Sidebar -> Workspace`. It presents
project state for Human navigation and control without becoming the canonical
store or executor for the state it may later project.

Keep common layout, interaction, and visual tokens in
`.agent-factory/workspace/common/`. The Activity Bar contains exactly these
five top-level items, in this order, with these Korean labels:

1. 일정
2. 에이전트
3. 문서
4. 로그
5. 테스트

No other top-level item is allowed. In particular, do not add separate
Explorer/File Explorer, Planning/Specification, Project Skills,
overview/dashboard, Roadmap, or alias buttons.

One Activity Bar item owns one corresponding Primary Sidebar view and one main
Workspace view. The Document sidebar contains three prominent, independently
collapsible explorer-like groups in this order: `원본문서`, `가공문서`, and
`스펙문서`. Original provides `개요` and `문서검색`; the search item selects a
compact semantic table view with no top tab bar. It uses the locally vendored,
exactly pinned Tabulator 6.5.2 distribution for sorting, column resize/reorder,
global text search, and filters on every column. Its exact visible order and
labels are `문서 분류`, `출처`, `태그`, `문서 이름`, `확장자`, `수정 일자`.
Tabulator's `fitColumns` layout distributes the ordinary desktop table width
across all six columns with explicit content-appropriate `widthGrow` weights,
while per-column minimum widths and the table's minimum width preserve
horizontal overflow when the viewport is genuinely narrow. Keep manual column
resizing and movement enabled.
The `문서 이름` header is plain text; each populated name cell is the source
link. `출처` shows decorative inline SVG plus visible provider text so color is
never the only distinction. Processed and Specification each provide
`개요` and visually and semantically consistent explorer/tree-shaped regions
for actual Documents. The UI spelling is exactly `스펙문서`, while the
semantic type remains Specification.

The Original search table is a read-only metadata and source-link projection.
It does not copy, normalize, or edit Original bodies, and it does not own or
trigger Gather synchronization. No live browser query/API/source adapter,
synchronization trigger or status contract, or metadata edit authority and
persistence has been accepted. The browser therefore starts in the truthful
`데이터 연결 대기` state without sample records and exposes only
`window.agentFactoryWorkspace.originalSearch.replaceRows(rows)` for a future
owner-backed loader. Rows carry `classification`, `provider`, `tags`, `name`,
`extension`, `modifiedAt`, `sourceUrl`, and stable `sourceIdentity` fields.
Unsafe URL schemes are not linked; external HTTP(S) links use appropriate
opener/referrer isolation. Global search treats input only as literal text
matched against the six displayed fields. The implemented bounded catalog
search CLI does not connect this table. Original overview details and the other
four Activity sidebars and their detailed capabilities
remain Human-owned and undecided and must say so. Existing server/discovery
utilities do not authorize a top-level Activity or a data integration beyond
this decided Document view shape.
The Original overview content uses the compact workspace inset directly,
without an editor header. The Document Sidebar's terminal Specification group
has no trailing bottom divider below its unresolved connection message;
separators between the three groups remain. These chrome decisions do not
resolve the overview's contents.

Use actual SVG for every user-facing icon. Preserve semantic HTML, keyboard
access, visible focus, readable contrast, responsive behavior, and usable
baseline content without JavaScript.

## Packaged assets and initialization

Workspace browser code has two required forms:

- `skills/workspace/assets/browser/{index.html,styles.css,app.js}` is the
  reusable distribution and installation source for this and other projects;
- `<project-root>/.agent-factory/workspace/common/{index.html,styles.css,app.js}`
  is that exact target project's installed, published copy.

These are the three core browser-code files. Create and maintain all three in
both forms together and byte-identically. A required packaged companion asset
must follow the same two-form publication contract. The current
`THIRD_PARTY_NOTICES.txt` provides attribution and license text for browser
code, including the pinned Tabulator files below `vendor/tabulator/6.5.2/`.
The initializer recursively copies all packaged regular files. Every vendored
file and the notice must remain byte-identical to its counterpart in `common/`;
the notice is not a fourth browser-code file. A missing form, a one-sided
change, or semantic or byte divergence is an incomplete Workspace change. This
does not create two canonical sources: the packaged assets are the reusable
installation source and `common/` is the materialized project copy.

The standard-library-only initializer is `skills/workspace/scripts/serve.py`.
Initialize an exact target Git root with:

```bash
python3 <resolved-workspace-skill>/scripts/serve.py \\
  --project-root <target-git-root> init
```

Initialization installs common assets into
`<target-git-root>/.agent-factory/workspace/common/`, preserves the current
local adapter's required directories, ensures the Human Specification and
Document roots exist, and copies `assets/workspace.sh` to
`<target-git-root>/workspace.sh` once. Preserve an existing root launcher even
when `init --force` is used; force applies only to differing common browser
assets. Without force, a differing installed browser file is a preflight
conflict; with force, only differing regular common browser files are replaced
from the packaged source. Existing path-containment, symlink, atomic-copy, and
combined-preflight safeguards remain mandatory.
Initialization also installs `assets/workspace.gitignore` as
`.agent-factory/workspace/.gitignore` when absent. An existing regular ignore
file must already contain the exact `/port.json` rule; unsafe or conflicting
paths fail preflight and are never overwritten.

For normal Human use:

```bash
<project-root>/workspace.sh
# or, from the project root
./workspace.sh --port 9000
```

The launcher resolves its own physical location, serves only its allowlisted
local roots on loopback, and opens `/common/`. With no port option, it reuses
the project's valid saved assignment or asks the operating system for an
actually available port, explicitly excluding `8000`. It publishes the
successfully bound assignment atomically as the small generated local state
`<project-root>/.agent-factory/workspace/port.json` with the exact shape
`{"version":1,"port":<port>}`. If a saved port is occupied, the launcher binds
another available non-`8000` port before replacing the assignment. `--port
<port>` or `-p <port>` accepts only 1 through 65535, rejects `8000`, and saves a
successful explicit bind for later launches. Malformed, out-of-range,
symlinked, non-regular, or escaping state fails closed; state publication uses
path containment checks, symlink rejection, and atomic replacement. The state
file is generated per-project adapter state, is ignored by Git, and is not a
packaged browser asset or a universal backend contract.

## Storage and authority boundary

The local Workspace UI is a projection and control surface. Visibility does
not imply acceptance, health, completion, or authority. Agent sessions,
Original/Processed/Specification Documents, Project Skills, and Human decisions
retain their owning stores and rules.

The exact local catalog at `<project-root>/.agent-factory/db.sqlite`, its
schema, manager, initialization, rebuild, status, searches, publication and
recovery are Agent-owned. Workspace does not invoke those operations, and
`serve.py init` has no catalog side effect. Workspace has no catalog/search UI,
query API, or search executor. It may later present read-only results supplied
through an explicit Agent-owned interface, but that possibility does not
authorize direct database access, a source/query binding, Activity behavior,
or any transfer of Agent, Document, or catalog ownership. Apply the detailed
catalog contract only from `skills/agent/SKILL.md`.

A server-hosted Workspace is exposed by its selected host or adapter and does
not require the local launcher. Backend configuration, identity,
synchronization/conflict policy, authentication, availability, and caching
remain unresolved until explicitly decided.
