---
name: analysis
description: Use for Agent Factory internal system and project analysis during Intake, including code, repository structure, databases, aggregate analytics, data, configuration, logs, tests, runtime behavior, and existing documents. Records inspected evidence in the active canonical Intake; use user-research instead for direct observation, contextual inquiry, usability sessions, or interpretation of participant research sessions.
---

# Agent Factory Internal Analysis

Use this skill to establish what the current project actually contains or does.
Apply `fact-only` and `agent-rule`, and work read-only unless the Human has
explicitly authorized a separate mutation task.

## Scope

Analyze only internal evidence relevant to the active Intake:

- source code and repository structure;
- database schemas and read-only query results;
- datasets and data quality;
- aggregate usage analytics, telemetry, and service metrics;
- configuration and environment behavior without exposing secrets;
- logs, traces, and runtime output;
- tests, fixtures, coverage, and verification output;
- existing specifications and other project documents.

Use `web-search` instead when the evidence comes from external web sources. Use
`specification` when accepted findings require a specification update. Route
direct observation, contextual inquiry, workflow shadowing, usability sessions,
and interpretation of consented participant research sessions to
`user-research`. Aggregate analytics, telemetry, logs, and runtime measurements
remain internal analysis when they do not require observing or interviewing a
person.

## Workflow

1. State the question and exact internal boundary being analyzed.
2. Inspect the smallest relevant files, commands, schemas, queries, logs, or
   runtime surfaces.
3. Keep commands and database queries read-only by default.
4. Record exact source paths, commands, query descriptions, and observed
   results without copying secrets or unnecessary sensitive content.
5. Separate observed facts from interpretations, recommendations, conflicts,
   limitations, and unresolved items.
6. Add each structured result to `evidence-and-findings` through the sibling
   Intake manager's `section-item-put` command, normally with kind
   `internal-evidence`.
   This kind satisfies the Intake profile's `evidence` family without a
   duplicate generic `evidence` item.
7. Run the sibling Intake manager's `validate` command immediately after the
   update.
8. Feed accepted findings into their owning requirement, decision, or Work
   Unit basis section and repeat analysis when semantic review finds missing
   internal evidence.

## Evidence Rules

- Use actual repository, database, data, test, log, or runtime output.
- Do not infer runtime behavior from source code when it can be checked safely.
- Do not treat a schema-valid result as proof that data meaning is correct.
- Do not run write queries, migrations, restarts, destructive commands, or
  external messages as analysis.
- Do not expose credentials, tokens, private message bodies, personal data, or
  unrelated proprietary content in command output or Intake findings.
- Record a limitation when evidence is inaccessible, stale, partial, or
  inconsistent.

## Canonical Record Shape

Each `internal-evidence` content item records in its `content` object:

- `kind`: `code`, `database`, `data`, `configuration`, `log`, `test`,
  `runtime`, `document`, or `other`;
- `source`: the inspected path, command, query description, or runtime surface;
- `method`: inspection, command, query, runtime observation, document review, or
  another explicit method when useful;
- `findings`: one or more observed evidence-backed facts;
- `interpretations`: interpretations kept separate from observed findings;
- `limitations`: inaccessible, stale, partial, or conflicting evidence limits.

Do not create a separate Markdown, HTML, or JSON analysis source of truth. Put
non-JSON supporting material under the active Intake package's `blocks/`
directory through the manager's `block-put` command when needed.

Apply the item with:

```text
python3 <agent-factory-skills-root>/intake/scripts/intake.py section-item-put \
  <package> evidence-and-findings --value-file <item.json>
python3 <agent-factory-skills-root>/intake/scripts/intake.py validate <package>
```

Resolve the sibling manager from the installed Plugin skills root as
`<agent-factory-skills-root>/intake/scripts/intake.py`. Do not resolve it
relative to the shell working directory or the `analysis` skill directory.

## Output

Report the Intake id, inspected internal sources, validation result,
limitations, conflicts, and whether more analysis, Human interview, web search,
user research, or specification alignment remains necessary.
