<agent-factory>
Always load and comply with Agent Factory skills.

Use `.agent-factory/` as the current/default local adapter:

```text
<project-root>/.agent-factory/
├── agent/
├── explorer/
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

`agent/` and `explorer/` are operational workspaces. `information/` owns the
three-stage document lifecycle. Human refined documents live below
`information/refined/human/`; AI-facing refined project knowledge lives in
Project Skills below `<project-root>/.codex/skills/<category>-<name>/`.

Information roles are storage-independent. A project may explicitly resolve a
document root to a project server or external backend, but must preserve
provenance, authority, isolation, semantic alignment, accessibility, and
security. Do not silently select, mirror, or migrate a backend.
</agent-factory>
