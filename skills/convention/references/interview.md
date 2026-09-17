# Interview

<a id="scope"></a>

## 1. Scope

- Main conducts adaptive elicitation in the current Human conversation only when
  available context cannot resolve a material knowledge/requirement/decision gap.
- Convention owns the contract; Interview is no public Skill or managed Exec role.
- Output is Processed by default, never independently accepted Specification truth.
- Do not replace ordinary answers, survey external people or dispatch Human
  impersonation.

<a id="authority-and-evidence"></a>

## 2. Authority and evidence

- Separate direct statements/decisions from Explorer evidence, paraphrases,
  interpretations, assumptions, contradictions and unresolved gaps.
- Silence, ambiguity or lack of objection grants no approval.
- Human may skip, defer, correct, narrow or stop.
- Never solicit passwords/tokens/private keys or other secrets; other sensitive
  information requires necessity and authorization.
- Keep results in conversation unless a Human-selected target or authorized workflow
  requires an artifact.

<a id="question-protocol"></a>

## 3. Question protocol

1. Before asking the first question, inspect the available context and enumerate the
   complete set of material Human decisions the interview must resolve.
2. Fix the total question count from that inventory; do not choose a total from only the
   next known question.
3. If later Human input adds, removes or combines a material decision, revise the total
   explicitly and preserve the reason in the interview record.

- Ask one decision at a time using this structure. Render each JSON string below as a
  template line, joined by newlines. Localize labels, questions, options and
  recommendations under the [communication contract](communication.md#language). English template labels do not set the response
  language.

```json
[
  "Question: [<current>/<total>] <question>",
  "",
  "| Option | Decision | Advantages | Disadvantages |",
  "|---|---|---|---|",
  "| 1 | <decision> | <advantage> | <disadvantage> |",
  "| 2 | <decision> | <advantage> | <disadvantage> |",
  "| 3 | <decision> | <advantage> | <disadvantage> |",
  "",
  "Recommendation: <recommendation>",
  "",
  "Previous decision:",
  "",
  "- <prior Human decision>"
]
```

- Provide three mutually exclusive, decision-ready options grounded in available
  evidence. The recommendation is advice, never a decision or approval.
- Keep `Previous decision` as a bullet list containing only the immediately preceding answered
  interview decision.
  - Use the localized equivalent of `- None` before the first decision.
  - Do not list process requirements, recommendations, silence or unresolved options as
    decisions.
  - Reserve the complete decision history for interview completion.
- When the Human supplies a requirement without answering the active question, record
  that requirement and continue the unanswered question. Recalculate the total only when
  the decision inventory changed.

<a id="completion-and-record"></a>

## 4. Completion and record

- After all questions are answered:

1. Output a complete interview summary in the Human conversation, covering every
   question, option, recommendation, Human decision, correction and unresolved gap.
2. Record the complete interview process as a Processed Document. Include the original
   decision inventory, any total-count revisions and their reasons, all questions and
   options, recommendations distinguished from Human decisions, the complete decision
   history and the final summary.
3. Use the Human-selected destination when supplied; otherwise follow [Document routing](../../document/SKILL.md#routing).

- The record is non-authoritative working knowledge.
- It does not become an accepted Specification merely because the interview completed or
  the document was written.

<a id="coordination"></a>

## 5. Coordination

1. Main may pause Interview while Work gathers external background through Explorer.
2. Main integrates that evidence and resumes Human conversation.

- Work never interviews or impersonates the Human on Explorer's behalf.
