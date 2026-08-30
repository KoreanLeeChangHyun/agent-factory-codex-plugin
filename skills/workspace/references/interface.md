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
Workspace view. The Human has not yet decided the sidebar information
architecture or detailed capabilities for any Activity. Each packaged view must
therefore say that its configuration is awaiting Human definition, without
invented controls, metrics, source contracts, internal hierarchy, or sample
project state. Existing server/discovery utilities do not authorize a visible
Activity, a nested destination, or a future information architecture.

Use actual SVG for every user-facing icon. Preserve semantic HTML, keyboard
access, visible focus, readable contrast, responsive behavior, and usable
baseline content without JavaScript.

## Packaged assets and initialization

Workspace browser code has two required forms:

- `skills/workspace/assets/browser/{index.html,styles.css,app.js}` is the
  reusable distribution and installation source for this and other projects;
- `<project-root>/.agent-factory/workspace/common/{index.html,styles.css,app.js}`
  is that exact target project's installed, published copy.

Create and maintain all three files in both forms together and byte-identically.
A missing form, a one-sided change, or semantic or byte divergence is an
incomplete Workspace change. This does not create two canonical sources: the
packaged files are the reusable installation source and `common/` is the
materialized project copy.

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

For normal Human use:

```bash
<project-root>/workspace.sh
# or, from the project root
./workspace.sh --port 9000
```

The launcher resolves its own physical location, serves only its allowlisted
local roots on loopback, and opens `/common/`. `--port <port>` or `-p <port>`
overrides the default port `8000`.

## Storage and authority boundary

The local Workspace UI is a projection and control surface. Visibility does
not imply acceptance, health, completion, or authority. Agent sessions,
Original/Processed/Specification Documents, Project Skills, and Human decisions
retain their owning stores and rules.

The exact future local catalog path is
`<project-root>/.agent-factory/db.sqlite`. Its maintained standard SQLite DDL is
`skills/workspace/assets/schema/catalog.sql`. The schema is an idempotent,
versioned foundation for a rebuildable, non-authoritative projection. The
schema asset alone does not authorize database creation, scanning,
rebuild/index jobs, runtime dual writes, screens, APIs, navigation, search, or
any Activity information architecture.

A server-hosted Workspace is exposed by its selected host or adapter and does
not require the local launcher. Backend configuration, identity,
synchronization/conflict policy, authentication, availability, and caching
remain unresolved until explicitly decided.
