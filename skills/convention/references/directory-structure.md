# Recommended Directory Structure

Use this structure as Agent Factory's current/default local adapter:

```text
<project-root>/.agent-factory/
├── agent/
│   └── <agent-id>/
│       ├── session.json
│       └── runs/
│           └── <run-id>/
├── explorer/
│   └── <exploration-id>/
├── information/
│   ├── original/
│   ├── processed/
│   └── refined/
│       └── human/
├── workspace/
│   ├── common/
│   ├── explorer/
│   └── skills/
└── sync.json
```

## Ownership

- `agent/` owns operational Agent sessions and run records.
- `.agent-factory/explorer/` owns temporary Work/Explorer evidence workspaces.
- `information/` owns the local adapter roots for the three loosely related
  active Document types: Original, Processed, and Specification. Preserve
  Original Documents in diverse native or
  source-appropriate formats. Write active Processed Documents as Markdown
  (`.md`) under this local adapter, but
  do not use preserved `information/processed/legacy-inquery/` material as an
  active target or format precedent. Put locally materialized Human-facing
  Specifications in `information/refined/human/`; the path name
  does not define Refined as a fourth active type. The roots do
  not impose a pipeline, transition sequence, maturity scale, or mapping
  cardinality among Documents.
- `workspace/` owns the local Human control-tower projection. `common/` holds
  the shared browser shell, `.agent-factory/workspace/explorer/` holds the
  read-only File/Project Explorer Activity projection, and `skills/` holds
  Project Skill navigation. The Explorer Activity discovers the project tree
  and the distinct temporary evidence tree; it does not copy or own either.
- `sync.json` holds Gather configuration, not gathered source collections.

Keep plugin distributed Skills below `<plugin-root>/skills/`. In a separate
consumer project, keep Project Skills below
`<project-root>/.codex/skills/<category>-<name>/`. Neither belongs below
`.agent-factory/`, and Gather writes source collections only to its explicitly
resolved destination outside this work root.

This layout is a local adapter, not a universal storage requirement. An
explicitly selected project server or external document store may replace a
document root while preserving provenance, authority, isolation, semantic
alignment, accessibility, and security. Do not silently choose, mirror, or
migrate a backend. Keep Agent runtime state under the declared local runtime
contract unless that contract is separately changed.

Directory layouts outside this Agent Factory adapter remain technology- and
distribution-specific. For example, Python's official packaging guide presents
`src` and flat layouts as alternatives with different import and installation
tradeoffs rather than one universal tree. Follow the owning ecosystem's
official layout guidance instead of projecting this adapter onto application
source code:

- [Python Packaging User Guide: src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
