---
name: intake
description: Use for every Agent Factory Intake that turns Human requests and feedback, web evidence, internal analysis, direct user research, Human interview decisions, and specification alignment into a validated sectioned document and executable Work Unit basis. Owns the Intake profile, split JSON package, synthesis, manager-only writes, readiness loop, and Work Unit handoff.
---

# Agent Factory Intake

Prepare the complete basis from which `work-unit-planner` can create a
self-contained Work Unit for a fresh Execution session. Apply `fact-only` and
`agent-rule` throughout Intake.

## Domain Boundary

Use five Intake-related skills:

1. `web-search` owns external web evidence.
2. `analysis` owns internal code, database, data, configuration, log, test,
   runtime, and document evidence.
3. `user-research` owns direct observation of users, operators, their context,
   workflows, usability, and consented research sessions.
4. `interview` owns Human clarification and Human-only decisions.
5. `intake` owns Human requirements and feedback, specification alignment,
   synthesis, the document profile, manager execution, validation, readiness,
   and Work Unit handoff.

The six Intake actions are Human input, web search, internal analysis, user
research, Human decision interview, and specification check or update. Apply
`specification` when editing specification files; it remains an adjacent
lifecycle skill rather than an evidence-acquisition domain.

## Methodological Gates

Before readiness, ensure the Intake has addressed each applicable concern:

- define the problem, desired outcome, success measures, scope, and exclusions;
- identify affected stakeholders, decision owners, requirement sources, and
  missing user or operator groups;
- acquire evidence through the minimum applicable capability skills instead of
  requiring every capability on every Intake;
- identify conflicts, compare viable alternatives, record decision rationale,
  and route the final Human-only choice through `interview`;
- identify technical, operational, security, privacy, legal, accessibility,
  migration, and delivery risks that are applicable to the recorded scope;
- preserve requirement provenance, priority when explicitly decided, change
  history, and traceability into acceptance criteria and Work Unit basis;
- validate correctness, completeness, consistency, feasibility, verifiability,
  stakeholder fit, and Execution sufficiency.

Keep decision analysis and risk assessment inside `intake` until either has a
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
sections. Component schemas under `assets/schema/` own field shapes. The Python
manager owns all canonical writes, table-of-contents generation, block
integrity, validation, and transitions. Do not edit package JSON directly.

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

Use `user-research` instead of treating stated preference as observed behavior.
Use `interview` instead of inventing a Human-only answer. Use a JSON value file
or argument array so shell interpolation cannot reinterpret generated content.

## Manager Commands

```text
python3 scripts/intake.py check-schemas
python3 scripts/intake.py create <package> --id <id> --title <title> --project-id <project> --language <language> --theme <theme>
python3 scripts/intake.py show <package> [--section <section-id>]
python3 scripts/intake.py title-set <package> <title>
python3 scripts/intake.py metadata-set <package> <field> --value-file <json-file>
python3 scripts/intake.py section-put <package> --value-file <section.json>
python3 scripts/intake.py section-item-put <package> <section-id> --value-file <item.json> [--subsection <id>]
python3 scripts/intake.py section-items-put <package> <section-id> --value-file <items.json> [--subsection <id>]
python3 scripts/intake.py section-add <package> --value-file <section.json> [--before <id>|--after <id>]
python3 scripts/intake.py section-move <package> <section-id> (--before <id>|--after <id>)
python3 scripts/intake.py section-remove <package> <optional-section-id>
python3 scripts/intake.py validate <package> [--full]
python3 scripts/intake.py transition <package> <draft|validating|ready|blocked|closed|superseded>
python3 scripts/intake.py block-put <package> <source> --path blocks/<path> --media-type <type> --description <text>
python3 scripts/intake.py block-remove <package> blocks/<path>
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
- The Human owns business decisions, approvals, preferences, scope tradeoffs,
  and risk acceptance.

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

The manager
serializes package access with a project-runtime lock and commits multi-file
changes through a recovery journal. On the next manager invocation, an
interrupted transaction is restored to its recorded preimage before the
requested command runs. Do not place actual style, CSS, or style-variable data
in section content or attributes; JSON stores only semantic data and the theme
identifier.

## Handoff

After `ready` validation succeeds, hand the package to `work-unit-planner`.
Report the Intake id, validation result, specification impact, remaining
non-blocking items, and Work Unit basis items.
