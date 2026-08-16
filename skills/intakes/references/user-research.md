# Agent Factory User Research

Collect direct evidence about what people do, need, and encounter in context.
Apply `rules`. Do not treat a participant statement as an
observed behavior or generalize beyond the sampled people and situations.

## Boundary

- Use `references/interview.md` for Human-only project and lifecycle decisions.
- Use `references/analysis.md` for repository, database, analytics, log, test,
  runtime, and document evidence that does not require observing a person.
- Use `references/web-search.md` for public or external published evidence.
- Use a Work Unit for prototype construction or other scoped mutations only
  when the Human separately selects that advanced route. Recruitment and
  external contact always require explicit authorization.
- Record a research need as an open item when access, consent, participants, or
  an appropriate observation surface is unavailable. Do not fabricate a study.

## Workflow

1. State the research question, target user or operator group, observation
   context, and the decision or requirement the evidence may inform.
2. Confirm authorization, consent, privacy boundaries, recording rules, and
   allowed artifacts before observing people or consuming session material.
3. Select the least costly method that can answer the question: direct
   observation, contextual inquiry, workflow shadowing, usability session,
   journey reconstruction, or review of consented recordings and screenshots.
4. Record what was directly observed separately from participant statements,
   interpretations, inferred needs, recommendations, and limitations.
5. Note sampling limits, accessibility context, environment, task conditions,
   researcher influence, missing user groups, and contradictory evidence.
6. Append each structured result through the sibling Intake manager's
   `entry-put` command with activity `user-research`.
7. Rely on manager-internal mutation validation. Run separate `validate` only
   when the Human explicitly requests verification.
8. Keep later decisions, optional Specifications, and Work Units traceable to
   the exact research entry ids. Route Human-only choices to `references/interview.md`.

## Evidence Contract

Each `user-research` entry's `content` object records:

- `researchQuestion`: the question investigated;
- `participantGroup`: a non-identifying description of the sampled group;
- `method`: the observation or research method;
- `context`: relevant environment, task, channel, and accessibility context;
- `observations`: directly observed behaviors or events;
- `participantStatements`: attributed but non-identifying statements when
  relevant;
- `interpretations`: interpretations kept separate from observations;
- `limitations`: sampling, consent, access, privacy, or method limitations.

Do not store names, contact details, credentials, raw personal data, private
message bodies, or unnecessary recordings in Intake JSON. Register authorized
non-JSON supporting material under `blocks/` through `block-put`, using a
redacted or minimized artifact whenever possible.

Apply an item with:

```text
python3 <agent-factory-skills-root>/intakes/scripts/intake.py entry-put \
  <package> <typed-data-arguments>
```

The manager constructs JSON from the typed data arguments. Do not create a
JSON value file.

Resolve the sibling manager from the installed Plugin skills root as
`<agent-factory-skills-root>/intakes/scripts/intake.py`. Do not resolve it
relative to the shell working directory or the `intakes` skill directory.

## Output

Report the Intake id, research question, sampled group and context, methods,
observations, limitations, manager mutation result, and whether more user research,
internal analysis, web search, Human interview, or specification alignment is
required.
