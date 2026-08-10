# Agent Factory Intake Management

## Boundary

An Intake is an append-only JSON ledger for one goal or topic. The Main Agent
decides whether new activity belongs to the active topic or starts another
Intake unless the Human explicitly specifies the boundary. Human instructions
always override the default Agent judgment.

Record every applicable activity: Human input, Agent response, interview, web
search, internal analysis, user research, observation, Specification check,
decision, correction, and feedback. Intake stores what happened and its source;
it does not require a synthesized requirements document.

## Mandatory Manager Script Gate

Treat `scripts/intake.py` as a hard precondition for every canonical operation.
Use it before mutation. Never create, edit,
delete, copy, move, or repair canonical Intake JSON with direct filesystem
writes, patches, ad hoc scripts, or generic tools. If the manager cannot express
the required operation, stop before mutation and report the capability gap. Do
not fall back to direct JSON editing and do not create an exception path.

Read `references/intake-structure.md` before authoring or reviewing an Intake.
Use the applicable capability reference for the activity being recorded.

- `references/intake-management.md` owns ledger management and routing.
- `references/analysis.md` owns internal analysis activity.
- `references/web-search.md` owns external published-source activity.
- `references/user-research.md` owns direct observation activity.
- `references/interview.md` owns Human-only decision interviews.

## Commands

```text
python3 scripts/intake.py check-schemas
python3 scripts/intake.py create <package> --id <id> --topic <topic> --project-id <project> --language <language>
python3 scripts/intake.py show <package> [--entry <entry-id>]
python3 scripts/intake.py entry-put <package> <typed-data-arguments>
python3 scripts/intake.py entry-items-put <package> <typed-data-arguments>
python3 scripts/intake.py topic-set <package> <topic>
python3 scripts/intake.py validate <package> [--full]
python3 scripts/intake.py session-bind <package> <session-id>
python3 scripts/intake.py session-show <package>
python3 scripts/intake.py session-clear <package>
python3 scripts/intake.py block-put <package> <source> --path blocks/<path> --media-type <type> --description <text>
python3 scripts/intake.py delete <package> --confirm-id <id> [--allow-invalid]
```

Supply only typed semantic arguments. The manager adds sequence and recording
time, constructs JSON, increments `documentVersion` once per semantic append,
and validates the package. Use `entry-items-put` when one activity produces a
related batch that should share one document revision.

Example:

```text
python3 scripts/intake.py entry-put <package> \
  --string /id HUMAN-001 \
  --string /actor/type human \
  --string /activity user-input \
  --string /content/message <message>
```

Corrections and changed decisions are new related entries, never replacements.
Session bind and clear are operational metadata changes and do not increment
`documentVersion` or `updatedAt`.

## Delegated Intake Agent

The Main Agent may delegate substantial `analysis`, `web-search`, or
`user-research` activity through `scripts/intake_agent_exec.py`. The delegated
Agent records its activity through `intake.py` and returns a compact result.
The Main Agent retains topic-boundary judgment, Human communication, optional
Specification routing, Work Unit creation, execution admission, and review.

## Specification and Work Unit routing

Specification creation is optional. When a relevant Specification exists,
record the check and reference it. Create or update one only when the Human or
Main Agent determines a reusable refined contract is warranted, subject to any
explicit Human condition.

A Work Unit is an Agent delegation contract. The Main Agent may create it from
the exact sufficient Intake entries, with or without a Specification. Intake
does not transition to ready and is not closed when a Work Unit is created.

## Output

Report the Intake id, topic, appended entry ids, validation result, sources and
limitations, and any Work Unit or optional Specification routing performed.
