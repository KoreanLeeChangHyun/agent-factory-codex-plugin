# Explicit Human Input Convention

## Explicitness boundary

Treat a requirement, choice, scope boundary, authority grant, or acceptance
criterion as explicit only when the Human actually states it or an already
accepted Specification resolves it unambiguously.

When a required part is not explicit, do not infer, invent, silently default,
or present an assumption as a decision. Ask the Human and wait for the answer
before proceeding through the affected decision. Silence, ambiguity,
convention, precedent, likely preference, and lack of objection do not count as
an explicit Human decision.

## Evidence and role behavior

Repository inspection and evidence gathering may establish observable facts,
but they cannot manufacture a missing Human decision. Keep discovered facts
distinct from Human-owned choices.

Apply this rule across Main, Work, Verification, Explorer, and Interview:

- Main asks the Human for the missing required decision and waits for the
  answer.
- Work and Verification report the unresolved question to Main and do not ask
  the Human directly or proceed through the affected decision.
- Explorer may gather evidence about observable facts, but does not convert
  evidence into a Human-owned choice and never interviews or impersonates the
  Human.
- Interview is conducted only by Main and preserves the distinction between a
  direct Human statement, evidence, interpretation, and an unresolved gap.

This rule creates no Agent role, public Skill, or capability. It does not
weaken existing safety, authority, Specification-pair, or managed graph
contracts.

## Provenance

This cross-cutting rule comes from the Human's delegated request at
`.agent-factory/agent/explicit-human-input-work-20260831/runs/run-20260830T174409464808Z-330b0066/request.md`.
