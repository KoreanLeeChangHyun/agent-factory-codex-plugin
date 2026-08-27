# 프롬프트 엔지니어링과 컨텍스트 엔지니어링 조사 보고서

> 상태: 2026-08-28 기준의 임시 Inquiry 산출물. ‘완전한 목록’이 아니라 대표성과 추적 가능성을 우선한 종합이다. 각 주장 옆 링크는 원문이며, 전체 서지는 [source-catalog.md](source-catalog.md), 검색 과정과 한계는 [search-notes.md](search-notes.md)를 참조한다.

## 요약

**프롬프트 엔지니어링(prompt engineering)**은 모델 파라미터를 바꾸지 않고, 한 번의 요청 또는 대화에서 모델이 받는 자연어·예시·출력 제약을 설계하고 반복 개선하는 일이다. **컨텍스트 엔지니어링(context engineering)**은 그보다 넓다. 매 추론 시점에 모델이 볼 정보 전체—상위 지침, 사용자 입력, 대화 상태, 검색 문서, 메모리, 도구와 스키마, 예시, 멀티모달 입력—를 선택·조립·격리·압축·전달하고, 비용·지연·안전·평가까지 운영하는 시스템 설계다. 프롬프트는 컨텍스트의 일부이며, 둘은 대체 관계가 아니다.

핵심 결론은 다음과 같다.

1. 좋은 문구보다 **좋은 작업 계약**이 중요하다. 목표, 허용 근거, 실패/기권 조건, 출력 스키마, 도구 권한을 명시하고 대표 데이터셋으로 평가해야 한다.
2. 컨텍스트 창이 커져도 무조건 더 넣는 전략은 실패한다. 긴 입력에서 정보 위치와 잡음의 영향이 크다는 *Lost in the Middle* 결과가 대표적이다([Liu et al., 2023/2024](https://arxiv.org/abs/2307.03172)). 선택·재순위화·중복 제거·질의 근접 배치가 필요하다.
3. RAG는 환각이나 보안을 자동 해결하지 않는다. 검색과 생성의 실패를 분리해 평가하고, 검색 문서는 **신뢰할 수 없는 데이터**로 취급해야 한다. OWASP는 직접·간접 주입, RAG 오염, 도구 조작을 별도 공격면으로 다룬다([Prompt Injection Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html), [RAG Security](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)).
4. 생각 과정을 길게 출력하게 하는 것이 항상 최선은 아니다. 복잡한 문제에는 분해·검증·도구 사용을 요청하되, 숨은 추론 원문을 요구하거나 저장하기보다 **간결한 근거, 계산 결과, 인용, 검증 가능한 중간 산출물**을 요청한다. 최신 추론 모델은 공급자별 지침이 다르므로 공식 가이드를 따른다.
5. 프롬프트/컨텍스트는 코드처럼 버전 관리하되, 품질은 코드 리뷰만으로 보장되지 않는다. 고정 테스트셋, 회귀 평가, 안전 공격셋, 비용·지연·도구 성공률, 온라인 A/B와 사용자 결과를 함께 본다. 모델 스냅샷을 고정하고 교체 때 재평가하라는 OpenAI의 지침이 이를 뒷받침한다([API backward compatibility](https://platform.openai.com/docs/api-reference/backward-compatibility)).

## 개념 지도와 경계

```text
LLM 애플리케이션 품질
├─ 모델/학습: 사전학습, 미세조정, 증류, 디코딩
├─ 프롬프트 엔지니어링
│  ├─ 지시·역할·제약·구분자
│  ├─ zero/one/few-shot 예시
│  ├─ 분해·체이닝·비평·출력 스키마
│  └─ 모델별 템플릿과 자동 최적화
└─ 컨텍스트 엔지니어링
   ├─ 지침 계층과 신뢰 경계
   ├─ 대화 상태·메모리·JIT 검색(RAG)
   ├─ 도구·함수·스키마·멀티모달 입력
   ├─ 선택·정렬·압축·캐시·토큰 예산
   └─ 평가·관측·보안·권한·거버넌스
```

Google은 prompt engineering을 모델 파라미터를 바꾸지 않고 지시와 예시로 기존 패턴 인식 능력을 활용하는 것으로 설명한다([ML Crash Course](https://developers.google.com/machine-learning/crash-course/llm/tuning)). ‘prompt design’은 흔히 동의어다([Google ML Glossary](https://developers.google.com/machine-learning/glossary)). 반면 ‘context engineering’은 아직 단일 표준 정의나 독립된 합의 벤치마크가 없다. 실무에서는 에이전트와 RAG가 확대되며 프롬프트 문자열을 넘어 **추론 시 입력 상태 전체를 만드는 규율**을 가리키는 용어로 정착 중이다. 따라서 “프롬프트 엔지니어링은 끝났고 컨텍스트 엔지니어링이 대체했다”는 주장은 수사에 가깝다.

구분 질문은 간단하다.

| 질문 | 주된 영역 |
|---|---|
| 같은 입력에서 어떤 지시 문구와 예시가 낫나? | 프롬프트 |
| 어떤 문서·메모리·도구를 언제 넣고 뺄까? | 컨텍스트 |
| JSON 필드를 어떻게 강제할까? | 프롬프트 + 스키마/API |
| 긴 대화를 어떻게 요약하고 원본과 연결할까? | 컨텍스트 |
| 모델 변경 후 품질 저하를 어떻게 잡을까? | 둘의 운영/평가 |

## 역사와 용어의 전개

- **2018–2020: 사전학습 모델과 in-context learning.** GPT-3는 자연어 설명과 소수 예시만으로 여러 과제를 수행하는 few-shot 능력을 체계적으로 보여 주었다([Brown et al., 2020](https://arxiv.org/abs/2005.14165)). PET와 prompt-based learning 계열은 분류 과제를 자연어 패턴으로 바꾸는 연구 흐름을 만들었다.
- **2021–2022: 추론 프롬프트의 폭발.** Chain-of-Thought(CoT)([Wei et al.](https://arxiv.org/abs/2201.11903)), zero-shot “step by step”([Kojima et al.](https://arxiv.org/abs/2205.11916)), self-consistency([Wang et al.](https://arxiv.org/abs/2203.11171)), generated knowledge([Liu et al.](https://arxiv.org/abs/2110.08387)), least-to-most([Zhou et al.](https://arxiv.org/abs/2205.10625))가 등장했다.
- **2020–2023: 검색과 행동 결합.** RAG는 생성 모델에 외부 검색을 결합했다([Lewis et al., 2020](https://arxiv.org/abs/2005.11401)). ReAct는 추론과 행동/관찰을 교차시켰다([Yao et al., 2022/ICLR 2023](https://arxiv.org/abs/2210.03629)). Toolformer는 도구 사용 학습을 탐구했다([Schick et al.](https://arxiv.org/abs/2302.04761)).
- **2023–2024: 장문맥·에이전트·자동 최적화.** 긴 문맥의 위치 편향이 드러났고, APE·OPRO·DSPy·TextGrad 같은 데이터 기반 프롬프트/프로그램 최적화가 발전했다. Reflection/Reflexion 계열은 실행 피드백을 다음 시도에 반영했다([Reflexion](https://arxiv.org/abs/2303.11366)).
- **2024–2026: 컨텍스트를 운영 체계로 다루기.** 공급자 API가 구조화 출력, 함수 호출, prompt/context caching, stateful responses, context editing/compaction, 에이전트 평가를 제공한다. 장문맥 자체보다 적시 검색, 상태 관리, 권한 경계, 관측 가능성이 중심 문제가 되었다. 용어는 널리 쓰이나 학술적 경계는 여전히 유동적이다.

## 프롬프팅 기법별 설명

### 기본 설계

**Zero-shot**은 지시만, **one/few-shot**은 하나/소수의 입출력 예시를 준다. 예시는 라벨 의미, 경계 사례, 형식을 자연어 설명보다 강하게 전달하지만 토큰을 쓰고 예시 편향을 만든다. 대표·난해·금지 사례를 섞고 실제 분포와 맞추며 예시 안의 민감정보를 제거한다. Google은 few-shot이 일반적으로 zero/one-shot보다 나을 수 있지만 더 긴 프롬프트를 요구한다고 정리한다([Glossary](https://developers.google.com/machine-learning/glossary)).

**역할과 지시 설계**는 페르소나 장식보다 업무 계약이 핵심이다. (1) 목표, (2) 입력의 의미와 신뢰도, (3) 반드시/절대 하지 않을 일, (4) 정보 부족 시 행동, (5) 출력 계약, (6) 성공 기준 순으로 쓴다. 긍정형 행동 지시를 우선하고 충돌 규칙을 명시한다. Anthropic은 명시적 지시, 이유가 있는 맥락, 원하는 행동과 일치하는 예시를 권한다([Claude prompting best practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices)).

**구분자와 구조화 출력**은 지시와 데이터를 섞지 않게 한다. Markdown/XML 태그, 명확한 필드명을 사용하되 태그만으로 주입이 방지되지는 않는다. 기계 소비 출력은 “JSON처럼 써라”보다 API의 JSON Schema/strict structured outputs를 사용하고 서버에서 재검증한다([OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)). 자유 텍스트와 실행 인자를 같은 채널로 처리하지 않는다.

### 추론, 분해, 검증

**CoT 관련 방법**은 복잡한 산술·상징·다단계 문제에서 중간 추론 예시가 성능을 높일 수 있음을 보였다. 그러나 효과는 모델·과제에 의존하고, 장황한 출력은 오류를 그럴듯하게 만들며 비용과 유출 표면을 늘린다. 실무 안전 패턴은 “문제를 내부적으로 검토하고, 답에는 결론·핵심 근거·검증 가능한 계산만 제시”하는 것이다. 정확성이 중요하면 자연어 사고 원문보다 코드 실행, 검색 인용, 테스트 결과 같은 외부 검증 수단을 쓴다.

**Self-consistency**는 서로 다른 추론 경로를 여러 번 샘플링해 최종 답의 다수/일관성을 선택한다. 단일 생성보다 비싸며, 같은 체계적 오류가 반복되면 도움되지 않는다. 신뢰도 추정과 동일시하지 말고 표본 수, 온도, 집계 규칙을 기록한다.

**Generated knowledge**는 답하기 전 관련 지식을 생성한 뒤 활용한다. 폐쇄형·검증 가능한 상식 과제에는 유용할 수 있으나, 생성 지식 자체가 환각일 수 있다. 고위험·최신 사실에서는 검색된 1차 근거로 대체한다.

**Least-to-most / decomposition**은 쉬운 하위 문제부터 풀어 결과를 다음 단계에 공급한다. **Prompt chaining**은 단계별 출력 계약과 검증/재시도를 둘 수 있어 긴 단일 프롬프트보다 관측 가능하다. 단, 각 단계 오류가 누적될 수 있으므로 원문 provenance와 실패 상태를 보존한다.

**ReAct**는 생각–행동–관찰의 반복으로 검색·계산·API 사용을 결합한다. 실제 제품에서는 자유 형식 “Thought” 문자열보다 구조화된 tool call, 제한된 횟수, 타임아웃, 멱등성, 권한 검사, 결과 검증을 사용한다.

**Reflection/critique**는 초안을 기준표로 비평해 수정한다. 생성자와 비평자가 같은 모델이면 상관 오류가 크다. 독립 근거, 별도 모델/규칙, 유닛 테스트나 사람 검토를 섞고, 무한 수정 루프를 막는다.

### 오케스트레이션과 도구

**Routing**은 의도·위험·언어·난도에 따라 프롬프트, 검색기, 모델, 사람 승인 경로를 선택한다. 라우터 오분류를 별도 평가하고 낮은 확신에는 안전한 기본 경로를 둔다.

**Tool/function use**에서는 도구 설명이 곧 컨텍스트이자 공격 표면이다. 짧고 상호 배타적인 도구명, 엄격한 JSON Schema, enum/범위 제한, 최소 권한, 실행 전 정책 검사, 결과의 불신 원칙을 적용한다. 모델의 “호출 의도”와 실제 권한 부여를 분리한다.

**Multimodal prompting**은 이미지·오디오·문서의 목표 영역, 시간 구간, 읽기 순서, 원하는 근거를 명시한다. OCR 오류·보이지 않는 텍스트·메타데이터에 의한 간접 주입을 고려하고, 중요 수치나 텍스트는 별도 추출·검증한다.

**Retrieval-augmented prompting**은 최신/사내 지식을 JIT로 가져온다. 질의 재작성→검색→필터/재순위→중복 제거→출처 라벨→생성→인용 검증의 파이프라인이다. “문맥에 없으면 모른다고 말하라”, 충돌 출처 처리, 인용 형식을 명시한다. Microsoft의 공식 RAG 가이드는 검색 품질과 생성 품질을 분리하고, 너무 많은 청크·불명확한 grounding·fallback 부재를 안티패턴으로 든다([Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-prompt-engineering)).

**자동 프롬프트 최적화**는 평가 데이터와 점수를 이용해 지시·예시·프로그램을 탐색한다. APE([Zhou et al.](https://arxiv.org/abs/2211.01910)), OPRO([Yang et al.](https://arxiv.org/abs/2309.03409)), DSPy([Khattab et al.](https://arxiv.org/abs/2310.03714)), TextGrad([Yuksekgonul et al.](https://arxiv.org/abs/2406.07496))가 대표적이다. 학습셋 과적합, judge 편향, 다른 모델/분포로의 전이 실패가 핵심 한계다. 반드시 held-out 세트와 수동 실패 분석을 둔다. AWS도 최적화 후 보지 않은 데이터로 검증하라고 권고한다([Bedrock evaluation methods](https://docs.aws.amazon.com/bedrock/latest/userguide/advanced-prompt-optimization-evaluation.html)).

## 컨텍스트 엔지니어링 아키텍처

### 계층과 신뢰 경계

메시지 역할은 공급자별로 다르다. OpenAI API에서는 developer/system 지시가 user보다 우선한다([Evals API 역할 설명](https://platform.openai.com/docs/api-reference/evals)); Anthropic은 최상위 `system`과 교대 user/assistant 메시지 모델을 사용한다; Gemini는 system instruction과 contents를 구분한다. **보편적이라고 가정하지 말고 각 API의 역할·도구 결과 의미를 확인**한다.

권장 컨텍스트 층:

1. 불변 정책과 권한(최상위, 짧고 캐시 가능)
2. 애플리케이션/작업 지시와 출력 스키마
3. 신뢰된 업무 상태와 사용자별 권한
4. few-shot 예시
5. 요청 시 검색된 문서·도구 결과(불신 데이터)
6. 최근 대화와 현재 사용자 입력

데이터 안의 명령은 명령으로 승격하지 않는다. 출처·시간·테넌트·ACL을 메타데이터로 유지하고, 사용자 권한보다 넓은 문서를 검색 단계에서 차단한다.

### 토큰 예산과 선택

컨텍스트 창은 입력+출력+일부 모델 내부 예산을 공유할 수 있다. 먼저 예상 출력과 도구 왕복을 예약하고 나머지를 지침, 예시, 검색, 대화에 배분한다. 청크 수를 “최대”가 아니라 eval로 조정한다. 우선순위는 대체로 **현재 목표/제약 > 직접 근거 > 최근 유효 상태 > 대표 예시 > 배경**이다.

선택 파이프라인은 freshness/authority/ACL 필터, hybrid 검색, reranking, 다양성, 중복 제거, 모순 묶기, 토큰 한도 절단을 포함한다. 문맥이 길수록 질문을 끝에 가까이 두는 것이 낫다는 Gemini 공식 지침이 있지만([Long context](https://ai.google.dev/gemini-api/docs/long-context)), 공급자·모델별로 평가해야 한다. 중요한 지침은 시작에, 최종 질문과 답 형식은 검색 문맥 뒤에 재명시하는 “sandwich”가 실용적이다.

### 압축, 기억, 상태

- **최근 창 + 요약 + 원본 포인터**: 최근 턴은 그대로, 오래된 턴은 사실/결정/미해결 항목으로 구조화 요약한다.
- **의미 기억과 일화 기억 분리**: 사용자 선호 같은 안정 사실과 과거 사건/대화를 구분하고 TTL·수정·삭제·출처를 둔다.
- **결정 로그/작업 상태는 구조화**: 자연어 대화에서 재추론하지 말고 typed state에 저장한다.
- **요약 손실 방지**: 숫자, 부정, 승인 범위, 출처, 미해결 충돌을 보존하고 원문으로 drill-down할 수 있게 한다.
- **쓰기 정책**: 모델이 제안하고 애플리케이션이 검증 후 저장한다. 민감정보, 일시적 감정, 추론 원문을 장기 기억에 자동 저장하지 않는다.

**Context rot**은 엄밀한 단일 메트릭보다, 문맥이 길고 반복·모순·오래된 정보가 쌓이며 유효 성능이 나빠지는 실무 용어다. *Lost in the Middle*은 관련 정보가 시작/끝보다 중간에 있을 때 성능이 떨어질 수 있음을 보였지만, 모든 최신 모델과 모든 과제의 보편 법칙으로 과장하면 안 된다.

### 캐시, JIT 컨텍스트, 컴팩션

공통의 큰 prefix(정책, 스키마, 정적 자료)를 앞에 두고 사용자별/동적 입력을 뒤에 두면 prompt cache hit를 높일 수 있다. Gemini는 2.5 이상에서 implicit caching과 명시적 cache를 설명하며 공통 토큰을 앞에 둘 것을 권한다([Context caching](https://ai.google.dev/gemini-api/docs/caching)). 캐시는 의미적 정확성을 보장하지 않으며 TTL, 데이터 보존, 개인정보, 테넌트 격리를 검토해야 한다.

JIT 컨텍스트는 모든 것을 미리 넣지 않고 필요할 때 검색/도구로 가져오는 원칙이다. 짧은 탐색 호출→정확한 원문 호출의 두 단계가 비용을 줄인다. 컴팩션은 임계 토큰 전에 수행하고, 요약 버전·근거 포인터·누락 가능성을 기록한다.

### 멀티에이전트 경계

에이전트마다 필요한 최소 컨텍스트만 주고, 전체 대화나 비밀을 복제하지 않는다. 위임 봉투에는 목표, 범위, 권한, 입력/출력 경로, 완료 조건, provenance를 넣는다. 병렬 에이전트 결과는 사실/가설/결론을 구분하고 독립 검토한다. 에이전트 간 자연어 메시지를 신뢰된 system 지시로 승격하지 않으며, 도구 자격증명은 작업별로 축소한다.

## 공급자별 차이

| 공급자 | 공식 지침에서 두드러진 점 | 주의 |
|---|---|---|
| OpenAI | developer/system 우선순위, strict schema, function tools, evals, pinned snapshots, prompt caching | GPT 계열과 reasoning 계열의 프롬팅 지침이 다름; 모델 교체 시 회귀 평가 |
| Anthropic | 명시적 지시, XML 태그, multishot, 긴 문서에서 질의를 뒤에, prompt caching/context editing | 모델 세대별 best practice가 달라짐; 도구 결과도 불신 데이터 |
| Google Gemini | multimodal/긴 문맥, 질의를 문맥 뒤에, implicit/explicit caching | 큰 창이 검색·선별을 자동 대체하지 않음 |
| Microsoft/Azure | RAG 아키텍처별 prompting, token budget, grounding·completeness·utilization 평가, prompt flow | 서비스 지표와 실제 비즈니스 결과를 구분 |
| AWS Bedrock | 모델별 prompt 형식, guardrails, prompt optimization과 held-out 평가 | Guardrail이 tool result를 모두 검사하는지 등 적용 범위 확인 |
| Meta/Llama | 모델 카드와 prompt format/chat template, Llama Guard/Prompt Guard | 호스팅 스택마다 템플릿·토크나이저가 달라 공식 모델 카드 확인 |

공통 조언은 “명확히 쓰고, 예시를 주고, 평가하라” 정도다. 역할 토큰, 권장 XML/Markdown, 추론 유도, 캐싱 조건, 구조화 출력 보장은 공급자별이다.

## 평가와 운영

### 평가 단위

1. **데이터셋**: 정상·경계·모호·충돌·정보 부족·다국어·긴 입력·공격 예시를 실제 빈도로 층화한다.
2. **컴포넌트**: 라우팅 정확도, retrieval recall/nDCG, reranker, context precision/recall, tool 선택/인자, schema 유효성.
3. **최종 결과**: 정확성, 근거성, 완전성, 관련성, 기권/명확화, 안전, 사용자 과업 성공.
4. **운영**: p50/p95 latency, time-to-first-token, 입력/출력/캐시 토큰, 도구 실패·재시도, 비용/성공 건, 가용성.

RAGAs는 reference-free RAG 평가를 제시했지만([EACL 2024](https://aclanthology.org/2024.eacl-demo.16/)), LLM judge는 위치·문체·자기모델 편향이 있고 정답을 대체하지 않는다. 사람 라벨의 anchor set으로 judge를 보정하고, judge prompt/model도 버전 고정한다. BERGEN은 RAG 구성 비교의 재현성 문제를 지적한다([EMNLP 2024](https://aclanthology.org/2024.findings-emnlp.449/)). 2026년 MTRAGEval은 다중 턴에서 unanswerable뿐 아니라 underspecified·non-standalone·unclear 질의를 분리한다([SemEval 2026](https://aclanthology.org/2026.semeval-1.447/)).

### 변경 절차

`prompt_id`, 의미 버전, 템플릿 해시, 모델 스냅샷, 디코딩, 도구/스키마 버전, retrieval index, 데이터셋 버전, 실험 ID를 함께 기록한다. 변경 하나씩 offline 회귀→안전 평가→shadow/canary→A/B→확대한다. 온라인 A/B는 클릭만 보지 말고 해결률, 재질문, 잘못된 자동 실행, 사람 에스컬레이션을 본다. 로그는 원문 최소화·PII 마스킹·보존 기간·접근 통제를 적용한다.

재현성은 seed만으로 보장되지 않는다. 공급자 백엔드와 도구/검색 결과가 변한다. 입력/출력, 문서 ID와 버전, 시각, 모델 snapshot, 호출 파라미터를 가능한 범위에서 캡처하고 통계적 반복을 사용한다.

## 보안과 실패 모드

| 실패/공격 | 원인 | 방어 |
|---|---|---|
| 직접 prompt injection/jailbreak | 사용자 입력이 지시를 탈취 | 역할 분리, 정책 검사, 공격 eval, 최소 권한, 출력/행동 검증 |
| 간접 injection | 웹·메일·문서·도구 결과 속 명령 | 외부 콘텐츠 격리/라벨, sanitize, action policy, 승인, allowlist |
| 데이터/프롬프트 유출 | 비밀을 컨텍스트에 넣거나 출력 경로 허용 | 비밀 미주입, DLP, 테넌트 격리, egress 통제, redaction |
| instruction conflict | 정책·예시·문서의 명령 충돌 | 계층 명시, 데이터는 명령 아님, 충돌 시 중단/명확화 |
| hallucination | 근거 부족, 생성 지식 과신 | 검색·인용 검증, 기권, 계산/도구, 사람 검토 |
| noisy/overlong context | 중복·낡은 상태·위치 편향 | 필터/rerank/dedupe, 예산, compaction, 회귀 평가 |
| retrieval poisoning | 공격자가 corpus/순위를 조작 | ingestion 서명/ACL, provenance, 이상 탐지, 신뢰도 rerank |
| tool misuse | 과권한·모호한 schema·비멱등 호출 | least privilege, strict schema, dry-run, 승인, idempotency |

NIST AI 600-1은 간접 주입을 원격 데이터에 삽입된 지시가 LLM 통합 애플리케이션에 검색되는 공격으로 다루고, 개인정보·안전·보안·신뢰성을 함께 관리하라고 한다([NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)). OWASP LLM01:2025는 RAG와 fine-tuning이 주입을 완전히 해결하지 않는다고 명시한다([LLM01](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)).

중요한 원칙은 **프롬프트를 보안 경계로 믿지 않는 것**이다. 모델이 거부하도록 쓰는 문장은 보조 통제다. 인증/인가, 샌드박스, 네트워크 제한, 승인, transaction limit, 서버 측 schema 검증이 실제 경계다. AWS Guardrails 문서상 일부 prompt-attack 필터가 tool result를 평가하지 않는 등 제품별 범위 차이가 있으므로 확인해야 한다([Bedrock prompt attack](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html)).

## 도메인별 작업 예시

### 채팅 지원

정책/톤→고객 권한→최근 3–5턴→필요 시 고객 문서 검색→답변과 출처 순으로 구성한다. 모호하면 한 가지 핵심 질문만 하고, 환불·계정 변경은 도구 호출 전 확인 화면을 둔다. 안티패턴은 전체 CRM 기록과 오래된 대화를 매번 넣는 것이다.

### 구조화 추출

필드 정의, null 규칙, 단위/날짜 표준, 겹치는 라벨의 판정 기준, 2–5개 경계 예시를 제공하고 strict JSON Schema로 받는다. 근거 span/페이지를 함께 추출하고 서버 검증 실패는 재시도 또는 사람 큐로 보낸다. 보이지 않는 값을 추측하지 않는다.

### 코딩 에이전트

저장소 지침→요청→관련 파일/심볼 검색→작은 변경→정적 검사/테스트(권한 있을 때)→diff 요약의 루프다. 전체 저장소를 한 번에 넣지 말고 symbol/search로 JIT 로드한다. 셸·네트워크·삭제 권한을 분리하고, 웹/issue의 명령을 untrusted로 처리한다.

### 연구 에이전트

질문·기간·포함 기준을 먼저 고정하고, 개요 자료에서 원출처로 추적한다. 관찰/해석/가설을 분리하고 URL·날짜·식별자를 기록한다. 여러 검색 query family, 반증 검색, paywall/누락 공개가 필요하다. “검색 결과 수”를 증거 품질로 오해하지 않는다.

### 엔터프라이즈 RAG

질문에 사용자/테넌트 ACL을 결합→hybrid retrieval→rerank/dedupe→authority/freshness 라벨→충돌 감지→인용 답변/기권이다. retrieval과 generation을 각각 평가한다. 인덱스 생성 시 문서 버전·owner·ACL·유효기간·해시를 저장하고 삭제 전파를 시험한다.

## 의사결정 프레임워크

| 상황 | 먼저 선택 | 이유 |
|---|---|---|
| 형식/톤/명확한 규칙이 문제 | 프롬프트 + schema | 가장 싸고 빠르게 검증 가능 |
| 최신/사내 사실이 부족 | RAG/JIT 도구 | 파라미터 지식보다 출처·갱신 가능 |
| 긴 대화가 문제 | state + memory + compaction | 창 확대만으로 낡은/모순 정보 해결 안 됨 |
| 반복 과제에서 prompt가 불안정 | 데이터셋+eval, 자동 최적화 검토 | 문구 감각보다 측정 가능한 반복 |
| 행동 위험이 큼 | 권한 축소+정책+승인 | 프롬프트는 보안 경계가 아님 |
| 지식/스타일이 대규모로 고정 | fine-tuning/증류 검토 | 매 요청 긴 예시보다 비용 효율 가능; 별도 평가 필요 |

## 재사용 체크리스트

**설계 전**

- [ ] 사용자 결과와 실패 비용, 사람 소유 결정을 정의했다.
- [ ] 최신 정보/사내 정보/도구/기억 중 무엇이 필요한지 분리했다.
- [ ] 입력별 신뢰도·ACL·민감도를 표시했다.
- [ ] 대표/경계/공격/기권 예시가 있는 eval set을 만들었다.

**프롬프트**

- [ ] 목표, 입력 의미, 제약, 부족/충돌 시 행동, 출력 계약이 명확하다.
- [ ] 예시는 실제 분포와 맞고 잘못된 행동을 암시하지 않는다.
- [ ] 기계 출력은 schema로 검증한다.
- [ ] 모델별 공식 가이드에 맞췄다.

**컨텍스트**

- [ ] 출력과 도구 왕복 토큰을 먼저 예약했다.
- [ ] 검색 결과를 ACL/freshness/authority로 필터하고 dedupe/rerank한다.
- [ ] 최근 상태와 장기 기억, 사실과 요약, 명령과 데이터를 분리한다.
- [ ] 압축 뒤에도 결정·숫자·부정·출처·미해결 항목을 보존한다.

**운영·보안**

- [ ] prompt/model/schema/index 버전과 비용·지연·품질을 추적한다.
- [ ] retrieval, generation, tool action을 따로 평가한다.
- [ ] 직접/간접 주입과 corpus poisoning 회귀셋이 있다.
- [ ] 최소 권한, 서버 검증, 승인, 감사 로그, kill switch가 있다.

## 논쟁, 모순, 근거 공백

1. **“컨텍스트 엔지니어링”의 정의**: 실무적 우산 용어로 유용하지만 표준 경계와 직접 벤치마크가 없다.
2. **CoT의 가치**: 초기 연구는 큰 이득을 보고했지만 최신 reasoning model에서는 장황한 유도가 방해될 수 있고, 공개 추론은 보안·품질 문제가 있다. 과제/모델별 평가가 답이다.
3. **장문맥 대 RAG**: 큰 창은 전체 문서 비교와 멀티모달 분석에 유리하고, RAG는 비용·갱신·접근통제·인용에 유리하다. 둘은 혼합된다.
4. **LLM-as-judge**: 규모화에 유용하지만 사람 판단의 완전한 대체가 아니다. 모델/프롬프트 편향과 데이터 누출을 보정해야 한다.
5. **자동 최적화**: 벤치마크 향상은 있으나 다른 과제·모델·실제 분포로의 전이가 불안정하다. 2026년 연구도 task-conditioned edit 효과와 전이 한계를 보고한다([Gong & Wen](https://arxiv.org/abs/2605.26655)).
6. **주입 방어**: 완전한 일반 해법은 없다. 필터의 false positive/negative, 멀티모달·다중 턴·간접 공격에 대한 공개 비교가 부족하다.
7. **벤더 주장**: 긴 문맥 정확도, 캐시 절감, guardrail 성능은 특정 모델·가격·구성에 종속된다. 독립 재현과 실제 워크로드 평가가 필요하다.

## 전망과 결론

향후 중심은 프롬프트 문장 자체보다 (1) JIT context와 typed state, (2) 자동 compaction과 provenance, (3) retrieval/tool/agent trajectory 평가, (4) 정책 기반 action authorization, (5) 멀티모달·다중 에이전트의 신뢰 경계, (6) 데이터 기반 prompt/context compiler로 이동할 가능성이 크다. 그러나 자연어 지시와 예시는 계속 인터페이스의 핵심이다.

실무 순서는 **과업과 평가 정의 → 최소 프롬프트 → 필요한 정보만 JIT 구성 → 구조화 도구/출력 → 권한과 보안 경계 → 회귀·온라인 평가 → 비용/지연 최적화**가 가장 안정적이다. 큰 창, 더 긴 지시, 더 많은 에이전트는 목표가 아니라 선택지다.

가장 작은 후속 Inquiry는 동일한 50–100개 한국어 평가셋으로 주요 공급자의 최신 모델을 비교해, 문맥 길이·정보 위치·RAG 청크 수·구조화 출력·간접 주입 방어를 실제로 측정하는 것이다.
