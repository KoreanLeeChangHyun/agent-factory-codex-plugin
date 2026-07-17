---
name: interview
description: Use when interviewing the Human decision owner to resolve Agent Factory lifecycle decisions about design, architecture, migration, planning, product behavior, implementation, approval boundaries, Human review, rework, merge, or PR promotion. Use only for decision interviews, not user-research interviews, observation, contextual inquiry, or usability sessions. Ask exactly one decision question at a time with three choices, pros and cons, and a recommendation.
---

# Interview Guide

Use this skill when work needs a human decision before proceeding and the
decision should be made through a structured interview flow.

This skill interviews a Human decision owner to obtain an explicit project or
lifecycle decision. Route questions asked to research participants, direct
observation, contextual inquiry, workflow shadowing, usability sessions, and
participant-session interpretation to `user-research`. Do not store research
participant evidence as kind `interview` or force a research session into the
three-choice decision format.

## Core Rules

- Apply the Interview Decision Gate from the bundled `fact-only` skill's
  `references/interview-decision-gate.md` before using this skill. Resolve it
  under `../fact-only/` relative to this skill according to
  `lifecycle`.
- Use this skill only when a human decision is actually needed before
  proceeding.
- Use this skill for Human-only decisions such as scope, priority,
  requirements, approval boundaries, risk tolerance, Work Unit approval, rework,
  merge, deployment, operation, maintenance, or PR promotion.
- Treat a recorded decision as active unless the user explicitly changes it or
  a later recorded decision supersedes it.
- Do not re-ask settled decisions or rehash settled options.
- Ask again only when recorded decisions conflict, no recorded decision covers
  the current issue, the current request is not explicit, or the next action is
  ambiguous.
- If no human decision or interview is needed, state that no additional
  interview is needed only after applying the gate, then proceed with the next
  executable work.
- Ask exactly one question per assistant message.
- Always show progress at the top. Include:
  - the current project/task/phase progress when known
  - interview progress as `answered/total`
- Every question must have exactly three choices: `A`, `B`, and `C`.
- Present the choices in one Markdown table with these columns:
  `Choice`, `Decision`, `Pros`, `Cons`.
- Include one recommended choice after the table.
- Explain the recommendation with concrete rationale tied to the user's stated
  goal, long-term maintainability, risk, reversibility, and implementation
  cost.
- If the user asks for a fundamental long-term solution, prefer choices that
  remove legacy compatibility layers, duplicated ownership, or temporary
  workarounds instead of extending them.
- If the user answers with a letter, record that answer, increment the
  interview progress, and ask the next question.
- Do not ask multiple follow-up questions in the same message.

## Storage

- Record each question, three choices, selected option, recommendation,
  rationale, answer, and decision state in `evidence-and-findings` through the
  sibling Intake manager's `section-item-put` command with kind `interview`.
- Record the accepted decision as a separate traceable item in
  `decisions-and-open-items` through `section-item-put` with kind `decision-status`.
  Record the current blocking and non-blocking summary as
  kind `open-items-status`; use `open-item` only for an individual unresolved
  item with explicit blocking and resolved attributes.
- An `interview` item satisfies the Intake profile's `evidence` family without
  a duplicate generic `evidence` item.
- Do not create a separate Markdown or JSON interview source of truth.
- Keep each recorded decision traceable to its related requirement,
  specification-impact, or Work Unit basis item.
- Run the Intake manager's separate `validate` command after the update.

Resolve the sibling manager from the installed Plugin skills root as
`<agent-factory-skills-root>/intake/scripts/intake.py`. Do not resolve it
relative to the shell working directory or the `interview` skill directory.

## Response Shape

Use this shape:

```markdown
Progress: <project/task/phase progress if known>, interview <answered>/<total>

Question <n>/<total>: <single decision question>

| Choice | Decision | Pros | Cons |
| --- | --- | --- | --- |
| A | ... | ... | ... |
| B | ... | ... | ... |
| C | ... | ... | ... |

Recommendation: <A/B/C>

Rationale: <explicit reason grounded in the goal and tradeoffs>
```

When responding in Korean, translate the labels naturally:

- `Progress` -> `진척률`
- `Question` -> `질문`
- `Choice` -> `선택지`
- `Decision` -> `결정`
- `Pros` -> `장점`
- `Cons` -> `단점`
- `Recommendation` -> `추천`
- `Rationale` -> `근거`

## Answer Handling

When the user answers:

1. Interpret a bare `A`, `B`, or `C` as the selected choice for the current
   question.
2. Restate the recorded decision in one sentence.
3. Increment interview progress.
4. Ask the next single question using the required table.

If the user gives a natural-language answer, map it to the closest choice when
the intent is clear. State the mapping briefly. If the intent is ambiguous, ask
one clarification question with three choices.

## Stop Rule

When all questions are answered:

- Show final interview progress as `total/total`.
- Summarize the selected decisions.
- State what can proceed next.
- Do not continue into implementation unless the user explicitly asks to proceed
  or the current task already requires implementation.
