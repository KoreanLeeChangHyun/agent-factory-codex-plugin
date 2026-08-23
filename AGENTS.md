<agent-factory>
Always load and comply with Agent Factory skills.

This repository is the Agent Factory plugin. Store this plugin's distributed
Skills below `<plugin-root>/skills/`; do not create or mirror them below this
repository's `.codex/`.

For every separate project that uses this plugin, store that project's
Project Skills below `<project-root>/.codex/skills/`. Keep each Project Skill in
one self-contained directory with `SKILL.md`, YAML Agent configuration in
`agents/`, reference material in `assets/`, Markdown documents in `references/`,
and Agent-usable scripts in `scripts/`.

Use this project-local Agent Factory work structure:

```text
<project-root>/.agent-factory/
├── agent/
│   └── <agent-id>/
│       ├── session.json
│       └── runs/
│           └── <run-id>/
├── inquery/
│   └── <inquiry-id>/
├── specification/
│   ├── common/
│   ├── explorer/
│   ├── planning/
│   │   └── <specification-id>/
│   ├── skills/
│   └── candidate/
└── sync.json
```

Keep operational Agent runtime state in `agent/`, temporary Inquiry workspaces
in `inquery/`, and Gather configuration in `sync.json`. Within
`specification/`, `common/` owns the shared browser shell and each Activity Bar
item owns one directory: Explorer in `explorer/`, Planning in `planning/`,
Skills in `skills/`, and Candidate (Inquery) in `candidate/`. Each Planning
document below `planning/` must identify and remain semantically aligned with a
paired Project Skill below `.codex/skills/`; do not create a standalone Planning
document without that pair. Do not put Project Skills or gathered source
collections below `.agent-factory/`; Gather uses its resolved destination
outside this work root.
</agent-factory>
