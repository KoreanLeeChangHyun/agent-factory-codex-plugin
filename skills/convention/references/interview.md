# Interview

<a id="scope"></a>

## 1. Scope

- Main conducts adaptive elicitation in the current Human conversation only when
  available context cannot resolve a material knowledge/requirement/decision gap.
- Convention owns the contract; Interview is no public Skill or managed Exec role.
- Output is Refined by default, never independently accepted Specification/Skill truth.
- Do not replace ordinary answers, survey external people or dispatch Human
  impersonation.

<a id="authority-and-evidence"></a>

## 2. Authority and evidence

- Separate direct statements/decisions from research evidence, paraphrases,
  interpretations, assumptions, contradictions and unresolved gaps.
- Silence, ambiguity or lack of objection grants no approval.
- Human may skip, defer, correct, narrow or stop.
- Never solicit passwords/tokens/private keys or other secrets; other sensitive
  information requires necessity and authorization.
- Keep results in conversation unless a Human-selected target or authorized workflow
  requires an artifact.

<a id="question-protocol"></a>

## 3. Question protocol

1. Before asking the first question, inspect the available context and identify the
   material Human decisions currently known to block or materially change the outcome.
2. Order those decisions by dependency and impact. Ask the earliest unresolved decision
   first; do not ask for information already available or safely inferable.
3. Treat the displayed total as the current known total, not a promise that no further
   question can emerge. When Human input adds, removes or combines a material decision,
   update the total, state the reason briefly and preserve the revision in any authorized
   interview record.

- Ask one material decision at a time using one rendered structure below. Replace the
  brace-delimited placeholders; do not wrap the response in a code fence. Select the
  structure from the Human's language under the
  [communication contract](communication.md#language), and do not mix label languages
  within one question. Korean and English are explicitly supported; localize the same
  fields for other Human-selected languages. The structure names below are explanatory
  and are not part of the response.

- Prefer a structured question channel over Markdown shape recognition.
  - When Codex exposes `request_user_input` in the active collaboration mode, use it.
    Use an ID ending in `{current}-of-{known total}`. Give each option a label and one
    description in the exact form `Pros: {advantage}; Cons: {disadvantage}`. Append
    `(Recommended)` to the recommended label.
  - Do not assume that a native tool exists merely because another execution mode or
    provider supports it. Installed Claude Code print mode and Antigravity use the
    Agent Factory marker below unless their active tool list actually exposes an
    equivalent question tool.
  - For the marker channel, emit one exact single-line marker before the terminal
    answer. Do not wrap it in a code fence or duplicate the Markdown table:

- Marker:
  `<agent-factory-interview-question>{"id":"interview-1-of-3","current":1,"total":3,"text":"{question}","options":[{"value":"1","label":"{decision}","pros":"{advantage}","cons":"{disadvantage}"},{"value":"2","label":"{decision}","pros":"{advantage}","cons":"{disadvantage}"}],"recommendedValue":"1","yesNo":false}</agent-factory-interview-question>`

  - Keep the terminal answer nonempty and concise after the marker. The adapter removes
    a valid marker and emits `interview.question`; an invalid marker remains visible and
    must not become a clickable question.
  - Use the Markdown structures below only as the compatibility fallback when no
    structured channel can be emitted. They also preserve old conversation replay.

**Korean structure**

**질문 [{current}/{known total}]:** {question}

| 선택지 | 결정 | 장점 | 단점 |
|---|---|---|---|
| 1 | {decision} | {advantage} | {disadvantage} |
| 2 | {decision} | {advantage} | {disadvantage} |
| 3 | {decision} | {advantage} | {disadvantage} |

**권고:** {recommendation}

**이전 결정:**

- {prior Human decision}

**English structure**

**Question [{current}/{known total}]:** {question}

| Option | Decision | Advantages | Disadvantages |
|---|---|---|---|
| 1 | {decision} | {advantage} | {disadvantage} |
| 2 | {decision} | {advantage} | {disadvantage} |
| 3 | {decision} | {advantage} | {disadvantage} |

**Recommendation:** {recommendation}

**Previous decision:**

- {prior Human decision}

- Provide two or three mutually exclusive, decision-ready options grounded in available
  evidence. Use three only when each option represents a meaningful distinct outcome.
  The recommendation is advice, never a decision or approval.
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
2. Create a durable Refined Document only when the Human requests an artifact or the
   authorized workflow requires one. Include the initial decision inventory, any
   total-count revisions and their reasons, all questions and options, recommendations
   distinguished from Human decisions, the complete decision history and the final
   summary.
3. For an authorized artifact, use the Human-selected destination when supplied;
   otherwise follow [Document routing](../../document/SKILL.md#routing).

- Any record is non-authoritative working knowledge.
- It does not become an accepted Specification merely because the interview completed or
  the document was written.

<a id="coordination"></a>

## 5. Coordination

1. Main may pause Interview for background research under the captured execution route; follow
   [research and evidence guidance](../SKILL.md#research).
2. Main integrates that evidence and resumes Human conversation.

- Work never interviews or impersonates the Human during background research.
