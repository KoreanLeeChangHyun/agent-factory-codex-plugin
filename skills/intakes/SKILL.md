---
name: intakes
description: Use for every Agent Factory Intake that turns Human requests and feedback, web evidence, internal analysis, direct user research, Human interview decisions, and specification alignment into a validated sectioned document and executable Work Unit basis. Owns the Intake profile, split JSON package, synthesis, readiness loop, and Work Unit handoff. All canonical Intake package operations must go through scripts/intake.py and fail closed when that script cannot perform the operation.
---

# Agent Factory Intake

Prepare the complete basis from which `work-unit-manager` can create a
self-contained Work Unit for a fresh Execution session. Apply `factory-rule`
throughout Intake.

## Mandatory Manager Script Gate

Treat `scripts/intake.py` as a hard precondition for every canonical Intake
package operation. Resolve it from this skill directory and invoke it before
creating, showing, mutating, validating, transitioning, registering or removing
blocks, or recovering an Intake package.

- Use the manager command that owns the requested operation. Use `show` and
  `validate` for authoritative package inspection and validation.
- Supply only typed semantic arguments. Let the manager construct, serialize,
  order, version, and transactionally write canonical JSON.
- Never create, update, delete, replace, move, or repair canonical Intake JSON
  with `apply_patch`, shell redirection, an ad hoc program, file copy or move,
  temporary JSON files, or any generic filesystem or MCP write tool.
- Never add, invoke, or rely on a hook to enforce this rule. The skill
  instruction and exact manager invocation are the enforcement contract.
- If `scripts/intake.py` is unavailable, fails, or cannot express the required
  operation, stop before mutation. Report the exact command, package, operation,
  and failure or capability gap. Do not fall back to direct JSON editing and do
  not create an exception path.

## Domain Boundary

Use five Intake-related skills:

1. `intake-web-search` owns external web evidence.
2. `intake-analysis` owns internal code, database, data, configuration, log, test,
   runtime, and document evidence.
3. `intake-research` owns direct observation of users, operators, their context,
   workflows, usability, and consented research sessions.
4. `intake-interview` owns Human clarification and Human-only decisions.
5. `intakes` owns Human requirements and feedback, specification alignment,
   synthesis, the document profile, manager execution, validation, readiness,
   and Work Unit handoff.

The six Intake actions are Human input, web search, internal analysis, user
research, Human decision interview, and specification check or update. Apply
`specifications` when editing specification files; it remains an adjacent
lifecycle skill rather than an evidence-acquisition domain.

## Methodological Gates

Before readiness, ensure the Intake has addressed each applicable concern:

- define the problem, desired outcome, success measures, scope, and exclusions;
- identify affected stakeholders, decision owners, requirement sources, and
  missing user or operator groups;
- acquire evidence through the minimum applicable capability skills instead of
  requiring every capability on every Intake;
- identify conflicts, compare viable alternatives, record decision rationale,
  and route the final Human-only choice through `intake-interview`;
- identify technical, operational, security, privacy, legal, accessibility,
  migration, and delivery risks that are applicable to the recorded scope;
- preserve requirement provenance, priority when explicitly decided, change
  history, and traceability into acceptance criteria and Work Unit basis;
- validate correctness, completeness, consistency, feasibility, verifiability,
  stakeholder fit, and Execution sufficiency.

Keep decision analysis and risk assessment inside `intakes` until either has a
distinct recurring trigger, workflow, and reusable contract that justifies a
separate capability skill. When uncertainty can only be resolved by building a
prototype or running an experiment, create a Work Unit basis item; do not build
it during Intake.

## Canonical Package

Store one sectioned package at:

```text
<project-root>/.agent-factory/intakes/<intake-id>/
  data/metadata.json
  data/title.json
  data/table-of-contents.json
  data/sections/<section-id>.json
  blocks/index.json
  blocks/**
```

Read `references/intake-structure.md` before authoring or reviewing a package.
The profile in `assets/profiles/intake.profile.json` owns required and optional
sections. The Intake metadata schema remains under `assets/schema/`; shared
title, table-of-contents, section, and block-index schemas come from
`factory-lifecycle/assets/schema/sectioned-document/`. The Intake adapter configures the
lifecycle-owned Python engine, which owns all canonical writes,
table-of-contents generation, block integrity, and transaction mechanics;
Intake retains its transitions and semantic validation. Do not edit package
JSON directly.

Use only `scripts/intake.py` with typed semantic arguments for canonical Intake
package management. The Mandatory Manager Script Gate applies without an
exception.

The title renders as H1, top-level sections as H2, and optional subsections as
H3. Reject deeper nesting. Keep large content in its own section file and large
non-JSON material in `blocks/`; split a request into another Intake when section
separation and one subsection level are still insufficient.

## Required Loop

Repeat until readiness passes:

1. Write one evidence-backed section or content-item candidate.
2. Apply it with `section-put`, `section-item-put`, or one
   `section-items-put` batch for a large same-section update.
3. Run `validate` immediately.
4. Review completeness, consistency, traceability, and Execution sufficiency.
5. Revise the failed section or return to the owning capability skill.

Use `intake-research` instead of treating stated preference as observed behavior.
Use `intake-interview` instead of inventing a Human-only answer. The LLM supplies only
typed semantic data arguments; the manager constructs and serializes JSON.
Pass commands as an argument array so shell interpolation cannot reinterpret
generated content. Never compose JSON strings or temporary JSON value files.

## Manager Commands

```text
python3 scripts/intake.py check-schemas
python3 scripts/intake.py create <package> --id <id> --title <title> --project-id <project> --language <language> --theme <theme>
python3 scripts/intake.py show <package> [--section <section-id>]
python3 scripts/intake.py title-set <package> <title>
python3 scripts/intake.py metadata-set <package> <field> <typed-data-arguments>
python3 scripts/intake.py section-put <package> <typed-data-arguments>
python3 scripts/intake.py section-item-put <package> <section-id> <typed-data-arguments> [--subsection <id>]
python3 scripts/intake.py section-items-put <package> <section-id> <typed-data-arguments> [--subsection <id>]
python3 scripts/intake.py section-add <package> <typed-data-arguments> [--before <id>|--after <id>]
python3 scripts/intake.py section-move <package> <section-id> (--before <id>|--after <id>)
python3 scripts/intake.py section-remove <package> <optional-section-id>
python3 scripts/intake.py validate <package> [--full]
python3 scripts/intake.py transition <package> <draft|validating|ready|blocked|closed|superseded>
python3 scripts/intake.py block-put <package> <source> --path blocks/<path> --media-type <type> --description <text>
python3 scripts/intake.py block-remove <package> blocks/<path>
```

Example:

```text
python3 scripts/intake.py section-item-put <package> request-and-goal \
  --string /id REQUEST-001 \
  --string /kind human-request \
  --string /content/request <request-text>
```

## Readiness Boundary

- The manager checks schemas, the Intake profile, title and table-of-contents
  integrity, section order and depth, paths, resolvable typed references, the
  exact registered block file set, transitions, required content kinds, and
  minimum ready-state invariants. Fast validation checks block size; `--full`
  also recomputes every block hash, and transition to `ready` always performs
  full validation.
- The LLM checks evidence quality, semantic completeness, conflicts,
  acceptance criteria, specification consistency, and hidden-context risk.
- The Human owns business decisions, explicit Work Unit execution requests,
  result review (`rework` or `complete`), preferences, scope tradeoffs, and risk
  acceptance.

Transition to `ready` only when every readiness flag is true, `reviewedAt` is
recorded, every profile-required content kind exists, no blocking open item or
pending interview remains, specification impact is resolved, and at least one
Work Unit basis item exists. Schema validity alone is not readiness.

Use terminal `closed` for a completed historical Intake whose accepted work no
longer needs a new Work Unit. Use terminal `superseded` when a later Intake,
decision, Specification, or contract replaces it. Record disposition evidence
before either transition. Do not use these states to hide unresolved active
work.

Every successful mutation increments `documentVersion` once. A mutation of a
`ready` Intake atomically returns it to `draft`, sets semantic readiness flags
to `false`, and clears `readiness.reviewedAt`; `closed` and `superseded` Intake
packages reject mutation. This Intake lifecycle rule is conditional on
`artifactType: intake` because the Work Unit manager reuses the common
sectioned-package mechanics.

The manager commits multi-file changes through a recovery journal. On the next
manager invocation, an
interrupted transaction is restored to its recorded preimage before the
requested command runs. Do not place actual style, CSS, or style-variable data
in section content or attributes; JSON stores only semantic data and the theme
identifier.

## Handoff

After `ready` validation succeeds, hand the package to `work-unit-manager`.
Report the Intake id, validation result, specification impact, remaining
non-blocking items, and Work Unit basis items.

There is no Git handoff, checkpoint, immutable snapshot, or approval boundary
for canonical Intake data. The primary main agent performs one sufficiency
check immediately before an explicitly requested Work Unit launch. Once
launched, execution continues without repeating readiness or decision checks.
Intake manager ownership remains limited to canonical JSON construction,
mutation, and validation in the primary repository.
