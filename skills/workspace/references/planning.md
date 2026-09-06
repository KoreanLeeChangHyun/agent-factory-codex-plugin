# Development planning (accepted 2026-09-05)

The Human accepted implementation of the schedule Activity using the existing
Activity Bar -> Primary Sidebar -> Workspace area shell. This decision resolves
only development planning; it does not change other Activities or background-job
scheduling. The selected MCP runtime owns tenant PostgreSQL planning records.

## Model and operations

- Three distinct levels: function domain (`domain`) -> user-facing feature
  (`feature`) -> implementation issue (`issue`). Parents must belong to the same
  Workspace; levels cannot be skipped. Domain has no parent. Kind and parent are
  immutable after creation.
- All levels have a name and description. Features have acceptance criteria,
  assignee label, pending/active/done status, optional blocked reason, optional
  start and target dates. Issues have assignee label, status, blocked reason and
  an optional target date. The assignee is a planning label, not an Agent launch
  or authorization grant.
- Domain dates are optional explicit overrides; each omitted boundary derives
  from the earliest known feature start or latest known feature target. Empty domains are pending. All-done features imply done;
  any active or partially completed set implies active; otherwise pending.
  Missing dates remain visibly unspecified; no estimated date is invented.
- Feature dates and status are explicitly managed. Issue completion counts do
  not imply time-based progress or automatically mark a feature complete.
- The Workspace plan also has an optional launch target date.
- Query/create/update/delete are tenant-scoped, permission-checked APIs. Reads
  require workspace.read; writes require workspace.manage and session CSRF.
  Revision checks prevent silent overwrite. Concurrent hierarchy edits serialize
  within the Workspace. Parents with children cannot be deleted.
- PostgreSQL tables plan_items and plan_settings own persistence, distinct from
  automated schedules/jobs. No project-local planning file or browser storage
  owns business state.

## Sidebar and Workspace area

- Sidebar: fixed 전체 일정, followed by collapsible domains and their features.
  Show status SVG and item name; selected row is highlighted. Long names are
  ellipsized with full title. Domain/feature navigation remains keyboard usable.
  Provide refresh and domain creation; child creation belongs to the selected
  parent view. Issues do not appear in the navigation tree.
- Entire plan: a domain-grouped feature timeline. One feature per row; sticky
  name column/date header; week default with calendar-month alternative; today,
  fit-entire-range, today line and optional launch target marker. Features with
  missing dates remain present with explicit partial/unspecified period text.
  Clicking a feature opens its details. Returning retains horizontal position.
- Domain: explicit/fallback period, derived status, description and feature table with status,
  period and issue completion count.
- Feature: editable period, status, assignee, acceptance criteria, description,
  blocked reason, plus issue table (name, assignee, status, optional target).
  Expand issue rows for inline description/property editing. Preserve drafts
  when navigating or opening other rows; successful save clears that draft.
- Expired unfinished targets show 기한 초과. Blocked items show 막힘 and reason.
  Issue targets outside known feature bounds show 상위 작업 기간 밖; feature editing
  is available to adjust the target deliberately, never automatically.
- Use explicit save/cancel for editing, deletion confirmation and nonempty-parent
  rejection. On revision conflict preserve input and explain cancel + refresh to
  retrieve latest state. Modal cancellation discards that modal draft.
- All views share a server snapshot; saved changes reload it. Stale requests
  from another Workspace or earlier reload cannot overwrite current data.
  Workspace switching clears selections, drafts and prior tenant content.
- Truthful loading/empty/error states and retry, read-only views for viewers,
  visible focus, semantic forms/tables and SVG icons are required.
- Initial implementation uses click-based date editing. Dependency lines,
  drag scheduling, extra dashboards and mandatory issue dates are not required.

## Runtime contract

MCP runtime files: app/modules/planning/, app/router/planning.py,
app/db/migrations/versions/0013_development_planning.py, static/js/planning.js,
static/css/planning.css, and the existing template/workspace/index.html shell.
API base: /api/organizations/{organization_id}/workspaces/{workspace_id}/plan.
GET base returns flat typed items, derived domain fields, settings and can_edit.
POST /items creates; PUT /items/{id} replaces editable fields with revision;
DELETE /items/{id}?revision=N removes a leaf; PUT /settings updates launch_date
with revision (0 before initial creation). Verification must cover real database
persistence, authorization/CSRF/RLS, hierarchy/date rejection and concurrent writes,
plus browser navigation, rendering, editing, tenant switching and error recovery.

새로고침과 작업 추가는 기본 사이드바 헤더 오른쪽의 SVG 아이콘 버튼으로 제공한다. 일정 선택 시에만 표시하며 추가는 편집 권한이 있을 때 제공한다. 본문에는 전체 일정과 도메인/기능 탐색 트리만 둔다.

## Common scheduling terminology (accepted 2026-09-05)

Use 작업 (Task) as the common user-facing name at every level. The sidebar
header control is 작업 추가; creation under a selected parent is 하위 작업 추가.
Name fields and table/timeline name columns say 작업 이름; child sections say
하위 작업. Explain derived totals as 하위 작업에서 집계 and out-of-bounds targets
as 상위 작업 기간 밖 with 상위 작업 기간 조정. Use generic terms in empty states,
dialogs, accessibility names, tooltips and validation errors as well.

Existing domain/feature/issue storage kinds, three-level parent constraints,
completion criteria, date rules and issue-detail editing stay unchanged.
Summary task and subtask describe relationships, not three new fixed type names.
This terminology change does not implement arbitrary-depth WBS or rename records.

Keep schedule header actions within the sidebar content width; do not use a negative end margin that exceeds the current shell header padding or creates horizontal sidebar scrolling.

## External AI schedule import (accepted 2026-09-05)

The external user-selected AI reads Excel files, Google Sheets, Notion or Jira
through its own file tools/connectors/MCPs, interprets the source and submits a
version-1 common proposal. The planning-import capability hosts no model or source-service connector; separately authorized cloud Gather integrations remain a different domain.
This is user-requested one-way import, not automatic synchronization.

Expose planning_schema, planning_read, planning_import_preview and
planning_import_apply plus agent-factory://planning/import-guide. Preserve the
existing three levels and field restrictions. Entries carry stable provider,
document and row identities, parent references, complete editable fields,
original values/location, corrections with reasons and unresolved questions.
Declared read scope must be complete; missing dates remain null and unresolved
questions block apply. No name-based automatic merging or imported deletion.

Persist previews and source mappings in tenant PostgreSQL tables plan_imports
and plan_source_links (migration 0016). A preview changes no plan items. The
Workspace area under 전체 일정 → 가져오기 lists the latest 50 previews/results,
shows source/read scope, hierarchy, additions/updates/unchanged rows, before and
after values, original values, correction reasons, errors and warnings. Escape
all imported text. Users inspect and acknowledge changes before applying;
viewers can read but cannot submit/apply. Keep sidebar header refresh/add and
navigation compact without extra horizontal overflow. Workspace changes discard
pending view state and stale responses. Loading/errors offer retry.

Use identical owner-side validation for REST and MCP. Reads require
schedule:read for MCP and workspace.read; writes require schedule:write for MCP
and workspace.manage, with browser CSRF. New editor MCP connections receive
schedule:write; old tokens are not silently elevated. Existing tokens without
that scope need a newly issued connection for MCP submission, while browser
apply uses the user's current permission. Preview IDs are tenant-scoped.

Same request key and identical payload return the same durable preview;
different payload with that key fails. Apply requires the exact preview digest
and explicit warning acknowledgement. Applied retries return the same result.
Workspace locking serializes writes; any intervening item revision/identity or
source mapping change invalidates pending previews. All planned rows and source
links commit atomically. Existing kind/parent cannot change. Stable source IDs
map repeated imports to the same items; existing_id explicitly binds an unlinked
source to a current item. Proposals replace all editable fields, including
omitted-field defaults, so previews must show all changes. Maximum 500 entries
per proposal; larger declared scopes use sequential batches and stable parent
references. Full collection completeness and semantic truth are assertions of
the external caller, not something schema validation can independently prove.

Runtime guide docs/planning-import.md includes the four source examples,
connection/scopes, mapping and uncertainty rules, preview/apply sequence,
idempotency and conflict recovery. Package that guide in the runtime image.
Verification covers deterministic contracts, real PostgreSQL migration cycle,
RBAC/CSRF/RLS, replay/concurrency/conflict, actual MCP calls and browser review,
apply and untrusted-text rendering.

## Optional top-level dates and required labels (accepted 2026-09-06)

Domain start_date and target_date are independently optional stored overrides.
Explicit values win per boundary; null derives that boundary from features,
with neither source available remaining unspecified. Domain status stays derived.
GET snapshot keeps effective start_date/target_date and adds configured_start_date,
configured_target_date, start_date_source/target_date_source (explicit, derived,
unspecified) and period_conflict for domains. Editing and import preservation use
configured fields so merely saving a name cannot freeze a derived date.
Two explicit reversed dates are rejected; a reversed mixed effective period is
shown as a conflict without changing either value or fabricating a date.

Show per-date origins in the domain summary and full timeline group, including
empty domains with optional dates. Include domain dates in fit-entire-range.
Warn when any known feature date lies outside its domain's effective bounds,
and when an issue target lies outside feature bounds. Offer deliberate parent
editing; do not block saving an otherwise valid out-of-bounds child or adjust dates.
Import previews evaluate resulting hierarchy bounds and return review warnings.
Task name has a visible * and native required semantics; dates and other optional
fields have no optional label or asterisk. Explain * as 필수 항목 in the form.
Keep API/MCP instructions, packaged import guide, tests and paired Human text aligned.

Timeline geometry must work under the runtime style-src self CSP: apply numeric
positions/widths through individual CSSOM properties rather than HTML style
attributes. Reserve compact header lanes for ticks and today; show launch date in the view summary;
body marker lines must not obscure domain period/origin text. Verify real rendered
geometry with the same CSP in the browser harness.


## Timeline visual layout (accepted 2026-09-06)

Use a sticky task-information column (280px desktop, 220px narrow) and a date
canvas, inspired by GitHub Projects roadmap, Notion's table beside its timeline,
and Jira parent/child schedule bars. Name/status and period occupy two compact
lines on the left; indent features below their domains. An undated item says
기간 미정 only there, leaving its date canvas empty. Domain origin badges say
직접 지정, 집계 or 직접 지정·집계; title exposes the per-boundary explanation,
while domain details retain fully visible per-date origins.

Render domains with summary bars and features with ordinary bars on the same
scale. A lone known date is a point with its exact date in the accessible label,
never an invented duration. Conflicting effective periods have no misleading bar.
Offscreen dated items retain a date-navigation action. Keep the calendar header
52px tall, today caption and thin body line, launch target in the summary with a
separate thin line, and subtle aligned vertical date guides. Keep CSP-safe numeric
CSSOM geometry, keyboard actions, status text in bar labels, and scoped scrolling.

Reference evidence: https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/customizing-the-roadmap-layout
https://www.notion.com/help/timelines
https://support.atlassian.com/jira-software-cloud/docs/what-is-the-timeline-and-how-do-i-use-it/
