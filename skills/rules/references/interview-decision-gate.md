# Interview Decision Gate

Use this gate before asking the Human a question and before saying no interview
is needed.

## Gate

Ask for a Human interview or decision when any item is true:

- A Human-only decision is required: goal, priority, acceptance criteria,
  business rule, preference, approval, risk tolerance, scope tradeoff, or PR
  promotion decision.
- Recorded decisions conflict, or a newer request may supersede an earlier
  decision.
- The request leaves multiple materially different Human-visible outcomes and
  repository evidence does not select one.
- The artifact purpose, audience, approval criteria, lifecycle stage, or output
  boundary is unclear.
- The work would add a new principle or change the meaning of an existing
  lifecycle rule.
- External research produced alternatives and the selection is not explicit.
- The action would cross a Human approval boundary or make a decision that the
  Human must be able to reject.

Do not ask for an interview when all items are true:

- The next action only applies a recorded decision.
- The bounded outcome is explicit enough to execute; ordinary file and
  implementation selection may come from repository evidence.
- The work is factual investigation or only records already-decided facts.
- The change does not require a new Human-owned product, risk, scope, or
  irreversible decision.

When a material Human decision is missing, ask one concise question. Otherwise
proceed without announcing an interview gate.

## Source Basis

This gate preserves the existing Agent Factory decision boundary. Its
historical evidence basis is NIST AI RMF guidance, requirements elicitation
sources, decision ownership guidance, and specification-first workflow
sources.
