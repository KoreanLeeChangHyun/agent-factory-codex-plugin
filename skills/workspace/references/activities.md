# Workspace Activities

## Decided top-level contract

The Activity Bar contains exactly five top-level Activities in this order and
with these Korean Human-facing labels:

1. 일정
2. 에이전트
3. 문서
4. 로그
5. 테스트

Do not add aliases, overview/dashboard items, or separate top-level Roadmap,
Explorer/File Explorer, Planning/Specification, or Project Skills items. Do not
infer or nest those earlier views beneath any of the five Activities.

The Document Activity's Primary Sidebar is also decided. It contains three
prominent, independently collapsible groups in exactly this order:

1. `원본문서`: accessible `개요` and `문서검색` navigation; `문서검색`
   selects a compact, tab-free Tabulator view with global search, per-column
   filters, and the ordered columns `문서 분류`, `출처`, `태그`, `문서 이름`,
   `확장자`, `수정 일자`. Document-name cells link to source Originals, while
   provider cells show inline SVG and visible provider text.
2. `가공문서`: accessible `개요` navigation and an explorer/tree-shaped area
   reserved for actual Processed Documents.
3. `스펙문서`: accessible `개요` navigation and the same explorer/tree-shaped
   area reserved for actual Specification Documents.

`스펙문서` is the exact no-space UI spelling. It does not rename the logical
Specification type. The Original search surface is only a read-only metadata
and source-link projection: it preserves Original source fidelity and neither
copies or edits bodies nor owns Gather synchronization. Live source/query/API
integration, synchronization trigger and status, and metadata mutation
authority and persistence remain Human-owned and unresolved. Show the truthful
`데이터 연결 대기` state without sample files, fabricated records, metrics,
sync controls, or editing. A small in-browser row adapter is only a boundary for
a future owner-backed loader; the implemented bounded catalog search CLI does
not connect or resolve this Activity source. Overview contents remain unresolved.

The other four Activities—Schedule, Agents, Logs, and Tests—still have no
decided Primary Sidebar information architecture or detailed capabilities.
Each must state that its configuration awaits Human definition. Do not use
placeholder project state or examples that could be mistaken for real state.

The public Tool Skill's lifecycle/control contract does not define a sixth
Activity and does not authorize placing Tool beneath any existing Activity.

## Shared authority boundary

Workspace remains a Human-facing observation and control-routing surface. It
does not become the canonical owner or executor of schedule data, Agent
runtime state, Documents, logs, or tests. When a future source or control
contract is resolved, present its unavailable or unconfigured state honestly
and route mutations only through the owning capability's explicit authority
contract. The five-category decision itself does not authorize a data source,
control, navigation hierarchy, or live integration.
