# Workspace Activities

## Top-level contract

Workspace has exactly six top-level Activities in this order:

1. 일정
2. 에이전트
3. 문서
4. 외부연동
5. 로그
6. 테스트

These exact Korean labels appear below decorative SVG icons in the Activity
Bar. Do not add aliases or another Activity. The order does not imply ownership
or a workflow among domains.

`외부연동` is a regular Activity with a Primary Sidebar and Workspace view. It
is not a bottom utility. Its Primary Sidebar has exactly seven ordered,
non-interactive work-purpose groups:

1. 웹·리서치
2. 문서·파일
3. 메일·메시지
4. 일정·회의
5. 지식·업무관리
6. 개발·운영
7. 데이터·비즈니스

Provider, account, integration method, status, permission scope, and last
synchronization time are item attributes rather than category axes. Categories
do not imply a connection, source selection, nested navigation, or
category-specific control. The Workspace view starts with the truthful
`외부연동 상태 연결 대기` state and may show only owner-backed integration
facts. Detailed rendering and the future loader contract belong to
`references/interface.md`.

## Document sidebar

The Document Primary Sidebar has three independently collapsible groups in this
order: `원본 문서`, `가공 문서`, `명세 문서`. These are exact Human-facing
labels; they do not rename logical types, identifiers, metadata, or paths.

### Original

Original contains `개요` and `문서검색`. Search uses a compact semantic table.
The MCP application may provide global search, per-column filters, sorting,
Human resizing and reordering without requiring this plugin to distribute a
browser library. The exact ordered columns are:

1. 문서 분류
2. 출처
3. 태그
4. 문서 이름
5. 확장자
6. 수정 일자

Only the document-name cell links to the source Original. Provider cells retain
visible provider text and a decorative inline SVG. This is a read-only
metadata/link projection; Workspace neither copies nor mutates Original content
and does not own Gather synchronization.

### Processed and Specification

Processed and Specification each contain `개요` followed immediately by a
visible `탐색기` parent row. Actual Document lists or truthful states appear
nested under that parent. Processed discovery reads authorized tenant Document records and their immutable revisions, never a project-local scan. An absent browser entry remains visibly unavailable; use the authenticated package preview when available.

Specification discovery compares reciprocal Human/AI binding metadata and
reports `paired`, `misaligned`, or `missing-human`. Only paired entries are
navigable. Selecting one opens or activates its Human browser document in a
read-only editor group. The explorer is an actual tree and supports click as the
non-drag fallback.

The detailed row geometry, short-title behavior, authenticated revision delivery and isolated preview,
keyboard model, tabs, close behavior, drag-and-drop, recursive splits, empty
states, iframe handling, and cleanup rules belong only to
`references/interface.md`.

## Development schedule

The schedule Activity is resolved as domain -> feature -> implementation issue
planning, with a domain/feature sidebar and timeline/detail Workspace views.
Apply the complete model and interaction contract in `planning.md`.

## Resolved and unresolved scope

Resolved scope includes the six top-level labels and order, seven External Integration categories, Document sidebar/read-only discovery shapes, accepted planning in `planning.md`, and cloud-backed domain routing. Cloud implementation alone does not authorize new UI controls or fill undecided navigation.

The following remain Human-owned and unresolved:

- Agents, logs, and tests sidebar architecture and detailed
  capabilities;
- overview content;
- live Original source/query integration;
- additional synchronization UI triggers and status presentation beyond the cloud collection contract;
- additional metadata-edit UI controls beyond the authenticated cloud Document contract;
- External Integration category navigation, child sources, and lifecycle
  controls beyond an owner-backed projection.

Show these as awaiting definition or connection. Do not invent hierarchies,
records, metrics, controls, accounts, connection health, or capabilities.

## Authority boundary

Workspace presents owner-backed state and routes authorized controls; it does
not become the canonical owner. Agent owns local execution/graph and receipts; the cloud owns shared reporting/search. Document
owns Documents, Gather owns external synchronization, Tool owns logical external
tool/connector lifecycle, and each provider remains authoritative. Existing
local discovery directories or utilities do not create an Activity or authorize
nesting under one.
