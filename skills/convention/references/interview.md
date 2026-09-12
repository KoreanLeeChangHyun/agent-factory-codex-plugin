# Interview

## Scope

- Main conducts adaptive elicitation in the current Human conversation only when
  available context cannot resolve a material knowledge/requirement/decision gap.
- Convention owns the contract; Interview is no public Skill or managed Exec role.
- Output is Processed by default, never independently accepted Specification truth.
- Do not replace ordinary answers, survey external people or dispatch Human impersonation.

## Authority and evidence

- Separate direct statements/decisions from Explorer evidence, paraphrases,
  interpretations, assumptions, contradictions and unresolved gaps.
- Silence, ambiguity or lack of objection grants no approval.
- Human may skip, defer, correct, narrow or stop.
- Never solicit passwords/tokens/private keys or other secrets; other sensitive
  information requires necessity and authorization.
- Keep results in conversation unless a Human-selected target or authorized workflow
  requires an artifact.

## Question protocol

Before asking the first question, inspect the available context and enumerate the
complete set of material Human decisions the interview must resolve. Fix the total
question count from that inventory; do not choose a total from only the next known
question. If later Human input adds, removes or combines a material decision, revise
the total explicitly and preserve the reason in the interview record.

Ask one decision at a time using this exact structure:

```markdown
질문: [<current>/<total>] <question>

| 선택지 | 결정 | 장점 | 단점 |
|---|---|---|---|
| 1 | <decision> | <advantage> | <disadvantage> |
| 2 | <decision> | <advantage> | <disadvantage> |
| 3 | <decision> | <advantage> | <disadvantage> |

추천: <recommendation>

이전 결정 사항:

- <prior Human decision>
```

- Provide three mutually exclusive, decision-ready options grounded in available
  evidence. The recommendation is advice, never a decision or approval.
- Keep `이전 결정 사항` as a bullet list containing only the immediately
  preceding answered interview decision. Use `- 없음` before the first decision.
  Do not list process requirements, recommendations, silence or unresolved options
  as decisions. Reserve the complete decision history for interview completion.
- When the Human supplies a requirement without answering the active question,
  record that requirement and continue the unanswered question. Recalculate the
  total only when the decision inventory changed.

## Completion and record

After all questions are answered:

1. Output a complete interview summary in the Human conversation, covering every
   question, option, recommendation, Human decision, correction and unresolved gap.
2. Record the complete interview process as a Processed Document. Include the
   original decision inventory, any total-count revisions and their reasons, all
   questions and options, recommendations distinguished from Human decisions, the
   complete decision history and the final summary.
3. Use the Human-selected destination when supplied; otherwise follow
   [Document routing](documents.md#routing).

The record is non-authoritative working knowledge. It does not become an accepted
Specification merely because the interview completed or the document was written.

## Coordination

1. Main may pause Interview while Work gathers external background through Explorer.
2. Main integrates that evidence and resumes Human conversation.

- Work never interviews or impersonates the Human on Explorer's behalf.
