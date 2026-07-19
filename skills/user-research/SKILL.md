---
name: user-research
description: Use for Agent Factory Intake when direct evidence about users, operators, or other affected people requires observation, contextual inquiry, usability sessions, workflow shadowing, journey reconstruction, or review of consented research recordings. Records observed behavior and context in the active canonical Intake without replacing Human decision interviews, internal system analysis, or external web research.
---

# Agent Factory User Research

Collect direct evidence about what people do, need, and encounter in context.
Apply `fact-only` and `agent-rule`. Do not treat a participant statement as an
observed behavior or generalize beyond the sampled people and situations.

## Boundary

- Use `interview` for Human-only project and lifecycle decisions.
- Use `analysis` for repository, database, analytics, log, test, runtime, and
  document evidence that does not require observing a person.
- Use `web-search` for public or external published evidence.
- Use a Work Unit during Execution for prototype construction, experiment
  implementation, recruitment, external contact, or other scoped mutations.
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
6. Add each structured result to `evidence-and-findings` through the sibling
   Intake manager's `section-item-put` command with kind `user-evidence`.
   This kind satisfies the Intake profile's `evidence` family without a
   duplicate generic `evidence` item.
7. Run the Intake manager's separate `validate` command immediately.
8. Feed accepted evidence into its owning requirement, constraint, decision,
   success criterion, or Work Unit basis item. Route Human-only choices to
   `interview`.

## Evidence Contract

Each `user-evidence` item's `content` object records:

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

Apply an item and validate with:

```text
python3 <agent-factory-skills-root>/intake/scripts/intake.py section-item-put \
  <package> evidence-and-findings <typed-data-arguments>
python3 <agent-factory-skills-root>/intake/scripts/intake.py validate <package>
```

The manager constructs JSON from the typed data arguments. Do not create a
JSON value file.

Resolve the sibling manager from the installed Plugin skills root as
`<agent-factory-skills-root>/intake/scripts/intake.py`. Do not resolve it
relative to the shell working directory or the `user-research` skill directory.

## Output

Report the Intake id, research question, sampled group and context, methods,
observations, limitations, validation result, and whether more user research,
internal analysis, web search, Human interview, or specification alignment is
required.
