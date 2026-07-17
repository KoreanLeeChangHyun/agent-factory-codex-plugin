---
name: init
description: Use at the start of Agent Factory lifecycle adoption in a target project, especially when the user wants an init-style entrypoint. Ask the Human for the current adoption timing, recommend Goal mode for long-running initialization, and route through Intake, Work Unit, Execution, and Human Review with Human-decided merge, rework, or PR promotion.
---

# Agent Factory Init

Use this skill as the Agent Factory lifecycle entrypoint when a target project
is adopting Agent Factory.

Treat `lifecycle` and its `references/lifecycle.md` as the
canonical lifecycle and Goal-creation authority. The route summaries here must
not override that contract.

This skill does not replace Codex built-in `/init`. It defines the Agent
Factory initialization flow that should be run as a long-running Goal when the
work may require baseline collection, Project Core, Design Report, Work Units,
review, or handoff.

## Goal Rule

Prefer Goal mode for Agent Factory initialization.

If no Goal is active, recommend that the Human start a Goal. Create a Goal only
when the Human explicitly asks Codex to create one; tool availability alone is
not authorization. The Goal should state that Codex must initialize Agent
Factory lifecycle adoption for the current project, determine the adoption
timing, collect only explicit baseline facts, update Project Core and Design
Report as needed by creating Work Units from validated ready Intake packages and
executing those Work Units.

Do not continue into artifact-writing, implementation, migration, cleanup, or
Work Unit creation without the lifecycle basis unless the Human explicitly asks
to bypass it.

Intake checks and updates relevant specifications through `intake` and
`specification` before Work Unit planning. Implementation and other scoped
delivery artifact writing belongs to Work Unit Execution.

## First Question

Use `interview` and ask exactly one three-choice timing question before
choosing the route:

```text
Which Agent Factory adoption timing applies to this project now?
```

Offer these choices:

- `A`: New project initialization.
- `B`: In-progress project adoption.
- `C`: Ending/release-handoff or maintenance/operations; ask one follow-up
  three-choice question to distinguish these routes.

For the `C` follow-up, offer `A` for ending or release-handoff, `B` for
maintenance or operations, and `C` for unresolved timing that must remain in
Intake until evidence or a Human decision distinguishes the route.

If the Human has already stated the timing explicitly, record it and do not ask
again.

## Timing Routes

### New Project Initialization

Do this when the project is starting or has no meaningful existing baseline.

1. Record the user's explicit purpose, scope, constraints, and unresolved items
   as Intake basis.
2. Transition the Intake to `ready`, then create small executable Work Units
   from its accepted basis.
3. Use those Work Units during Execution to create or update Project Core,
   Design Document, and Design Report output.
4. Keep the baseline minimal; do not invent requirements.
5. When the Design Document or Design Report covers later implementation,
   record it as a specification input to a new Intake, transition that Intake
   to `ready`, and create the implementation Work Units from its accepted
   basis.

### In-Progress Project Adoption

Do this when code, documents, runtime behavior, or decisions already exist.

1. Collect the baseline in a canonical Intake before changing Project Core or
   creating Work Units.
2. Record current structure, existing documents, commands, tests, runtime,
   deployment, known constraints, open work, and unresolved decisions.
3. Complete specification alignment, validate the Intake, and use only its
   `ready` Work Unit basis entries to create Work Units.
4. Use those Work Units during Execution and update Project Core only for
   purpose, principles, scope, approval boundaries, or unresolved items.
5. Record the updated Design Document or Design Report as an Intake
   specification reference when it covers later implementation work.

### Ending Or Release-Handoff Adoption

Do this when the project is being finalized, released, reviewed, or handed off.

1. Collect a final-state baseline: current deliverables, completed work,
   pending reviews, known defects, deployment status, release constraints,
   handoff needs, and unresolved decisions.
2. Transition the final-state Intake to `ready`, then create Work Units only
   from its approved finalization, rework, verification, deliverable, release,
   or handoff basis entries.
3. Use those Work Units during Execution to update Project Core, Design
   Document, or Design Report when their approved scope requires artifact changes.
4. Keep Work Unit Outputs separate from customer-facing deliverables.
5. Leave merge, release, deployment, operation, and promotion decisions to the
   Human.

### Maintenance Or Operations Adoption

Do this when the project is live, operated, bug-fixed, or maintained.

1. Collect an operations baseline: runtime, deployment, incidents, logs,
   monitoring, known risks, current behavior, maintenance request, and
   approval boundaries.
2. Transition the operations Intake to `ready`, then create Work Units for its
   scoped design, maintenance, bugfix, verification, operation, or document
   basis entries.
3. Use those Work Units during Execution to update Project Core, Design
   Document, Design Report, implementation, or operational documentation within
   their scope.
4. Keep implementation-only rework within its existing Work Unit; return new
   requirements or specification changes to Intake.
5. Return new operation or maintenance requests to Intake.

## Skill Routing

- Use `fact-only` for all initialization work.
- Use `intake` to create and validate the canonical Intake package and repeat
  revision until it is ready for Work Unit planning.
- Use `interview` for the adoption timing question when the timing
  is not already explicit.
- Use `web-search` when initialization needs recorded web research,
  external-source verification, comparison research, recommendation evidence,
  or investigation summaries.
- Use `analysis` when initialization needs an internal code, database, data,
  configuration, log, test, runtime, or document baseline.
- Use `user-research` when initialization needs authorized direct observation
  of users, operators, workflows, usage context, or usability evidence.
- Use `lifecycle` after the timing route is known.
- Use `specification` during Intake when Project Core or other specification
  source is missing, affected, or changed.
- Use `work-unit-planner` only after the canonical Intake package validates in
  `ready` status.

## Output

State:

- The selected adoption timing.
- Whether Goal mode is active or should be started.
- Which lifecycle phase comes next.
- Which artifacts may be changed next.
- Which facts remain missing or unresolved.
