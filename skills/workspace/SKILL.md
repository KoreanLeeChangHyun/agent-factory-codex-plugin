---
name: workspace
description: Provide the Human-facing Agent Factory control tower for managing project Agents, documents, and project views. Use for the local Workspace shell, navigation, browser launcher, or Human operational visibility; do not use it to define document semantics or execute Agent work.
---

# Agent Factory Workspace

## Entry contract

Use Workspace for the Human-facing control tower that presents and organizes
Agents, documents, and project state. Workspace owns the browser shell,
navigation, Activity views, local read-only serving, and the project-root
launcher. It does not execute managed Agent work, define Document content,
accept Specification truth, or change Document types or relationships.

Keep the responsibility split explicit:

- `agent` owns Agent roles, sessions, execution, orchestration, and results;
- `convention` owns Agent rules, constraints, and core semantics;
- `gather` synchronizes external sources as Original Documents;
- `document` defines and maintains Original, Processed, and Specification Documents;
- `workspace` lets the Human navigate and manage those actors and artifacts.

The two local Explorer paths have different owners and must remain distinct:
`.agent-factory/explorer/` stores temporary Work/Explorer evidence, while
`.agent-factory/workspace/explorer/` is the read-only Workspace File/Project
Explorer Activity projection. The Activity discovers the project and evidence
trees but never copies, edits, moves, deletes, promotes, or owns their contents.

## Reference routing

Read `references/interface.md` before creating, editing, installing, or serving
the Workspace UI. It defines the local adapter, Activity ownership, launcher,
allowlisted roots, and presentation boundaries.

## Local/default structure

```text
<project-root>/.agent-factory/workspace/
├── common/
├── explorer/
└── skills/
```

Planning reads Human-facing Specifications from
`.agent-factory/information/refined/human/`; it does not own or mirror a
document directory. Agent runtime state remains below `.agent-factory/agent/`,
and temporary Work/Explorer evidence workspaces remain below
`.agent-factory/explorer/`; the similarly named Workspace Activity directory
is only their Human-facing read-only projection.

The local structure is an adapter, not a universal storage requirement. A
resolved project server or external control surface may replace the local UI
while preserving authority, provenance, isolation, accessibility, and
security. Never silently select, mirror, or migrate a backend.
