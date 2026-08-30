# Workspace Interface

## Human control tower

Workspace uses a developer-familiar VS Code-shaped shell whose primary spatial
relationship is `Activity Bar -> Primary Sidebar -> Workspace`. It presents
project state for Human navigation and control without becoming the canonical
store for Agent runtime state, source collections, or Specifications.

Keep common layout, interaction, and visual tokens in
`.agent-factory/workspace/common/`. Provide these default Activity views:

- `.agent-factory/workspace/explorer/` presents the read-only File/Project
  Explorer Activity. It separately labels the project tree and temporary
  Work/Explorer evidence discovered below `.agent-factory/explorer/`;
- Planning presents Human-facing Specifications from
  `.agent-factory/information/refined/human/`;
- `skills/` presents discovered Project Skill navigation and views.

One Activity Bar item owns one corresponding view. Treat the Primary Sidebar
as the contextual companion to the selected Activity and main Workspace, not
as a document table of contents. A document-specific table of contents belongs
inside that document's Workspace presentation.

Display only resources that actually exist. Project Skill navigation mirrors
the actual hierarchy below `<project-root>/.codex/skills/`; it must not copy or
hardcode Project Skill content into the control tower. Use actual SVG for every
user-facing icon and preserve semantic HTML, keyboard access, visible focus,
readable contrast, and responsive behavior.

The Explorer Activity is a bounded metadata projection, not a file service or
storage owner. Do not expose file contents or operational Agent state. Reject
traversal and symlink escape, omit sensitive control/runtime paths from the
project tree, and impose deterministic depth, entry-count, and response-size
limits. Show explicit missing, empty, truncated, and error states. The Activity
must not copy, edit, move, delete, or promote temporary Explorer evidence.

## Packaged assets and initialization

The reusable shell is packaged below `skills/workspace/assets/browser/` and the
standard-library-only initializer is `skills/workspace/scripts/serve.py`.
Initialize an exact target Git root with:

```bash
python3 <resolved-workspace-skill>/scripts/serve.py \
  --project-root <target-git-root> init
```

Initialization installs common assets into
`<target-git-root>/.agent-factory/workspace/common/`, creates the `explorer/`
and `skills/` Activity directories, ensures the Human Specification root exists, and
copies `assets/workspace.sh` to `<target-git-root>/workspace.sh` once. Preserve
an existing root launcher even when `init --force` is used; force applies only
to differing common browser assets.

For normal Human use:

```bash
<project-root>/workspace.sh
# or, from the project root
./workspace.sh --port 9000
```

The launcher resolves its own physical location, serves only the allowlisted
Workspace UI and Human Specification roots on loopback, and opens `/common/`.
`--port <port>` or `-p <port>` overrides the default port `8000`.

## Storage and authority boundary

The local Workspace UI is a projection and control surface. It must not claim
that displayed data is accepted merely because it is visible. Agent sessions,
temporary Work/Explorer evidence workspaces, Original/Processed/Specification Documents, Project Skills,
and Human decisions retain their owning stores and authority rules.

A server-hosted Workspace is exposed by its selected host or adapter and does
not require the local launcher. Backend configuration, identity,
synchronization/conflict policy, authentication, availability, and caching
remain unresolved until explicitly decided.
