---
name: fact-only
description: Always use this skill for Agent Factory lifecycle work. Control scope only by explicit user statements, canonical Intake, Project Core, Specification, Design Report, Work Unit content, repository evidence, runtime evidence, or current authoritative research; avoid inference.
---

# Fact Only

Only explicit user statements and inspected authoritative project evidence are
facts. Anything not explicitly stated or evidenced is unspecified. Do not infer,
assume, expand, reinterpret, or fill gaps. If required information is missing,
ask a clarification question before writing design or code.

This skill is a hard gate. If another skill, habit, prior conversation summary,
or convenience conflicts with this skill, follow this skill first.

## Rules

- Treat only explicit user statements as facts.
- For Agent Factory lifecycle work, also treat inspected canonical Intake,
  Project Core, Specification, Design Report, Work Unit records, repository
  files, runtime output, test output, and command output as project evidence.
- Treat anything not explicitly stated by the user as unspecified.
- Do not modify code unless the change is grounded in explicit user facts and
  either current web research or actual project/runtime data.
- Before code edits, fact-check the basis using web research when the source is
  external/current, or actual data from the repository, runtime, tests, logs,
  screenshots, browser DOM, command output, or user-provided files when the
  source is local.
- For external product, standard, theme, library, API, or design-system values,
  use the official or primary source before editing code. Do not approximate
  those values from memory.
- Example: if the user asks for VS Code theme colors, search and inspect the
  actual VS Code theme source files first, then reflect those source-backed
  values in code.
- If neither web research nor actual data supports the change, ask before
  editing code.
- Do not infer.
- Do not assume.
- Do not expand the user's wording.
- Do not reinterpret the user's wording.
- Do not fill gaps.
- If required information is missing, ask a clarification question before
  writing design or code.
- If the user's request is ambiguous, ask a clarification question before
  writing design or code.
- Keep facts, assumptions, recommendations, and unresolved items separate.
- Do not treat unapproved assumptions as requirements.
- Do not restate an assumption as if the Human said it.
- Do not add a hidden constraint, target, file path, naming rule, lifecycle
  rule, storage rule, routing rule, or implementation boundary unless the Human
  explicitly said it or inspected repository evidence proves it.
- Do not choose between multiple plausible interpretations silently. Stop and
  ask one focused question.
- Surface principle risks and missing evidence.
- Before asking or declaring that no interview is needed, apply the Interview
  Decision Gate in `references/interview-decision-gate.md`.
- Do not say "no interview is needed" by habit. Say it only after checking that
  no Human-only decision, conflict, ambiguity, approval boundary, or lifecycle
  change is present.

## No Assumption Hard Stop

Stop before acting when any of these are true:

- The next action depends on a meaning the Human did not explicitly state.
- A request names an object but not the exact field, file, directory, behavior,
  or artifact boundary to change.
- The same phrase could reasonably mean more than one operation.
- The work would rename, move, delete, overwrite, replace, or regenerate files
  and the exact target set is not explicit.
- The work would change skill names, skill directories, routing names,
  frontmatter, global propagation behavior, or AGENTS behavior and the exact
  naming or target rule is not explicit.
- The answer would summarize the Human's intent using words the Human did not
  use and those words could change the implementation.

When a hard stop is hit:

1. State the exact missing fact.
2. State what evidence was inspected.
3. Ask one focused clarification question.
4. Do not edit files until the Human answers.

## Evidence Labels

Before nontrivial edits, separate basis into these labels:

- `Human Fact`: direct user statement.
- `Repository Fact`: inspected file, command output, test output, or runtime
  evidence.
- `External Fact`: authoritative current source.
- `Unspecified`: anything not covered by the above.

Only `Human Fact`, `Repository Fact`, and `External Fact` may define scope.
`Unspecified` items may not be implemented.

## Reporting Rule

In final reports, do not claim a rule, reason, or intent unless it is backed by
an explicit Human Fact or inspected evidence. If a previous response included
an assumption, identify it as an assumption and stop using it as a basis.
