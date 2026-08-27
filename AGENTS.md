<agent-factory>
Always load and comply with Agent Factory skills.

Treat Main as the Human-facing adaptive Interview, orchestration, and result
integration layer. Main performs no implementation, research, tests,
verification, recovery, or other executable task work directly. Route research
to a managed Explorer, bounded changes to Work and independent Review, and only
explicitly Human-authorized checks to a separate managed Verification Agent.
Main may attach evidence those actors already produced as a control-plane
record operation. Explorer never impersonates or interviews the Human.

This repository is the Agent Factory plugin. Store this plugin's distributed
Skills below `<plugin-root>/skills/`; do not create or mirror them below this
repository's `.codex/`.

For every separate project that uses this plugin, store that project's
Project Skills below `<project-root>/.codex/skills/`. Keep each Project Skill in
one self-contained directory with `SKILL.md`, YAML Agent configuration in
`agents/`, reference material in `assets/`, Markdown documents in `references/`,
and Agent-usable scripts in `scripts/`.

Use this project-local structure as the current/default local adapter, not as a
universal document-storage requirement:

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
├── specification/
│   ├── common/
│   ├── explorer/
│   └── skills/
└── sync.json
```

Keep operational Agent runtime state in `agent/`, temporary Explorer workspaces
in `explorer/`, and Gather configuration in `sync.json`. Use `information/` for
the three-stage document lifecycle: original, processed, and refined. Store
locally materialized Human refined documents below `information/refined/human/`.
Preserved legacy Inquery artifacts live below
`information/processed/legacy-inquery/`; do not use them as active targets.
Within the local adapter's `specification/`, `common/` owns the shared browser
shell, `explorer/` owns Explorer UI, and `skills/` owns Skill navigation.
Planning reads Human refined documents from `information/refined/human/` rather
than owning a document directory.

A Human refined document must remain semantically aligned with its AI-facing
Skill. This plugin repository's Agent Factory core pair is owned by the
distributed `skills/convention/` Skill. A separate consumer project's pair is
a Project Skill below that project's `.codex/skills/`. Do not create a
standalone Human refined document without its resolved pair.

Information classes and document roles are logical and storage-independent.
An explicitly resolved alternative store, such as a project server, external
document store, mounted filesystem, or configured backend, may replace the
local document adapter while preserving provenance, authority, isolation,
semantic alignment, accessibility, and security. Do not silently choose,
mirror, or migrate a backend. Keep operational Agent runtime state under the
declared local runtime contract unless separately changed. Do not put Project
Skills or gathered source collections below `.agent-factory/`; Gather uses its
resolved destination outside this work root.
</agent-factory>
