# 검색 노트

보고서: [report-ko.md](report-ko.md) · 서지: [source-catalog.md](source-catalog.md)

## 조사 경계와 방법

- 기간: 기원적 연구부터 2026-08-28까지. 접근일은 모두 2026-08-28.
- 언어: 영어 중심 원출처 검색, 한국어 용어/공식 번역 페이지도 확인. 한국어 2차 글은 원출처보다 우선하지 않았다.
- 우선순위: 공식 문서·정부/보안 표준 → 원 논문·학회/benchmark → 유지형 repository → 종합/교육 자료.
- 포함: 정의·역사·핵심 기법·장문맥·RAG·상태/메모리·도구·평가/운영·보안·도메인 패턴·논쟁.
- 제외/축소: SEO형 “prompt 목록”, 출처 없는 vendor 비교, 단순 뉴스, 중복 미러, 유료 course 홍보, 성능 근거 없는 framework 마케팅.

## 사용한 query family

실제 검색은 여러 변형과 citation chasing을 포함했다. 대표식:

1. `prompt engineering history definition few-shot chain of thought survey`
2. `context engineering definition LLM context window memory state tools`
3. `site:platform.openai.com/docs prompting structured outputs function calling evals prompt caching`
4. `site:docs.anthropic.com prompt engineering XML multishot long context prompt caching context editing`
5. `site:ai.google.dev prompt design long context context caching multimodal`
6. `site:learn.microsoft.com prompt engineering RAG token budget evaluation prompt flow`
7. `site:docs.aws.amazon.com Bedrock prompt optimization guardrails prompt injection`
8. `site:llama.com/docs prompt format tool calling Llama Guard Prompt Guard`
9. `site:arxiv.org chain of thought self consistency generated knowledge least to most ReAct Reflexion`
10. `site:arxiv.org lost in the middle long context automatic prompt optimization DSPy TextGrad OPRO`
11. `site:aclanthology.org retrieval augmented generation evaluation benchmark RAGAs BERGEN`
12. `site:owasp.org LLM prompt injection indirect injection RAG poisoning tool misuse`
13. `site:nist.gov generative AI profile indirect prompt injection`
14. 한국어 변형: `프롬프트 엔지니어링 정의 기법`, `컨텍스트 엔지니어링 RAG 메모리 평가`, `프롬프트 인젝션 간접 주입 보안`.
15. 반증/한계 검색: `chain of thought not always improve`, `long context degradation`, `LLM judge bias`, `automatic prompt optimization transfer limitations`, `RAG does not prevent prompt injection`.

## citation chasing

Prompt Report/공급자 overview에서 기법명을 얻은 뒤 CoT, self-consistency, least-to-most, ReAct, RAG, APE, OPRO, DSPy, TextGrad의 원 논문으로 이동했다. 보안은 OWASP LLM01과 cheat sheet에서 NIST/MITRE 및 간접 주입/RAG 공격면으로 확장했다. RAG 평가는 RAGAs에서 BERGEN, MIRAGE, MEMERAG, 2026년 MTRAGEval/T2/LIT-RAGBench로 확장했다.

## 커버리지와 중복 제거

- 최종 카탈로그: **69개** 항목.
- 1차 연구/benchmark 24, 공식 공급자 문서 25, 표준·보안 5, 오픈소스/도구 11, 2차/학습 4. (일부 항목은 둘 이상 성격이나 한 범주에만 배치.)
- 공급자: OpenAI, Anthropic, Google, Microsoft, AWS, Meta를 최소 1개 이상 포함.
- DOI/arXiv/ACL Anthology 안정 식별자를 가능한 연구 항목마다 기록.
- 같은 문서의 언어별 URL, PDF/HTML 복제, 검색결과 미러는 하나로 통합.

## 확인된 모순과 해석 규칙

1. **지시 위치**: 전통적 OpenAI 가이드는 지시를 앞에 두라고 하고, Gemini/Anthropic 긴 문맥 팁은 긴 자료 뒤에 질의를 두는 것을 권한다. 모순이라기보다 “상위 정책/작업 정의”와 “현재 질문”의 역할 차이로 해석했다. 시작의 불변 지시 + 문맥 뒤의 최종 질문/출력 계약을 후보로 삼되 eval이 필요하다.
2. **더 많은 문맥**: vendor는 높은 needle-retrieval 결과를 강조하지만 Lost in the Middle 및 RAG 실무 문서는 불필요 토큰과 위치 효과를 경고한다. 최대 창과 유효 과업 성능을 구분했다.
3. **CoT**: 초기 논문은 특정 모델/과제에서 향상을 보이지만 최신 reasoning model 가이드는 과도한 단계 강제를 경고할 수 있다. 보편 법칙 대신 모델/과제별 실험으로 결론냈다.
4. **자동 평가**: RAGAs 등은 확장성을 제공하지만 LLM judge는 편향이 있다. 사람 anchor와 component metric을 함께 쓰도록 정리했다.
5. **RAG와 안전**: grounding이 환각을 줄일 수 있다는 기대와, RAG가 injection을 막지 않고 새로운 ingestion/retrieval 공격면을 만든다는 OWASP/NIST 지침을 병기했다.

## 접근 불가·제약

- 일부 공급자 문서는 JavaScript 렌더링, 지역/버전별 redirect, 검색 색인 지연 때문에 갱신일을 명확히 확인하기 어려웠다. `n.d.`로 표시하고 canonical URL을 사용했다.
- 유료/폐쇄형 analyst 보고서와 course는 검증 가능성이 낮아 제외했다.
- Meta 공식 문서의 검색 가시성이 다른 공급자보다 낮아 모델별 세부 prompt template을 충분히 대조하지 못했다. 실제 적용 시 해당 모델 카드와 tokenizer/chat template을 다시 확인해야 한다.
- 2026년 논문 중 arXiv-only 항목은 동료평가 여부가 확정되지 않을 수 있다. 최근성보다 증거 수준을 낮게 표시했다.
- 검색 API의 반환 순위·색인 범위는 전체 웹을 대표하지 않는다. 따라서 문자 그대로의 “폭넓은 검색 결과 전부”를 주장하지 않는다.
- 본 Inquiry는 문헌 종합이며 모델 호출 실험은 하지 않았다. 공급자별 최신 모델을 같은 데이터로 직접 비교한 결론은 없다.

## 남은 근거 공백

- context engineering의 합의된 정의·taxonomy·독립 benchmark.
- 한국어에서 장문맥 위치, 높임말/형태소, 다국어 RAG의 공급자 간 직접 비교.
- 최신 reasoning model에서 CoT/critique/agent loop의 비용 대비 효과.
- 실제 enterprise corpus를 대상으로 한 retrieval poisoning 방어의 독립 평가.
- compaction/요약이 장기 작업의 결정·숫자·부정·출처를 얼마나 보존하는지에 대한 표준 평가.
- multi-agent context isolation, 권한 위임, provenance의 공개 benchmark.

## 가장 작은 유용한 후속 Inquiry

한국어 50–100개 고정 세트(추출, 다단계 QA, 긴 문서 needle, 모호/정보부족, RAG, 간접 주입)를 만들고, 3개 공급자의 pinned model에서 다음 네 축만 factorial 비교한다: (a) 짧은 문맥/전체 장문맥/RAG, (b) 관련 정보의 앞·중간·끝 위치, (c) 청크 수와 reranking, (d) 자연어 형식 지시 대 strict schema. 정확성·근거성·기권·공격 성공률·p95 지연·비용을 기록하면 본 문헌 종합의 가장 큰 실증 공백을 좁힐 수 있다.
