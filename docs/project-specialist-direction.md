# Project-specialized Agent direction

Status: the two-Skill plugin source is implemented; project-specialized Agent
creation remains a separate unresolved follow-up.

Decision recorded on 2026-09-07 from the Human conversation in this project.

## Target product boundary

The Agent Factory plugin has a two-Skill public surface:

- `agent` owns managed Agent execution and orchestration; and
- `convention` owns shared concepts, authority, and engineering rules.

`document`, `gather`, `tool`, and `workspace` should not remain public plugin
Skills. Their operations, live state, schemas, and guides belong to the Agent
Factory MCP application. The retired plugin Skill and paired Human
Specification sources remain recoverable from Git history.

## Meaning of Specialist

A Specialist is not a Document, Gather, Tool, or Workspace domain Agent. It is
a working Agent specialized for one concrete project: its architecture,
components, repository conventions, accepted decisions, development workflow,
and relevant history.

Creating and maintaining project specialization is a proposed Agent/MCP
capability, not another public plugin Skill. It should inspect current project
evidence, identify stable and refreshable context sources, propose a bounded
responsibility and capability profile, obtain required Human decisions, and
only then create or update the Specialist through the resolved owning runtime.
It must not manufacture expertise from an uninspected summary or treat stale
memory as current project truth.

## Execution relationship

The intended execution shape is conceptually:

```text
Main -> project-specialized worker -> Verification
```

Project specialization changes who performs bounded work and what project
context is bound to that work. It does not permit self-verification. A separate
Verification Agent still checks the resulting work from current evidence.
Document, Gather, Tool, and Workspace capabilities may be supplied by MCP when
needed, but they do not define the Specialist's identity.

## Required profile concerns

A future Specialist definition should bind at least:

- a stable project identity and Specialist identity;
- mission and bounded responsibility;
- authoritative and refreshable context sources;
- included and excluded paths or components where applicable;
- allowed capabilities, effects, and scopes for each dispatched task;
- project-specific constraints and completion criteria;
- provenance, version, freshness, and invalidation or refresh conditions; and
- the persistent session or continuity policy without turning memory into
  authority.

Capability readiness never grants execution authority. Main must still bind
the exact capability, target, scope, and allowed effect to each task.

## Explicitly unresolved

This decision does not yet choose:

- whether the runtime role identifier remains `work` with a Specialist profile
  or is migrated to a new public `specialist` role name;
- the Specialist profile schema, persistence backend, MCP tool names, or API;
- whether a project has one Specialist or several component-specialized
  Specialists;
- profile generation, refresh, retirement, conflict, and portability details;
- compatibility and migration behavior for existing Work sessions and receipts;
- rollout priority, owner, deadline, verification evidence, publication, or
  deployment.

The two-Skill distribution decision is implemented separately from these still
unresolved Specialist details. The current `Main -> Work -> Verification`
runtime contract remains the executable truth until an explicitly reviewed
runtime change replaces it.
