---
name: lifecycle
description: Use when Codex must follow the Agent Factory lifecycle from Intake through Work Units, execution, Human review, merge or rework, and Human-decided PR promotion.
---

# Agent Factory Lifecycle

Read `references/common-document-contract.md` when creating, validating, or
reviewing Intake, Specification, or Work Unit document structure and profiles.

Use this skill as the top-level router for the Agent Factory workflow in Codex
CLI.

This is an Agent Factory skill for applying the lifecycle consistently in
target projects and in this repository.

## Source Location

Use this Plugin's `skills/` directory as the single active location for Agent
Factory skills and bundled assets. Resolve references, schemas, scripts, tests,
and templates relative to the owning bundled skill. Do not use legacy
standalone skill roots as active Agent Factory skill locations.

## Dynamic Path Resolution

- Treat the root directory opened in the current editor, IDE, or Codex
  workspace as `<project-root>`.
- Resolve Agent Factory artifacts from `<project-root>/.agent-factory/`. Do not
  hardcode a user home, machine-specific workspace path, or Plugin installation
  path.
- Resolve bundled Plugin resources from the installed Plugin and the owning
  skill, independently of `<project-root>`.
- Do not substitute the shell's current subdirectory for `<project-root>` when
  the opened workspace root is available.
- If no root directory is open, or a multi-root workspace does not identify the
  target root, stop and ask the Human which root is in scope.

## Lifecycle

Use this required artifact and approval lifecycle:

```text
Intake
  -> Work Unit
  -> Execution
  -> Review
```

Use these lifecycle phases:

- Intake uses `intake` to coordinate Human requirements and feedback, external
  research, internal code or data analysis, direct user research, Human
  decision interviews, and specification checks or updates. It repeats write -> manager apply -> deterministic
  validation -> semantic review -> revision until the canonical Intake package
  is ready for Work Unit planning.
- Work Unit packages the accepted basis into the minimum `/goal
  <work-unit-id>` execution unit for a fresh Codex Goal session.
- Execution runs one Work Unit through Plan -> Work -> AI Review -> Report,
  performs scoped artifact writing when it is an expected Work Unit output,
  records verification evidence, performs AI review, and prepares any Human
  approval, rework, merge, or PR promotion decision material.
- Review is Human review after Execution.

Intake checks and updates relevant specification source when accepted
requirements, feedback, or evidence changes it. Implementation and other scoped
delivery artifact writing belongs to Work Unit Execution.

Every Agent Factory task must pass through Intake -> Work Unit -> Execution ->
Review, including analysis, research, Design Document work, Design Report work,
document work, code work, verification, operation, and maintenance.

Detailed lifecycle rules are in `references/lifecycle.md`. Read that reference
when creating or updating Project Core, Design Report, Work Units, execution
records, review output files, or handoff material.

## Lifecycle Entry

Agent Factory work can begin when a project starts, while it is in progress, at
release handoff, or during maintenance. Always start with `intake`; do not add a
separate entry skill or mandatory pre-Intake questionnaire.

When timing is not explicit, record that uncertainty in Intake and use
`interview` only when the timing changes scope or another Human-owned decision.
Goal mode may be recommended for long-running work, but it is not a lifecycle
phase and may be created only on explicit Human request.

Use these routes:

- New project start: complete a canonical Intake, transition it to `ready`, and
  create Work Units from its accepted basis. Create or update Specification,
  Project Core, Design Document, or Design Report only when the Intake impact
  decision and Work Unit scope require those outputs.
- In-progress project adoption: collect the current project baseline through
  Intake, validate specification alignment, transition Intake to `ready`, and
  create Work Units only from its Work Unit basis entries.
- Ending or release-handoff adoption: collect final-state, review, release,
  deliverable, risk, and handoff baseline material, create only approved
  finalization, rework, verification, release, or handoff Work Units, and use
  those Work Units during Execution for scoped artifact writing.
- Maintenance or operations adoption: collect runtime, deployment, incident,
  behavior, maintenance request, and approval baseline material during Intake,
  transition Intake to `ready`, and create scoped Work Units from it.

## Skill Routing

- Use `fact-only` for all Agent Factory lifecycle work.
- Use `intake` for every Intake package, the five Intake-related skill domains, its manager
  validation loop, and readiness handoff to `work-unit-planner`.
- Use `interview` when the Human must decide scope, priority,
  architecture, approval boundaries, risk, or promotion.
- Use `web-search` when recording web research, external-source
  verification, comparison research, recommendation evidence, or investigation
  summaries.
- Use `analysis` for internal code, repository, database, data, configuration,
  log, test, runtime, and existing-document evidence during Intake.
- Use `user-research` when Intake needs direct observation, contextual inquiry,
  workflow shadowing, usability sessions, journey reconstruction, or review of
  consented user-research artifacts.
- Use `diagram` when creating, updating, reviewing, or choosing
  diagrams, diagram data models, JavaScript diagram renderers, architecture
  diagrams, class diagrams, sequence diagrams, ERDs, workflows, state diagrams,
  deployment diagrams, data-flow diagrams, UI-flow diagrams, or traceability
  graphs.
- Use `agent-rule` before modifying files, designing, coding, reviewing,
  refactoring, changing skills or artifacts, or making architecture, frontend,
  runtime, API, framework, state-model, DOM ownership, security, verification,
  or workflow claims.
- Use `specification` during Intake to check or update relevant specification
  source and during Execution when scoped work produces new design facts.
- Use `work-unit-planner` when transforming a validated `ready` Intake package
  into executable Work Units.
- Use `work-unit-execution` for named Work Unit Goal Execution to validate
  the explicit repository, base ref, dedicated branch, and linked worktree path;
  prepare or inspect the execution worktree; and record canonical JSON evidence.
- Use `human-review` for Human-facing review artifacts and final
  review material.
- Use `svg-icon` when creating, replacing, reviewing, or refactoring
  user-facing UI icons or icon-like controls.

## Execution Rules

- Do not jump from idea to implementation unless the user explicitly asks to
  bypass the lifecycle.
- Keep Agent Factory lifecycle records under
  `<project-root>/.agent-factory/`.
- Use these canonical artifact roots:
  - `<project-root>/.agent-factory/intakes/<intake-id>/` for the canonical
    sectioned package whose metadata, title, manager-owned table of contents,
    individual section files, and connected blocks combine Human input,
    interview, user research, web research, internal analysis, specification alignment, readiness,
    and Work Unit basis.
  - `<project-root>/.agent-factory/specifications/` for Specification packages.
  - `<project-root>/.agent-factory/work-units/` for Work Unit packages, execution evidence, review
    material, and Work Unit outputs.
  - `<project-root>/.agent-factory/deliverables/` for customer-facing software engineering deliverable
    documents.
- Keep Agent Factory HOME runtime paths under `runtime/` separate from current
  lifecycle records under `<project-root>/.agent-factory/`.
- Do not create `INDEX.md` files as artifact source of truth.
- When the Human submits `/goal <work-unit-id>` or otherwise provides only a
  Work Unit id as the Goal objective, resolve the id to
  `<project-root>/.agent-factory/work-units/<work-unit-id>/` before planning.
- A named Work Unit may also execute in a fresh `codex exec` session. Treat its
  explicit Work Unit id and recorded execution context as the execution
  identity; do not require persistent Goal mode for this route.
- For named Work Unit Goal execution in this project, work in Korean for
  planning, progress updates, review summaries, reports, and other
  Human-readable communication. Keep commands, file paths, identifiers, code,
  API names, package names, branch names, and exact log output unchanged.
- For named Work Unit Goal execution, validate and read the full sectioned Work
  Unit package before work begins: metadata, title, table of contents, all
  canonical sections, the block index, and referenced blocks.
- Before scoped edits in named Work Unit Goal execution, use
  `work-unit-execution` with the package's explicitly resolved execution
  context to prepare or inspect the dedicated branch and linked worktree. Do not
  invent fallback path names. Derive the branch as
  `work-unit/<work-unit-id>` and reuse the same registered branch and worktree
  pair for re-execution or rework. Record the returned canonical JSON in the
  Work Unit evidence.
- Run worktree cleanup only after an explicit Human cleanup decision. Do not
  remove a dirty worktree, force removal, delete a branch, merge, or promote a
  PR on the Human's behalf.
- Execute only the resolved Work Unit scope unless the Human explicitly expands
  or changes scope. If the id cannot be resolved, more than one package
  matches, or the package lacks enough basis for a fresh session, stop and ask
  the Human before editing.
- Do not create executable Work Units from vague ideas or unvalidated notes.
  Create them from a canonical Intake package whose status is `ready`; that
  package may incorporate Design Report content, Human requests, Goal records,
  rework, operation, maintenance, repository evidence, runtime evidence, or
  review evidence.
- Before implementation, migration, cleanup, or artifact-writing work, create or
  update the relevant Work Unit unless the user explicitly asks to bypass the
  lifecycle.
- Keep Work Unit scope small enough to execute and review.
- Treat each Work Unit as a self-contained minimum execution and review unit for
  a fresh Codex Goal session. The session that defines the Work Unit and the
  session that executes the Work Unit are separate. The Work Unit must therefore
  contain enough basis, scope, expected output, AI checklist, verification, Human
  checklist, Human review method, and unresolved items for the execution
  session to work without relying on hidden context from the defining session.
- For code Work Units, define tests before implementation.
- Create a Goal only when the Human explicitly requests Goal creation. A Goal
  recommendation, active lifecycle, or available Goal tool is not itself
  authorization.
- During Execution, prepare evidence, AI review results, a Human checklist, and
  a Human review method that explains what to inspect, how to inspect it, and
  which approval, rework, merge, or PR promotion decisions remain with the
  Human during Review.
- Treat the Work Unit as AI-successful and ready for Human review when the
  scoped work, verification evidence, Human checklist, and Human review method
  are ready. Do not block or fail AI completion merely because Human final
  review, approval, merge, or PR promotion has not happened yet.

## Output

State which lifecycle phase the work is in, which skills were applied, which
artifacts changed, and what remains unresolved.
