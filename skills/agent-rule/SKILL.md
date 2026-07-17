---
name: agent-rule
description: Always use for Agent Factory work before modifying files, designing or changing code, reviewing code, refactoring, changing skills or project artifacts, or making architecture, frontend, runtime, API, library, framework, state-model, DOM ownership, security, verification, or workflow claims. Combines Agent Factory engineering principles, evidence-first source discipline, and intent confirmation before edits.
---

# Agent Rule

Use this skill as the general Agent Factory rule gate before edits, design,
code, review, refactoring, artifact changes, skill changes, or workflow changes.

## Core Rule

Do not invent requirements, architecture, APIs, state models, frontend patterns,
runtime behavior, library usage, ownership models, identifiers, fallback scopes,
or workflow rules.

Before editing, make sure the change is grounded in:

- Explicit Human instruction.
- Current repository evidence.
- Relevant Design Document, Work Unit, review, runtime, or test evidence.
- Current authoritative external sources when the change depends on a public
  technology, standard, browser behavior, framework, library, API, protocol,
  security, performance, or architecture claim.

If evidence does not support the proposed change, change the approach or ask
the Human.

## Critical Thinking Rule

Do not act as a yes-man. Agreement is only valid when the request is supported
by explicit Human facts, repository evidence, runtime evidence, Work Unit or
Design Document content, or authoritative research.

Challenge the request when there is a concrete evidence gap, contradiction,
risk, missing decision, hidden assumption, or cheaper maintainable alternative.
Do not invent objections for their own sake.

Before accepting a design, workflow, implementation, review, diagram, artifact,
or recommendation direction, check:

- Evidence: what explicit facts support the request.
- Conflict: whether inspected evidence or recorded decisions contradict it.
- Missing basis: which required facts, ownership, boundaries, runtime behavior,
  approval rules, security constraints, or state model details are absent.
- Risk: what could break, mislead, overfit, or become hard to maintain.
- Alternative: whether a simpler, safer, reversible, or lower-cost option
  satisfies the same explicit goal.
- Decision owner: whether the next choice belongs to the Human.

When the request is sound, proceed without performative doubt.

When the request is weak, contradictory, risky, or underspecified:

- Say the issue directly.
- Tie the objection to evidence or a specific missing fact.
- Propose the smallest correction that preserves the Human's goal.
- Ask one focused question only when a Human-only decision blocks progress.

Do not soften contradictions into agreement. Do not say "sounds good" when the
evidence says the proposal is wrong, incomplete, or likely to create rework.

## Agent Factory Engineering Principles

Apply these principles to design, code, refactoring, review, Work Units,
artifacts, and skill work:

- SOLID: keep object and module boundaries change-local and extensible.
- SoC: separate different responsibilities and concerns explicitly.
- DRY: do not repeat the same knowledge, rule, or ownership decision in
  multiple places.
- YAGNI: do not add features, abstractions, or structure not needed by the
  current recorded requirement.
- Refactoring: improve internal structure while preserving external behavior
  unless the Human explicitly approves behavior change.
- CI/CD: keep integration, verification, and deployment paths automatable and
  deployable.
- Test Pyramid: balance unit, integration, and E2E checks according to risk and
  blast radius.
- Agile Principles: keep changes small, get feedback quickly, and improve
  continuously.
- Human-in-the-loop Review: AI-produced results require Human review and Human
  responsibility.
- Spec-Driven Development: define specification and success criteria before
  implementation.
- Evaluation: judge output through criteria, tests, and metrics.
- Observability: make inputs, outputs, decisions, and errors traceable.
- Security by Design: include security, authorization, and data protection from
  the design phase.

## Lifecycle Rule

All Agent Factory work follows:

```text
Intake -> Work Unit -> Execution -> Review
```

- Intake coordinates Human input, external research, internal analysis, user
  research, Human decision interviews, and specification alignment, then repeats deterministic and
  semantic validation until its canonical package is ready.
- Work Unit defines a self-contained minimum Codex Goal execution unit from a
  validated ready Intake package.
- Execution performs the scoped Work Unit work through
  Plan -> Work -> AI Review -> Report.
- Review means Human review.

## Intent Confirmation

Do not edit first when the user's intent or scope can be interpreted in more
than one way.

Before broad or ambiguous edits:

1. Restate the requested change in 1-3 short sentences.
2. List explicit facts from the Human and inspected repository evidence.
3. List what is unspecified.
4. State the edit boundary: files or areas to touch, and files or areas not to
   touch.
5. Ask for confirmation when any unspecified item could change behavior,
   layout, icons, wording, data, tests, commits, runtime, generated artifacts,
   or existing uncommitted work.

Ask before editing when:

- The request uses broad words such as `통일`, `정리`, `수정`, `개선`, `맞춰`,
  `좋겠습니다`, `간단히`, `비슷하게`, `형태`, or `느낌`.
- UI work could affect position, icon, visible text, DOM structure, keyboard
  behavior, focus behavior, accessibility, spacing, or responsive layout.
- The target file, component, selector, route, API, artifact, or skill is not
  named.
- The worktree has unrelated uncommitted changes in files that may be touched.
- The change could require a commit, rollback, restart, migration, destructive
  command, or generated artifact update.

For UI work, preserve position, icon, visible text, DOM structure, event
behavior, keyboard behavior, data model, persistence, and unrelated tests unless
the Human explicitly asks to change them.

## Change Safety

- Do not roll back commits unless the Human explicitly asks for a commit
  rollback.
- Do not overwrite, restore, discard, reset, or replace uncommitted work unless
  the Human explicitly approves that exact file and operation.
- Even after the Human approves an operation that can remove or replace
  uncommitted work, ask for one more explicit confirmation before executing it.
- Do not treat a broken runtime state as permission to revert files.
- Before any operation that can remove or replace uncommitted changes, show the
  exact files and exact command or edit, then wait for Human approval.
- Prefer read-only diagnosis first: inspect status, diffs, logs, runtime state,
  browser errors, and tests before proposing any destructive or replacement
  action.
- If a file appears broken but contains uncommitted work, preserve it first and
  ask the Human how to proceed.

## Runtime Restart Safety

- Do not restart the Agent Factory server, frontend, backend, supervisor, or
  all runtime targets on your own.
- Runtime restart is allowed only when the Human explicitly asks for server
  restart.
- Even after the Human explicitly asks for server restart, ask for one more
  explicit confirmation before executing any restart command, API call, button
  flow, script, or supervisor operation.
- If the Human does not provide the second confirmation, do not restart.

## Frontend Cache And Verification

- When changing frontend JavaScript modules while an existing Agent Factory
  frontend server is running, do not assume the browser or Vite module graph has
  loaded the newest file.
- Do not restart the frontend server just to clear module cache unless the
  Human explicitly asks for restart and gives the required second confirmation.
- Prefer read-only cache diagnosis first: inspect the served module with
  `curl`, compare it against the local file, and check whether an import chain
  uses query-string cache keys.
- If a changed module is imported through existing query-string cache keys,
  update only the necessary import chain from the changed module back to the
  frontend entrypoint.
- Keep cache-key updates scoped to the touched behavior. Do not rename broad
  cache keys or sweep unrelated imports.
- For small frontend UI behavior changes, default to focused verification:
  syntax checks for touched JavaScript, relevant minimal-app boundary checks,
  and the Playwright spec or grep that covers the changed behavior.
- Run full `npm run check`, full E2E, mobile checks, or screenshot checks only
  when the change touches shared runtime wiring, global layout/CSS, broad API
  behavior, or when the Human asks for full verification.
- If focused verification passes but a broader check fails in an unrelated
  area, record the exact failing command, failing file or assertion, and whether
  the failure is in files touched by the current work. Do not fix unrelated
  failures unless the Human approves that expanded scope.

## Evidence-First Workflow

Before code, architecture, frontend, runtime, API, library, framework,
state-model, DOM ownership, security, or performance edits:

1. Inspect local evidence: files, tests, logs, runtime output, DOM snapshots,
   Design Documents, Work Units, or review artifacts.
2. Check authoritative external sources when the claim depends on public
   technology or current external behavior.
3. Separate source-backed facts from project-specific decisions.
4. Explain the implementation boundary in terms of the evidence.
5. Edit only after the basis is clear.
6. Verify with focused tests or checks that cover the changed behavior.
7. In the final answer, name sources used and local verification commands when
   relevant.

For filesystem security boundaries, a path check is not proof that a later
path operation is safe. When an attacker can mutate directories between check
and use, anchor traversal and mutation to trusted directory descriptors, reject
symlinks without following them, and add an adversarial regression test that
performs the swap between validation and use. Static pre-existing-symlink tests
alone do not cover this race.

For executable command evidence, validate the exact recorded invocation with
the installed command parser and preserve the accepted option order. For final
repository evidence, update human-facing reports first, capture repository
state afterward, register the capture, and verify a second capture has the same
changed-path set except for an explicitly bounded evidence-registration delta.

Prefer authoritative sources in this order:

1. Official project documentation for the exact tool or framework.
2. Standards bodies and primary platform documentation such as WHATWG, W3C,
   TC39, MDN, Node.js, Python, browser vendor docs, or database vendor docs.
3. Official source code, RFCs, design docs, API references, migration guides, or
   release notes from the owning project.
4. Peer-reviewed papers or primary research sources for research-based work.

Do not use blogs, Medium posts, Stack Overflow, Reddit, generated answers, or
SEO tutorials as the basis for code or architecture unless they are only
secondary context and a primary source is also checked.

## Hard Stops

Stop and ask before editing when:

- No authoritative source supports a required external technology claim.
- Repository evidence contradicts the proposed design.
- The change would replace a domain model with an invented fallback, sentinel,
  pseudo-scope, cache key, or hidden global state.
- The implementation requires a broad architecture or workflow decision not
  recorded in the Design Document, Work Unit, or Human instruction.
- The change can remove, overwrite, reset, or replace uncommitted work.

## Agent Factory State Model Rule

For Agent Factory session UI work, preserve this ownership chain unless the
Human explicitly changes it:

```text
Session -> DOM -> State
```

- A session owns its DOM.
- The session-owned DOM owns visible message, composer, loading, planning, and
  status surfaces for that session.
- State is keyed by the real session id or an explicit pending session id.
- No fake fallback scope may stand in for a missing session.
- If no session is active, no session-owned message, composer, loading, or
  status surface should be visible.

Do not introduce new sentinel ids, pseudo-session ids, pseudo-scopes, or hidden
default session names to make code paths easier.

## Reporting

When this skill affects the work, briefly report:

- Local evidence inspected.
- Authoritative sources checked when relevant.
- The source-backed conclusion.
- Confirmation boundary or Human decision needed, if any.
- Verification commands or checks run.
