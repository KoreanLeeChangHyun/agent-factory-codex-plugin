# Agent Factory Lifecycle

This reference summarizes the current Agent Factory lifecycle for Codex use.

## Purpose

Agent Factory manages the customer's SDLC through visible UI/UX. Codex uses
Agent Factory skills and `<project-root>/.agent-factory/` artifacts
to follow the intended lifecycle.

`<project-root>` is the root directory opened in the current editor, IDE, or
Codex workspace. Resolve Agent Factory artifacts from
`<project-root>/.agent-factory/` and bundled Plugin resources from the installed
Plugin's owning skill. Never derive either root from a machine-specific
absolute path. When the shell is inside a project subdirectory, the opened
workspace root remains `<project-root>`. If no root is open, or a multi-root
workspace leaves the target ambiguous, require an explicit Human selection
before writing.

## Required Artifact And Approval Lifecycle

```text
Intake
  -> Work Unit
  -> Execution
  -> Review
```

During lifecycle adoption, Codex uses Intake, Work Unit, Execution, and Review
to keep requests moving through the required artifact and approval lifecycle.

## Lifecycle Routing Phases

```text
Intake:
  Customer explains goal, submits a requirement, asks for analysis or research, or requests rework/operation/maintenance
    -> record Human requirements and feedback
    -> perform external web research when needed
    -> analyze internal code, databases, data, configuration, logs, tests, and runtime when needed
    -> observe users, operators, workflows, and usage context when direct user evidence is needed and authorized
    -> interview the Human when a Human-only decision is needed
    -> check and update relevant specifications
    -> repeat manager apply -> validation -> semantic review -> revision
    -> transition the canonical Intake package to ready only when it can define one or more executable Work Units

Work Unit:
  Create executable Work Unit packages from a validated ready Intake
    -> each Work Unit is the minimum /goal <work-unit-id> execution unit for a fresh Codex Goal session
    -> each Work Unit includes basis, goal, scope, expected output, verification, AI checklist, Human checklist, Human review method, and unresolved items

Execution:
  Execute one Work Unit through Plan -> Work -> AI Review -> Report
    -> perform scoped artifact writing when it is an expected Work Unit output
    -> apply checklist, TDD, and verification loop
    -> perform AI review
    -> prepare evidence and Human review checks

Review:
  Human reviews Work Unit execution
    -> approve, request rework, merge, or decide PR promotion when applicable
    -> if implementation rework is needed, return to Work Unit or Execution
    -> if requirement or design changes are needed, return to Intake

Promotion and operations:
  Promoted work can create operation or maintenance requests
    -> operation and maintenance requests return to Intake
```

All Agent Factory work follows Intake -> Work Unit -> Execution -> Review.
This includes analysis, research, Design Document work, Design Report work,
document work, code changes, verification, operation, maintenance, and other
artifacts. Execution includes AI review. Review means Human review.

Intake checks and updates relevant specification source so accepted
requirements, feedback, and evidence remain aligned before Work Unit planning.
Implementation and other delivery artifact writing belongs to Work Unit
Execution. Execution may return changed requirements or design facts to a new
Intake loop.

## Adoption Scenarios

Agent Factory lifecycle adoption can start at different project timings. The
first task is to identify the timing, then route the work without bypassing the
lifecycle.

### New Project Initialization

Use this route when the project is starting or has no meaningful existing
baseline.

- Ask for the explicit project purpose, scope, constraints, approval
  boundaries, and unresolved items.
- Collect and validate a canonical Intake package from explicit Human facts and
  any approved interview, research, data investigation, code investigation, or
  runtime analysis.
- Check or update the relevant specification during Intake.
- Create Work Units from the accepted Intake basis.
- Use those Work Units during Execution to create a canonical Project Core
  package when absent and the scoped Specification or Design Report output.
  Governed Specifications reference Project Core without copying its content;
  a Design Report may render the resolved relation as a read-only top view.
- Treat the baseline as minimal unless the Human provides more facts.
- Expand Design Report detail only from explicit facts and approved decisions.
- When the Design Report covers later implementation, record it as a
  specification input to a new Intake, transition that Intake to `ready`, and
  create the implementation Work Units from its accepted basis.

### In-Progress Project Adoption

Use this route when code, documents, runtime behavior, or decisions already
exist.

- Collect baseline reference material in a canonical Intake package before
  creating Work Units.
- Record current structure, documents, commands, tests, runtime, deployment,
  known constraints, open work, and unresolved decisions.
- Check or update the relevant specification and use only a `ready` Intake as
  explicit basis for Work Units.
- Use those Work Units during Execution to update Project Core, Design Document,
  Design Report, implementation, review, or maintenance output within their scope.
- During Execution, update Project Core only when purpose, principles, scope,
  approval boundaries, or unresolved items change.
- Record an updated Design Report as a specification reference in Intake when
  it covers the work. Work Unit basis always comes from the validated `ready`
  Intake, which preserves that specification reference and result.

### Ending Or Release-Handoff Adoption

Use this route when the project is being finalized, released, reviewed, or
handed off.

- Collect final-state baseline material: deliverables, completed work, pending
  reviews, known defects, deployment state, release constraints, handoff needs,
  and unresolved decisions.
- Transition the final-state Intake to `ready`, then create Work Units only
  from its approved finalization, verification, rework, deliverable, release,
  or handoff basis entries.
- Use those Work Units during Execution to update Project Core, Design Document,
  or Design Report when the approved finalization, rework, release, or handoff
  scope requires artifact changes.
- Keep Work Unit Outputs separate from customer-facing Customer Deliverables.
- Leave release, deployment, operation, and promotion decisions to the Human.

### Maintenance Or Operations Adoption

Use this route when a live or maintained project needs operation, bugfix,
documentation, or maintenance work.

- Collect operations baseline material: runtime, deployment, incidents, logs,
  monitoring, known risks, current behavior, maintenance request, and approval
  boundaries.
- Create Work Units for scoped design changes, maintenance, bugfix,
  verification, operation, or documentation tasks when the canonical Intake is
  ready.
- Use those Work Units during Execution to update Project Core, Design Document,
  Design Report, implementation, or operational documentation within their scope.
- Return new operation or maintenance requests to Intake.

## Goal-Based Initialization

Agent Factory initialization should prefer Goal mode when available. The Goal
keeps the adoption route alive across baseline collection, Project Core, Design
Report, Work Unit planning, review, merge or rework, and promotion decisions.
Recommend Goal mode when useful, but create a Goal only after an explicit Human
request to create it.

The initialization Goal should include:

- Determine the current adoption timing.
- Collect only explicit baseline facts.
- Complete and validate a canonical Intake package before Work Units.
- Create self-contained Work Units from validated ready Intake packages.
- Use Work Units to create or update Project Core and Design Report when those
  artifacts are the expected output.
- Keep Human approval, merge, deployment, operation, maintenance, and PR
  promotion decisions with the Human during Review.

## Named Work Unit Goal Execution

When the Human starts a fresh session with `/goal <work-unit-id>` or invokes a
fresh `codex exec` session with an explicit Work Unit id and its recorded
execution context, treat the request as execution of that exact Work Unit
package. The `codex exec` route does not require persistent Goal mode.

Use this resolution flow:

- Resolve `<work-unit-id>` to `<project-root>/.agent-factory/work-units/<work-unit-id>/`.
- Work in Korean for planning, progress updates, review summaries, reports, and
  other Human-readable communication during this project's named Work Unit Goal
  execution. Keep commands, file paths, identifiers, code, API names, package
  names, branch names, and exact log output unchanged.
- Run the Work Unit manager's full validation, then read `data/metadata.json`,
  `data/title.json`, the manager-owned table of contents, every canonical
  section, `blocks/index.json`, and referenced blocks. Schema version `4.0.0`
  is the sectioned execution contract.
- Use the package as the execution source of truth for basis, goal, scope,
  out-of-scope items, acceptance criteria, verification, AI checklist, Human
  checklist, Human review method, unresolved items, and review boundaries.
- Execute only that Work Unit unless the Human explicitly expands or changes
  scope.
- Route the Git execution boundary through `work-unit-execution`. Resolve the
  repository root, base ref, dedicated branch, and absolute linked worktree path
  from the package or an explicit Human decision, derive the branch as
  `work-unit/<work-unit-id>`, then prepare or inspect the worktree and record its
  canonical JSON result as execution evidence. Re-execution and rework reuse the
  same registered pair.
- Never generate fallback worktree path names. Cleanup requires an explicit
  Human cleanup decision and must refuse dirty worktrees and forced removal.
- If the package is missing, ambiguous, already complete, blocked, or lacks
  enough basis for a fresh session, stop and ask the Human before editing.
- Preserve the separation between the defining session and the execution
  session. Do not rely on hidden chat history from the defining session.

## Baseline Checklist

For in-progress, ending, release-handoff, maintenance, or operations adoption,
collect only explicit baseline facts that are relevant to the request:

- Project purpose and current status.
- Existing Design Report, Project Core, Work Units, outputs, and deliverables.
- Current repository structure and important source paths.
- Documents, diagrams, decisions, and known constraints.
- Commands, tests, runtime, deployment, and verification status.
- Open work, known defects, incidents, risks, and unresolved decisions.
- Pending Human approvals, review requests, merge decisions, release decisions,
  operation decisions, maintenance decisions, or PR promotion decisions.

The baseline is reference material. It never replaces Project Core, Design
Report, Work Units, Work Unit Outputs, or customer-facing Customer
Deliverables.

## Core Artifacts

- Intake is the canonical basis package that combines Human input, external
  research, internal analysis, user research, Human decision interviews,
  specification alignment, synthesis,
  and readiness.
- A Work Unit is the minimum Codex Goal execution and review unit. It contains
  basis, goal, scope, expected output, AI checklist, verification or test plan,
  AI checklist result, Human checklist, Human review method, approval or rework
  criteria, and unresolved items.
- The Work Unit defining session and the Work Unit execution session are
  separate. A Work Unit must be complete enough for a fresh execution session to
  reconstruct the context without hidden assumptions from the defining session.
- Work Unit execution is successful when the scoped work is complete,
  verification evidence is recorded, AI review is complete, the AI checklist is
  satisfied, and Human review material states what to inspect, how to inspect
  it, and which approval, rework, merge, or PR promotion decision remains with
  the Human.
- Do not block AI Work Unit completion merely because Human Review,
  approval, rework, merge, or PR promotion has not happened yet.
- Project Core is the short single canonical
  `<project-root>/.agent-factory/specifications/project-core/` package.
- Project Core contains purpose, core principles, scope, Human approval
  boundaries, and unresolved items.
- Design Report is the Human-facing HTML/CSS/JavaScript design artifact.
- Design Report renders detailed Specification data and may render its resolved
  `governed-by` Project Core relation without copying canonical content.
- Design Report may be an expected Work Unit output or a specification input to
  a later Intake. It is not a direct Work Unit basis.
- Work Units are stored under `<project-root>/.agent-factory/work-units/<id>/`.
- Work Unit Outputs are internal and separate from customer-facing Customer
  Deliverables.

## Work Unit Package

Schema version `4.0.0` Work Units use the common sectioned JSON package:

```text
<project-root>/.agent-factory/work-units/<id>/
  data/
    metadata.json
    title.json
    table-of-contents.json
    sections/<section-id>.json
  blocks/index.json
  blocks/**
```

The required profile covers basis, definition, plan, execution context,
acceptance and verification, execution, AI review, Human review, and report.
The basis includes a typed reference to the ready Intake package root with an
anchor to the selected `work-unit-basis` item. Markdown, HTML, CSS, and
JavaScript are optional derived rendering and never replace canonical JSON.

## Boundaries

- The Human is the final approval authority.
- The Human decides approval, rework, rejection, merge, PR promotion,
  deployment, operation, and maintenance approval boundaries.
- AI work must remain traceable from the ready Intake and selected Work Unit
  basis through every applicable Project Core, Specification, or Design Report
  reference to the Work Unit and review output. Do not invent a Specification
  or Design Report link when Intake records it as not applicable.
- Work Unit traceability must point to its ready Intake package, the selected
  Work Unit basis entry, and the source evidence or specification references
  recorded there.
- Agents must separate facts, assumptions, recommendations, and unresolved
  items.
- Agents must surface principle risks and provide evidence.
- Agents must not bypass Human approval boundaries.
