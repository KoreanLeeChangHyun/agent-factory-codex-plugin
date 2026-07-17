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
- The request is broad enough that the change level is unclear.
- The artifact purpose, audience, approval criteria, lifecycle stage, or output
  boundary is unclear.
- The work would add a new principle or change the meaning of an existing
  lifecycle rule.
- External research produced alternatives and the selection is not already
  explicit.
- The action would cross a Human approval boundary or make a decision that the
  Human must be able to reject.

Do not ask for an interview when all items are true:

- The next action only applies a recorded decision.
- The path, file, artifact, or command is explicit enough to execute.
- The work is factual investigation: reading code, searching files, checking
  current state, or web research that does not choose a policy.
- The work only records or formats already-decided facts.
- The change does not alter lifecycle rules, approval criteria, scope, or Human
  review boundaries.

When unsure, ask one concise question. When the gate passes with no Human
decision needed, state that no additional interview is needed and proceed.

## Source Basis

Web research was performed from multiple angles on 2026-06-05:

- Requirements and stakeholder elicitation.
- Human oversight and human-AI role boundaries.
- Decision ownership and approval roles.
- Spec-driven clarification before implementation.

This historical source table uses numeric authority and freshness scores.
New external source records use the authority-first tiers and freshness labels
from `web-search`.

| Source | Authority | Freshness | Used For |
| --- | ---: | ---: | --- |
| NIST AI Risk Management Framework | 5 | 5 | Human-AI role and oversight boundaries. |
| NIST AI RMF Appendix C | 5 | 3 | Need to define and differentiate Human roles and responsibilities. |
| IIBA BABOK Elicitation and Collaboration | 5 | 4 | Elicitation, collaboration, confirmation, approval, and interview techniques as business analysis practices. |
| US EPA Stakeholder Interviews guide | 5 | 5 | Interviews obtain project-relevant information and reveal hidden concerns or ideas. |
| Atlassian DACI Decision-Making Framework | 4 | 4 | Complex or high-stakes decisions require clear roles, one approver, and contributors. |
| GitHub Spec Kit documentation | 5 | 5 | Specification-first workflow and structured phases before implementation. |
| GitHub Spec Kit repository | 5 | 5 | Clarify and ask questions around specifications; do not treat first attempts as final. |
| Microsoft Learn Responsible AI guidance | 4 | 5 | Human review and feedback loops for AI systems, role accountability, and governance. |

## Source URLs

- https://www.nist.gov/itl/ai-risk-management-framework
- https://airc.nist.gov/airmf-resources/airmf/appendices/app-c-ai-risk-management-and-human-ai-interaction/
- https://www.iiba.org/knowledgehub/business-analysis-body-of-knowledge-babok-guide/4-elicitation-and-collaboration/
- https://www.epa.gov/international-cooperation/public-participation-guide-stakeholder-interviews
- https://www.atlassian.com/team-playbook/plays/daci
- https://github.github.com/spec-kit/
- https://github.com/github/spec-kit
- https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/responsible-ai
