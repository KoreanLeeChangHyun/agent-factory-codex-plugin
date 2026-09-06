# Information lifecycle: two stages versus three stages

## Human question

공개 웹 자료를 조사하여 다음 두 정보 수명주기 모델을 비교한다.

- 2단계: `원본 -> 정제`
- 3단계: `원본 -> 가공 -> 정제`

Agent Factory에서 원본문서, 탐색·분석·인터뷰 결과, 그리고 정제된
Specification/Project Skill을 관리할 때 어느 모델이 더 적합한지 판단할 수
있는 근거를 제공한다.

## Research boundary

This is an Inquiry, not an implementation or Specification update. Search the
public web and prioritize primary or authoritative sources. Do not change
product code, Skills, plugin metadata, the core Specification, Project Skills,
or canonical project decisions.

Use current repository contracts only as local comparison evidence:

- `AGENTS.md`
- `skills/gather/SKILL.md` and gather management reference
- `skills/inquery/SKILL.md` and workspace reference
- `skills/interview/SKILL.md` and conduct reference
- `skills/specification/SKILL.md` and its Specification/Project Skill references
- `.codex/skills/agent-factory-core/`

## Web research questions

1. Find established two-stage or direct source-to-curated/published models and
   explain when they work well.
2. Find established three-or-more-stage models that distinguish raw/source,
   transformed/working/intermediate, and curated/authoritative/published
   information. Relevant domains may include records management, digital
   curation, data engineering, data provenance, scientific workflows, content
   publishing, and knowledge management.
3. Use authoritative sources where possible, such as standards bodies,
   government archives, recognized research institutions, or official
   platform architecture documentation. Distinguish standards/evidence from
   vendor patterns and explanatory analogies.
4. Compare the models on:
   - provenance and auditability;
   - preservation of Human statements versus AI interpretation;
   - reproducibility and reprocessing;
   - contradiction and uncertainty handling;
   - storage and lifecycle complexity;
   - privacy, retention, and deletion;
   - promotion/approval semantics;
   - suitability for small/simple projects versus research-heavy projects;
   - risks of treating processed AI material as accepted truth.
5. Determine whether “processed” should be a distinct information authority
   state, merely an operational workspace, or both. Avoid assuming that every
   intermediate file must be retained.
6. Apply the evidence to Agent Factory's current concepts: Gather, Explorer,
   Interview, Inquery workspace, Specification, and paired Human/AI refined
   representations.
7. Recommend a default model plus explicit conditions under which a two-stage
   shortcut is safe. Keep the final architecture decision Human-owned.

## Expected output

Write a detailed Korean Markdown report to:

`.agent-factory/inquery/information-lifecycle-2-vs-3-stage-20260828/report.md`

Include:

- concise conclusion;
- terminology normalization;
- source-backed comparison table;
- examples of both models;
- Agent Factory mapping;
- recommended default and safe shortcut criteria;
- retention/provenance implications;
- contradictions, evidence limitations, and unresolved Human decision;
- direct source links and access date;
- smallest useful follow-up Inquiry, if any.

Do not run tests or verification commands.
