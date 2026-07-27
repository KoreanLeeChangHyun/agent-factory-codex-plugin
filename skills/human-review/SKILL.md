---
name: human-review
description: Use when creating or updating Human-facing Agent Factory lifecycle artifacts, Human checklists, final review material, approval prompts, rework prompts, merge or promotion review material, or other outputs the Human must read or decide on. Write them in the Human language; for this project, use Korean.
---

# Human Review Language

## Rules

- Write Human-facing review artifacts in the Human's language.
- For this project, use Korean for Human-facing review artifacts because the
  user explicitly stated the current Human is Korean.
- Apply this to Human checklists, Human Review instructions, approval or
  rework prompts, merge or promotion review material, user-facing review
  summaries, and report text meant for Human decision-making.
- Keep AI checklist material separate from Human checklist material.
- Make Human review material sufficient for approval, rework, rejection, merge,
  or PR promotion decisions.
- Keep machine-facing material unchanged when translation would reduce
  precision or break usage.

## Approval-Only Prompts

- Use an approval-only prompt only when the Human must approve or reject a
  specific result or action. Present exactly two choices: `YES` and `NO`.
- Keep this approval prompt separate from the three-choice `A`/`B`/`C`
  interview flow. Use `interview` when the Human must choose among project or
  lifecycle alternatives.
- Determine approval intent from the current approval request and the Human's
  full response, not a fixed string allowlist.
- Treat `YES`, `Y`, `승인`, `네`, `진행`, and `ㄱㄱ` as non-exhaustive examples
  of wording that can express clear approval in context. Other wording may
  also mean `YES` when the response unambiguously approves the current request.
- Treat a clear rejection or rework request as `NO`. A negated, deferred,
  conditional, partial, or ambiguous response is not approval.
- When approval intent is not clear, do not perform the approval-gated action;
  ask the Human again for an explicit `YES` or `NO`.

## Do Not Translate

Do not translate these unless the user explicitly asks:

- Code.
- Commands.
- File paths.
- Branch names.
- Identifiers.
- API names.
- Package names.
- Log output that must remain exact.
- Quoted source text that must remain exact.

## When Language Is Unspecified

If the Human language is not explicit in the current project rules, user
messages, or relevant artifact source, ask before writing Human-facing review
artifacts.

## Mixed Artifacts

For artifacts that contain both Human-facing and machine-facing sections:

- Write Human-facing prose in the Human's language.
- Keep machine-facing literals exact.
- Add a short Human-language explanation around exact literals when needed for
  review.
