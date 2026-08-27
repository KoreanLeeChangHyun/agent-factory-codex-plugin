# 출처 카탈로그

> 접근일은 전 항목 **2026-08-28**. 중복 URL은 제거했다. 날짜는 원문에서 확인 가능한 최초 공개/논문 연도 또는 페이지의 갱신일이며, `n.d.`는 명확히 표시되지 않음을 뜻한다. 보고서로 돌아가기: [report-ko.md](report-ko.md).

## 1. 1차 연구와 벤치마크

1. **Language Models are Few-Shot Learners** — Brown et al., 2020, arXiv:2005.14165. [원문](https://arxiv.org/abs/2005.14165). 연구/NeurIPS. GPT-3의 zero/one/few-shot in-context learning을 대규모로 제시한 출발점.
2. **Chain-of-Thought Prompting Elicits Reasoning in Large Language Models** — Wei et al., 2022, arXiv:2201.11903. [원문](https://arxiv.org/abs/2201.11903). 연구/NeurIPS. CoT의 대표 논문.
3. **Large Language Models are Zero-Shot Reasoners** — Kojima et al., 2022, arXiv:2205.11916. [원문](https://arxiv.org/abs/2205.11916). 연구/NeurIPS. zero-shot step-by-step 유도의 초기 결과.
4. **Self-Consistency Improves Chain of Thought Reasoning** — Wang et al., 2022/ICLR 2023, arXiv:2203.11171. [원문](https://arxiv.org/abs/2203.11171). 연구. 여러 추론 경로 집계.
5. **Generated Knowledge Prompting for Commonsense Reasoning** — Liu et al., 2021/ACL 2022, arXiv:2110.08387. [원문](https://arxiv.org/abs/2110.08387). 연구. 답 전 지식 생성.
6. **Least-to-Most Prompting Enables Complex Reasoning** — Zhou et al., 2022/ICLR 2023, arXiv:2205.10625. [원문](https://arxiv.org/abs/2205.10625). 연구. 문제를 쉬운 하위 문제로 순차 분해.
7. **ReAct: Synergizing Reasoning and Acting in Language Models** — Yao et al., 2022/ICLR 2023, arXiv:2210.03629. [원문](https://arxiv.org/abs/2210.03629). 연구. 추론·행동·관찰 루프.
8. **Reflexion: Language Agents with Verbal Reinforcement Learning** — Shinn et al., 2023, arXiv:2303.11366. [원문](https://arxiv.org/abs/2303.11366). 연구/NeurIPS. 피드백을 언어 기억으로 반영.
9. **Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks** — Lewis et al., 2020, arXiv:2005.11401. [원문](https://arxiv.org/abs/2005.11401). 연구/NeurIPS. RAG의 대표 원전.
10. **Toolformer** — Schick et al., 2023, arXiv:2302.04761. [원문](https://arxiv.org/abs/2302.04761). 연구/NeurIPS. API 호출을 학습하는 접근.
11. **Lost in the Middle: How Language Models Use Long Contexts** — Liu et al., 2023/TACL 2024, arXiv:2307.03172. [원문](https://arxiv.org/abs/2307.03172). 연구. 긴 문맥의 위치 편향을 대표적으로 측정.
12. **Automatic Prompt Engineer (APE)** — Zhou et al., 2022/ICLR 2023, arXiv:2211.01910. [원문](https://arxiv.org/abs/2211.01910). 연구. LLM이 후보 지시를 생성·선택.
13. **Large Language Models as Optimizers (OPRO)** — Yang et al., 2023/ICLR 2024, arXiv:2309.03409. [원문](https://arxiv.org/abs/2309.03409). 연구. 자연어 최적화 궤적.
14. **DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines** — Khattab et al., 2023/ICLR 2024, arXiv:2310.03714. [원문](https://arxiv.org/abs/2310.03714). 연구/프레임워크. 프롬프트가 아니라 LM 프로그램을 데이터로 최적화.
15. **TextGrad: Automatic Differentiation via Text** — Yuksekgonul et al., 2024, arXiv:2406.07496. [원문](https://arxiv.org/abs/2406.07496). 연구. 자연어 피드백을 ‘텍스트 기울기’로 사용.
16. **Why Prompt Optimization Works, and Why It Sometimes Doesn't** — Gong & Wen, 2026, arXiv:2605.26655. [원문](https://arxiv.org/abs/2605.26655). 최근 1차 연구. optimizer의 과제별 전이 한계와 edit family 효과.
17. **RAGAs: Automated Evaluation of Retrieval Augmented Generation** — Es et al., EACL 2024, DOI 10.18653/v1/2024.eacl-demo.16. [원문](https://aclanthology.org/2024.eacl-demo.16/). 연구/도구. reference-free RAG 평가.
18. **BERGEN: A Benchmarking Library for RAG** — Rau et al., EMNLP 2024, DOI 10.18653/v1/2024.findings-emnlp.449. [원문](https://aclanthology.org/2024.findings-emnlp.449/). 연구/라이브러리. 재현 가능한 구성요소 비교.
19. **MIRAGE: A Metric-Intensive Benchmark for RAG Evaluation** — Wang et al., NAACL 2025, DOI 10.18653/v1/2025.findings-naacl.157. [원문](https://aclanthology.org/2025.findings-naacl.157/). 연구. retrieval/generation 구성요소별 평가.
20. **MEMERAG** — ACL 2025, DOI 10.18653/v1/2025.acl-long.1101. [원문](https://aclanthology.org/2025.acl-long.1101/). 연구. 다국어 RAG와 LLM judge meta-evaluation.
21. **T2-RAGBench** — Strich et al., EACL 2026, DOI 10.18653/v1/2026.eacl-long.8. [원문](https://aclanthology.org/2026.eacl-long.8/). 연구. 23,088 text/table QA, 실제 검색과 수치 추론을 함께 평가.
22. **SemEval-2026 Task 8: MTRAGEval** — 2026, DOI 10.18653/v1/2026.semeval-1.447. [원문](https://aclanthology.org/2026.semeval-1.447/). 벤치마크. 다중 턴의 unanswerable/underspecified/non-standalone/unclear 질의.
23. **LIT-RAGBench** — Itai et al., LREC 2026, DOI 10.18653/v1/2026.lrec-1.427. [원문](https://aclanthology.org/2026.lrec-1.427/). 벤치마크. 통합·추론·논리·표·기권 능력.
24. **PFW at MTRAGEval** — Tamsal & Rusert, SemEval 2026, DOI 10.18653/v1/2026.semeval-1.198. [원문](https://aclanthology.org/2026.semeval-1.198/). 실증 시스템 보고. 작은 표본에서 명시적 인용 형식의 큰 효과와 underspecified 약점을 보고.

## 2. 공식 공급자 문서

25. **Best practices for prompt engineering with the OpenAI API** — OpenAI, 2026 갱신. [원문](https://help.openai.com/en/articles/6654000-playground-and-prompt-engineering). 공식 가이드. 지시 우선 배치, 구분자, 명확성, 형식 예시.
26. **Prompt engineering best practices for ChatGPT** — OpenAI, 2026 갱신. [원문](https://help.openai.com/en/articles/10032626). 공식 가이드. 정의와 반복 개선.
27. **Structured Outputs** — OpenAI, n.d. [원문](https://platform.openai.com/docs/guides/structured-outputs). 공식 API 문서. JSON Schema 기반 출력 계약.
28. **Function calling** — OpenAI, n.d. [원문](https://platform.openai.com/docs/guides/function-calling). 공식 API 문서. 도구 스키마와 호출 루프.
29. **Evals API** — OpenAI, 2026 확인. [원문](https://platform.openai.com/docs/api-reference/evals). 공식 API 문서. 데이터셋과 grader 구성, 메시지 역할.
30. **Backward compatibility** — OpenAI, 2026 확인. [원문](https://platform.openai.com/docs/api-reference/backward-compatibility). 공식 API 문서. snapshot pinning과 eval 권고.
31. **Prompt caching** — OpenAI, n.d. [원문](https://platform.openai.com/docs/guides/prompt-caching). 공식 문서. 공통 prefix 캐싱과 사용량.
32. **A practical guide to building agents** — OpenAI, 2025. [원문](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf). 공식 실무 가이드. 모델 선택, 도구, 가드레일, eval.
33. **Claude prompt engineering overview** — Anthropic, n.d. [원문](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview). 공식 가이드 허브.
34. **Claude 4 prompting best practices** — Anthropic, 2025. [원문](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices). 공식 모델별 가이드. 명시성, 맥락, XML, 예시.
35. **Use XML tags** — Anthropic, n.d. [원문](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags). 공식 가이드. 지시/데이터 구조화.
36. **Long context tips** — Anthropic, n.d. [원문](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips). 공식 가이드. 긴 문서와 질의 배치.
37. **Prompt caching** — Anthropic, n.d. [원문](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching). 공식 API 문서. cache breakpoint와 비용/TTL.
38. **Context windows** — Anthropic, n.d. [원문](https://docs.anthropic.com/en/docs/build-with-claude/context-windows). 공식 문서. 창 계산과 모델별 동작.
39. **Gemini long context** — Google AI, 2026 갱신. [원문](https://ai.google.dev/gemini-api/docs/long-context). 공식 문서. 멀티모달 장문맥, 질문 후위 배치, 비용/지연.
40. **Gemini context caching** — Google AI, 2026-07-30 갱신. [원문](https://ai.google.dev/gemini-api/docs/caching). 공식 문서. implicit/explicit cache와 prefix 권고.
41. **Prompt engineering for generative AI** — Google Developers, 2024. [원문](https://developers.google.com/machine-learning/resources/prompt-eng). 공식 교육. 기본 구조, 예시, 제약, 분해.
42. **ML Glossary: prompt engineering/few-shot/prompt chaining** — Google, 2026 갱신. [원문](https://developers.google.com/machine-learning/glossary). 공식 용어집.
43. **Fine-tuning, distillation, and prompt engineering** — Google, 2025. [원문](https://developers.google.com/machine-learning/crash-course/llm/tuning). 공식 교육. 파라미터 변경 여부의 경계.
44. **Prompt engineering for RAG** — Microsoft Azure Architecture Center, 2026. [원문](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-prompt-engineering). 공식 아키텍처 지침. token budget, chunk ordering, grounding, A/B, anti-pattern.
45. **RAG evaluators** — Microsoft Foundry, 2026. [원문](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/rag-evaluators). 공식 문서. retrieval 품질 평가.
46. **Detect prompt attacks with Bedrock Guardrails** — AWS, 2026 확인. [원문](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html). 공식 제품 문서. jailbreak/injection/leakage와 필터 적용 범위.
47. **Bedrock prompt optimization evaluation methods** — AWS, 2026. [원문](https://docs.aws.amazon.com/bedrock/latest/userguide/advanced-prompt-optimization-evaluation.html). 공식 문서. 대표 데이터와 held-out 검증.
48. **Agentic AI input validation and guardrails** — AWS, 2026. [원문](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-security/best-practices-input-validation.html). 공식 보안 지침. 다층 방어와 관측.
49. **Llama model documentation** — Meta, n.d. [원문](https://www.llama.com/docs/overview/). 공식 허브. 모델 카드, chat template, 도구 사용 확인 출발점.

## 3. 표준·보안 지침

50. **NIST AI 600-1, Generative AI Profile** — NIST, 2024. [원문 PDF](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf). 정부 표준 지침. 생성형 AI 위험, 간접 주입, 거버넌스.
51. **OWASP LLM01:2025 Prompt Injection** — OWASP, 2025. [원문](https://genai.owasp.org/llmrisk/llm01-prompt-injection/). 보안 지침. injection/jailbreak 구분과 영향, RAG/fine-tuning의 한계.
52. **LLM Prompt Injection Prevention Cheat Sheet** — OWASP, 2026 확인. [원문](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html). 보안 지침. 직접·간접·멀티모달·RAG·에이전트 공격과 방어.
53. **RAG Security Cheat Sheet** — OWASP, 2026 확인. [원문](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html). 보안 지침. ingestion부터 output까지 전 파이프라인 통제.
54. **MITRE ATLAS** — MITRE, 지속 갱신. [원문](https://atlas.mitre.org/). 위협 지식베이스. AI 공격 전술·기법의 공통 분류.

## 4. 유지되는 오픈소스/도구

> 아래는 기능 존재와 실무 유용성을 위한 출처다. 성능 우월성 증거가 아니며, 유지 상태·라이선스·보안은 도입 시 재확인해야 한다.

55. **DSPy** — Stanford NLP, 유지형 저장소. [GitHub](https://github.com/stanfordnlp/dspy). LM 프로그램 선언과 optimizer.
56. **LangChain** — LangChain, 유지형 저장소. [GitHub](https://github.com/langchain-ai/langchain). 모델·retrieval·tool orchestration 생태계; 추상화 누수와 버전 변화를 평가해야 함.
57. **LlamaIndex** — LlamaIndex, 유지형 저장소. [GitHub](https://github.com/run-llama/llama_index). 문서 ingestion·index·RAG·agent 구성.
58. **Haystack** — deepset, 유지형 저장소. [GitHub](https://github.com/deepset-ai/haystack). 검색/생성 pipeline과 평가.
59. **Semantic Kernel** — Microsoft, 유지형 저장소. [GitHub](https://github.com/microsoft/semantic-kernel). plugin/tool/agent orchestration.
60. **promptfoo** — promptfoo, 유지형 저장소. [GitHub](https://github.com/promptfoo/promptfoo). 프롬프트 회귀·provider 비교·red-team 테스트.
61. **OpenAI Evals** — OpenAI, 유지형 저장소. [GitHub](https://github.com/openai/evals). eval 예시와 레지스트리; API 최신 상태는 공식 문서를 우선.
62. **Ragas** — Exploding Gradients, 유지형 저장소. [GitHub](https://github.com/explodinggradients/ragas). RAG 평가 구현; 자동 점수는 사람 anchor로 보정.
63. **Phoenix** — Arize AI, 유지형 저장소. [GitHub](https://github.com/Arize-ai/phoenix). trace/observability/evaluation.
64. **Langfuse** — Langfuse, 유지형 저장소. [GitHub](https://github.com/langfuse/langfuse). prompt versioning, trace, dataset/eval 운영.
65. **Guardrails AI** — Guardrails AI, 유지형 저장소. [GitHub](https://github.com/guardrails-ai/guardrails). 입출력 validator와 schema; 보안 경계의 단독 대체재는 아님.

## 5. 고품질 2차 자료와 학습 자료

66. **The Prompt Report: A Systematic Survey of Prompting Techniques** — Schulhoff et al., 2024, arXiv:2406.06608. [원문](https://arxiv.org/abs/2406.06608). 대규모 분류/서베이. 기법 지도에 유용하나 개별 성능은 원 논문 확인.
67. **Prompt Engineering Guide** — DAIR.AI, 지속 갱신. [원문](https://www.promptingguide.ai/). 교육/커뮤니티 종합. 폭넓은 링크 허브이며 1차 근거로 재검증 필요.
68. **Anthropic Prompt Engineering Interactive Tutorial** — Anthropic, 유지형. [GitHub](https://github.com/anthropics/prompt-eng-interactive-tutorial). 공급자 공식 실습 자료.
69. **OpenAI Cookbook** — OpenAI, 유지형. [GitHub](https://github.com/openai/openai-cookbook). 공식 예제. API 변화 때문에 날짜와 최신 문서 교차확인.

## 출처 해석 주의

- 공급자 문서는 자사 모델/서비스의 **현재 동작과 권장법**에는 1차 출처지만, 독립 비교나 보편적 우월성의 증거는 아니다.
- arXiv는 영구 식별과 빠른 공개에는 유용하나 모두 동료평가된 것은 아니다. 게재처/버전을 병기했다.
- 벤치마크 수치는 데이터·모델·시점에 묶인다. 본 보고서는 서로 다른 논문의 절대 점수를 직접 순위화하지 않았다.
- 프레임워크 목록은 채택 권고가 아니라 구현 선택지다. 유지 상태는 변동성이 높다.
