---
name: workspace
description: Provide the Human-facing Agent Factory control tower with exactly five top-level Activities for schedule, Agents, Documents, logs, and tests. Use for Workspace shell and navigation work; do not infer undecided Activity details or own the projected state.
---

# Agent Factory Workspace

## Entry contract

Use Workspace for the Human-facing project control tower. Its Activity Bar has
exactly five top-level Activities in this order: 일정, 에이전트, 문서, 로그,
테스트. No other top-level item or alias is allowed. The Human has not yet
defined any Activity's Primary Sidebar information architecture or detailed
capabilities; show that state honestly and do not infer a hierarchy, source,
metric, or control. Workspace owns the browser shell, navigation, Activity
views, local read-only serving, and project-root launcher. It does not become
the canonical owner or executor of projected state.

The browser shell has two required forms: reusable installation sources below
`assets/browser/` and the current project's installed publication below
`.agent-factory/workspace/common/`. Maintain the three core browser-code files
`index.html`, `styles.css`, and `app.js` together and byte-identically. Maintain
any required packaged companion asset in both forms as well: the current
`THIRD_PARTY_NOTICES.txt` carries attribution and license text, is installed by
the initializer, and must remain byte-identical to its materialized copy. It is
not a fourth browser-code file. A missing or divergent required form is
incomplete. The packaged assets remain the installation source rather than a
second runtime authority.

Under the current/default local adapter, Workspace owns the maintained schema
asset for the project-wide catalog at `assets/schema/catalog.sql`. A future
initializer materializes that schema only at `<project-root>/.agent-factory/db.sqlite`.
The database is a rebuildable, non-authoritative read model spanning Agent
execution structure and Documents; visibility there transfers neither Agent
nor Document semantics to Workspace.

Keep the responsibility split explicit:

- `agent` owns Agent roles, sessions, execution, orchestration, and results;
- `convention` owns Agent rules, constraints, and core semantics;
- `gather` synchronizes external sources as Original Documents;
- `document` defines and maintains Original, Processed, and Specification Documents;
- `tool` owns logical external tool and connector lifecycle control while its
  host, plugin, MCP server, or project manifest remains authoritative;
- `workspace` lets the Human navigate and manage those actors and artifacts.

Existing local projection or discovery directories and utilities do not define
a top-level Activity or authorize nesting under one of the five Activities.
Tool is likewise not a sixth Activity. Any future Tool projection or control
must remain owner-backed and must not infer an Activity placement.

## Reference routing

- Read `references/activities.md` when defining or presenting the five
  top-level Activities. It records the decided order, undecided detail, and
  ownership boundary.
- Read `references/interface.md` before creating, editing, installing, or
  serving the Workspace UI. It defines the two-form publication invariant,
  local adapter, launcher, allowlisted roots, and presentation bounds.

## Local/default structure

```text
<project-root>/.agent-factory/workspace/
├── common/
├── explorer/
└── skills/
```

Human-facing Specifications remain below
`.agent-factory/document/specification/human/`; Workspace does not own or
mirror that Document directory. Agent runtime state remains below
`.agent-factory/agent/`. The five-category decision does not assign these
stores to an Activity information architecture.

The schema asset normalizes schema version metadata, Agents and resumable
sessions, runs and turns, Work/Verification loops, graph and dispatch
relationships, Documents and storage-independent types, representations,
source-backed Document relationships, Agent-Document relationships, and
Specification pair status. It deliberately stores no bodies, event streams,
requests, results, receipts, heartbeats, or containment/recovery evidence.
Catalog population, rebuild jobs, dual writes, query APIs, search, and screens
are not implemented by the schema foundation.

The local structure is an adapter, not a universal storage requirement. A
resolved project server or external control surface may replace the local UI
while preserving authority, provenance, isolation, accessibility, and
security. Never silently select, mirror, or migrate a backend.
