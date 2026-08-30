---
name: workspace
description: Provide the Human-facing Agent Factory control tower with exactly five top-level Activities for schedule, Agents, Documents, logs, and tests. Use for Workspace shell and navigation work; do not infer undecided Activity details or own the projected state.
metadata:
  specification-id: workspace
  human-entry: .agent-factory/document/specification/workspace/index.html
  ai-root: skills/workspace/
---

# Agent Factory Workspace

## Entry contract

Use Workspace for the Human-facing project control tower. Its Activity Bar has
exactly five top-level Activities in this order: 일정, 에이전트, 문서, 로그,
테스트. No other top-level item or alias is allowed. Only the Document
Activity's Primary Sidebar is decided: three independently collapsible groups
in the order `원본문서`, `가공문서`, `스펙문서`. Original has `개요` and
`문서검색`. Its compact, tab-free search view uses pinned local Tabulator
6.5.2 with global search and per-column filters over these exact ordered Korean
columns: `문서 분류`, `출처`, `태그`, `문서 이름`, `확장자`, `수정 일자`.
At ordinary desktop widths, the table automatically distributes available
width across all six columns using content-appropriate proportions. Each
column keeps a compact minimum width so genuinely narrow views use horizontal
overflow; Human column resizing and movement remain enabled.
Only document-name cells link to the source Original; provider cells combine
visible provider text with decorative inline SVG. This is a read-only
metadata/link projection that does not copy, normalize, edit, or take ownership
of Original bodies or Gather synchronization. Its source/query adapter,
synchronization trigger and status contract, and metadata mutation authority
and persistence remain unresolved, so it exposes only a small in-browser row
adapter and truthfully reports `데이터 연결 대기` until data is supplied.
Processed and Specification each have `개요` and a consistent explorer/tree-shaped
area for actual Documents. The no-space `스펙문서` spelling is a UI label and does not
rename the Specification type. Overview details, live Document
discovery/source integration, and the other four Activities' sidebar
architectures and capabilities remain Human-owned and unresolved; show those
states honestly and do not invent hierarchy, data, metrics, or controls.
Workspace owns the browser shell, navigation, Activity views, local read-only
serving, and project-root launcher. It does not become the canonical owner or
executor of projected state.
The local launcher and reusable server bind loopback only. When no port is
specified, the first successful bind chooses an available port other than
`8000`, records `{"version":1,"port":<port>}` atomically in generated local
state at `.agent-factory/workspace/port.json`, and later launches reuse it when
available. An occupied saved port is replaced only after another non-`8000`
port has been bound successfully. Explicit `--port`/`-p` values must be from 1
through 65535, may not be `8000`, and become the saved project assignment only
after a successful bind. Malformed or unsafe state fails closed.
The Original overview uses the compact content region without an editor header.
In the Document Sidebar, the terminal Specification group has no trailing
bottom divider below its unresolved connection message; separators between the
three groups remain. This visual treatment does not resolve the still-undecided
Original overview contents.

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

Workspace does not own, initialize, rebuild, inspect, or execute searches
against the Agent-owned catalog at `<project-root>/.agent-factory/db.sqlite`.
`serve.py init` has no catalog side effect. Workspace may later present only
Agent-provided read-only results, but no catalog/search UI or source/query
binding is implemented and presentation transfers no catalog, Agent, or
Document ownership.

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
`.agent-factory/document/specification/`; Workspace does not own or
mirror that Document directory. Agent runtime state remains below
`.agent-factory/agent/`. The five-category decision does not assign these
stores to an Activity information architecture.

Specification discovery uses explicit reciprocal binding metadata rather than
directory-name conventions. Each Human Specification binds to exactly one
Skill directory and that Skill reciprocates the same identity, Human entry,
and AI root. A matching reciprocal locator establishes only the pair and scope,
so semantic alignment remains `unknown` without independent evidence;
mismatches are reported fail-closed as `misaligned`.
An explicitly bound Skill with an unavailable declared Human entry is reported
as `missing-human`; discovery never creates the missing Specification or a
Skill root.

Ordinary consumer-project pairs use the exact same lowercase hyphen-case
`<category>-<title>` identity under `.codex/skills/` and
`.agent-factory/document/specification/`. This plugin is the explicit exception
whose existing six distributed Skill and Specification identities remain
single names.

The local structure is an adapter, not a universal storage requirement. A
resolved project server or external control surface may replace the local UI
while preserving authority, provenance, isolation, accessibility, and
security. Never silently select, mirror, or migrate a backend.
