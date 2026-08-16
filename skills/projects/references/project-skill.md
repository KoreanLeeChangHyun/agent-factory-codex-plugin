# Project Skill

## Purpose

The Project Skill is the default AI-facing project source. Keep it concise and
load details progressively from its references. It replaces mandatory
Specification authoring in the normal feedback loop; Specification remains an
explicit Human-selected option.

## Target layout

```text
<project-root>/.agent-factory/skills/project/
  SKILL.md
  references/project.md
  references/decisions.md
  references/progress.md
  diagrams/
```

The plugin repository provides the capability and templates. Each target
project owns its generated Project Skill. Do not create a target-specific
Project Skill inside the Agent Factory plugin repository merely because the
plugin is being developed there.

## AI loading contract

The Main Agent checks for this Project Skill when Agent Factory is active in a
target project. Load `SKILL.md` before project work, then load only the relevant
reference. Project facts may also come from current repository or runtime
evidence and explicit Human statements.

Keep `SKILL.md` below 500 lines. Put stable purpose and operating boundaries in
`references/project.md`, accepted Human decisions in `references/decisions.md`,
and concise completed-work entries in `references/progress.md`. Store
AI-readable diagram JSON or DSL files under `diagrams/`.

## Work-first recording

Project Skill recording follows implementation and Human feedback:

1. Main Agent delegates the bounded task to a Work Agent.
2. Work Agent changes the current Git workspace and returns a compact receipt.
3. Main Agent immediately presents the result to the Human.
4. After Human feedback, Main Agent starts a separate Recording Agent in the
   background.
5. Recording Agent appends only accepted decisions and completed-work facts.

Recording must not delay implementation, result delivery, or the next bounded
task. A recording failure is reported separately and does not invalidate the
work. Use `scripts/project.py`; do not hand-edit its append-only progress and
decision records.

## Tests

Do not run tests, smoke checks, lint, type checks, builds, or verification
commands unless the Human explicitly requests the exact command. Record
`tests not run` when no command was authorized.
