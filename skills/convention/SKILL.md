---
name: convention
description: Apply the Agent Factory core model, local/default work structure, Skill ownership and naming, storage-independent information lifecycle, annotations, and SVG-only user-interface conventions.
---

# Agent Factory Convention

## Entry contract

Use this Skill whenever work designs, reviews, or explains Agent Factory core
concepts or applies its cross-cutting conventions, including information
stages, capability boundaries, Skill ownership and naming, document storage,
code annotations, or UI icons. Read every applicable reference before acting.

Agent Factory has exactly six public distributed Skills: `gather`, `explorer`,
`interview`, `convention`, `agent`, and `specification`. Convention owns the
durable core semantic model and its paired AI-facing representation.

Treat original, processed, and refined information as logical lifecycle stages
independent of storage. `.agent-factory/` is the current/default local adapter;
an explicitly resolved project server or external backend may own any document
root without weakening provenance, authority, isolation, semantic alignment,
accessibility, or security. Never invent or silently select a backend.

Keep distributed plugin Skills below `<plugin-root>/skills/`. Keep consumer
Project Skills below `<project-root>/.codex/skills/<category>-<name>/`. Use the
accepted `<category>-<name>` form for newly named Skill identities when the
owning context requires two parts, and preserve existing accepted identities.

## Reference routing

- `references/annotation.md`: Create or review comments, documentation comments, and traceable TODO annotations.
- `references/svg-icon.md`: Enforce SVG-only icon implementation for frontend and design-system work.
- `references/agent-factory-core.md`: Apply the accepted information lifecycle,
  capabilities, engineering stack, Skill ownership, storage-independent
  document roles, and paired representations.
- `references/agent-factory-core-diagrams.md`: Keep AI-readable Mermaid sources
  aligned with the Human-facing core document.

## Local/default project structure

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
three-stage local document lifecycle. Shared Specification UI remains in
`specification/common/`; Human refined documents live in
`information/refined/human/`. AI-facing refined knowledge remains in Skills,
outside `.agent-factory/`.

## Bootstrap assets

`assets/AGENTS.md` is the plugin-provided project instruction template.
`scripts/init_agents.py` copies it once to `<project-root>/AGENTS.md` and refuses
to overwrite any existing path. The plugin manifest itself does not inject
project files.
