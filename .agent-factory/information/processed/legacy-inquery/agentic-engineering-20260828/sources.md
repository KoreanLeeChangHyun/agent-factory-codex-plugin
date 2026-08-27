# 주석형 출처 목록

> 중복 제거한 직접 원문. 접근일은 모두 2026-08-28 (Asia/Seoul). 날짜 없는 공식 문서는 “지속 갱신”으로 표기한다. 신뢰도는 해당 주장에 대한 적합성이며 공급자 효능의 독립 검증을 뜻하지 않는다.

## 정의·역사·기초 연구

1. **What is Agentic Engineering?** — IBM / Anna Gutowska, 2026-02-27, 공식 해설. https://www.ibm.com/think/topics/agentic-engineering — 전문 엔지니어가 SDLC agent를 오케스트레이션·감독한다는 용례. **중상; 한계:** 업계 해설, 표준 정의 아님.
2. **Proceedings of the 1st International Workshop on Agentic Engineering (AGENT 2026)** — ACM/ICSE, 2026, 학술 workshop. https://doi.org/10.1145/3786167 — goal-directed autonomy system의 설계·개발·운영 discipline 용례. **높음(학술 범위); 한계:** 신생 workshop, 합의 표준 아님.
3. **Building effective agents** — Anthropic, 2024-12-19, 공식 engineering blog. https://www.anthropic.com/engineering/building-effective-agents — workflow/agent 구분, augmented LLM, routing/parallel/evaluator-agent pattern, simplicity·ACI. **높음(설계 설명); 한계:** 공급자 경험.
4. **ReAct: Synergizing Reasoning and Acting in Language Models** — Yao et al., ICLR 2023. https://arxiv.org/abs/2210.03629 — reasoning/action loop. **높음; 한계:** 최신 production agent 직접 연구 아님.
5. **Reflexion** — Shinn et al., NeurIPS 2023. https://arxiv.org/abs/2303.11366 — verbal feedback와 episodic memory. **높음; 한계:** 작은 초기 benchmark.
6. **SWE-bench** — Jimenez et al., ICLR 2024. https://arxiv.org/abs/2310.06770 — 실제 GitHub issue→patch test. **높음; 한계:** 공개 오염·repo/language 편향.
7. **SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering** — Yang et al., 2024. https://arxiv.org/abs/2405.15793 — ACI가 agent 성능을 좌우. **높음; 한계:** 특정 초기 model/benchmark.
8. **Introducing GitHub Copilot** — GitHub, 2021-06-29, 공식 발표. https://github.blog/news-insights/product-news/introducing-github-copilot-ai-pair-programmer/ — completion/pair programmer 역사. **높음(발표 사실); 한계:** 마케팅.

## 프로토콜·지침·관측 표준

9. **MCP Architecture** — Model Context Protocol project, 2025-06-18 revision. https://modelcontextprotocol.io/specification/2025-06-18/architecture — host/client/server와 security boundary. **높음(규범 원문); 한계:** 구현 안전은 별도.
10. **MCP Authorization** — MCP project, 2025-06-18 revision. https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization — OAuth 기반 resource/audience, token passthrough 금지. **높음; 한계:** HTTP auth 범위.
11. **A2A Protocol Specification 1.0** — A2A project/Linux Foundation, 지속 갱신. https://github.com/a2aproject/A2A/blob/main/docs/specification.md — AgentCard, task/message/artifact, async/stream/HITL. **높음; 한계:** 상호 trust/quality 보증 아님.
12. **A2A Project** — Linux Foundation project, 지속 갱신. https://github.com/a2aproject — Google 기여, SDK/TCK와 governance. **높음(프로젝트 상태); 한계:** adoption은 변동.
13. **AGENTS.md** — Agentic AI Foundation, 지속 갱신. https://agents.md/ — 저장소별 agent 지침 관례. **중상; 한계:** 자유형 Markdown, 실행 의미가 client별로 다름.
14. **Agent Skills specification** — Agent Skills project, 지속 갱신. https://agentskills.io/specification — `SKILL.md`, scripts/references/assets, progressive disclosure. **높음(형식); 한계:** allowed-tools는 experimental이고 client reliability 변동.
15. **AI Agent Observability—Evolving Standards** — OpenTelemetry, 2025, 공식 blog. https://opentelemetry.io/blog/2025/ai-agent-observability/ — GenAI/agent semantic convention 방향. **중상; 한계:** evolving draft/implementation 차이.

## SDK·framework·production architecture

16. **OpenAI developer quickstart: Build agents** — OpenAI, 지속 갱신, 공식 docs. https://platform.openai.com/docs/quickstart/make-your-first-api-request — Agents SDK, tools/handoffs. **높음(기능); 한계:** 제품 변화.
17. **The next evolution of the Agents SDK** — OpenAI, 2026-04-15, 공식 발표. https://openai.com/index/the-next-evolution-of-the-agents-sdk/ — controlled workspace, sandbox, snapshot/rehydration. **높음(발표); 한계:** 효능은 공급자 주장.
18. **Demystifying evals for AI agents** — Anthropic, 2026-01-09, 공식 engineering guide. https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents — task/trial/grader, transcript/outcome eval. **중상; 한계:** 공급자 실무 지침.
19. **Microsoft Agent Framework docs** — Microsoft, 지속 갱신. https://learn.microsoft.com/en-gb/agent-framework/ — workflow, memory, HITL, checkpoint, hosting, AutoGen/SK migration. **높음(기능); 한계:** version/preview 상태 확인 필요.
20. **LangGraph overview** — LangChain, 지속 갱신. https://langchain-ai.github.io/langgraph/index.html — stateful long-running orchestration, durable execution/HITL. **높음(기능); 한계:** vendor docs.
21. **Strands Agents examples/docs** — AWS/Strands, 지속 갱신. https://strandsagents.com/docs/examples/ — model/tool/multi-agent와 AgentCore integration. **높음(기능); 한계:** production outcome 아님.
22. **OpenHands repository/paper** — OpenHands, 지속 갱신. https://github.com/OpenHands/OpenHands ; https://arxiv.org/abs/2407.16741 — software development agent platform/sandbox. **높음; 한계:** repo 최신판과 논문 차이.
23. **GitHub Agentic Workflows security architecture** — GitHub, 2026, 공식 security/engineering blog. https://github.blog/ai-and-ml/generative-ai/under-the-hood-security-architecture-of-github-agentic-workflows/ — substrate/config/planning layer, secret/exfil threat. **중상; 한계:** 자사 제품.
24. **Automate repository tasks with GitHub Agentic Workflows** — GitHub, 2026, 공식 blog. https://github.blog/ai-and-ml/automate-repository-tasks-with-github-agentic-workflows/ — triage/docs/quality, safe outputs와 explicit write approval. **중상; 한계:** preview 기능.
25. **AI in SRE: How Google is Engineering the Future of Reliable Operations** — Google SRE, 2026, 공식 기술 논문/글. https://sre.google/resources/practices-and-processes/ai-engineering-reliable-operations/ — autonomy L0–L4, no ambient access, risk engine, dry-run, progressive authorization, kill switch, eval data pipeline. **중상; 한계:** 단일 공급자 내부 사례, 일부 목표 수치.
26. **AWS DevOps Agent overview** — AWS, 지속 갱신. https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html — release readiness, incident investigation, SRE tasks. **높음(제품 기능); 한계:** 효능 독립 검증 아님.

## 평가·생산성·조직

27. **OpenAI Evals API** — OpenAI, 지속 갱신. https://platform.openai.com/docs/api-reference/evals — dataset/config/grader/run 구조. **높음(기능); 한계:** platform-specific.
28. **SWE-bench Verified** — OpenAI, 2024-08-13. https://openai.com/index/introducing-swe-bench-verified/ — human-validated 500 subset. **중상; 한계:** 공급자가 later signal degradation을 지적, public contamination.
29. **SWE-Lancer** — OpenAI et al., 2025-02-18. https://openai.com/index/swe-lancer/ — 1,488 freelance IC/manager tasks와 경제적 가치. **높음(설계); 한계:** 한 시장/과거 projects.
30. **Terminal-Bench** — Terminal-Bench team, 2025. https://www.tbench.ai/news/announcement — container terminal task/harness. **중상; 한계:** infra drift·budget 영향.
31. **RE-Bench** — METR, 2024, repository/paper. https://github.com/METR/RE-Bench — 7개 8시간 ML R&D tasks와 human expert. **높음; 한계:** 작은 수와 AI R&D 편향.
32. **The Impact of AI on Developer Productivity** — Peng et al., 2023, RCT. https://arxiv.org/abs/2302.06590 — 95명 제한 JS task에서 55.8% faster. **높음(내적 타당성); 한계:** completion 도구·단일 task.
33. **Early-2025 AI and Experienced OSS Developer Productivity** — METR, 2025, RCT. https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf — 16명/246 tasks, 19% slowdown. **높음(설계); 한계:** 작은 표본·숙련 repo·특정 도구 세대.
34. **DORA AI Capabilities Model** — Google Cloud DORA, 2025-09-23, 연구 요약. https://cloud.google.com/blog/products/ai-machine-learning/introducing-doras-inaugural-ai-capabilities-model — policy, data, context, batch, user focus, VCS, internal platform. **중상; 한계:** 관찰연구/공급자 발행.
35. **Impact of Generative AI in Software Development** — DORA, 2025. https://dora.dev/ai/gen-ai-report/report/ — 개인·팀·delivery 상관과 조직 practice. **중상; 한계:** 인과 실험 아님.

## 보안·거버넌스

36. **LLM06:2025 Excessive Agency** — OWASP GenAI, 2025. https://genai.owasp.org/llmrisk/llm062025-excessive-agency/ — excessive functionality/permission/autonomy와 injection 사례. **높음(위험 taxonomy); 한계:** compliance 표준 아님.
37. **AI Agent Security Cheat Sheet** — OWASP, 지속 갱신. https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html — injection, tool, memory, identity 통제. **높음(실무 지침); 한계:** 제품별 구현 필요.
38. **Agentic AI Threats and Mitigations** — OWASP, 2025-02-17. https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/ — agent threat-model reference. **높음; 한계:** evolving taxonomy.
39. **Summary Analysis of Responses on AI Agent Security** — NIST CAISI, 2026-05-18. https://www.nist.gov/publications/summary-analysis-responses-request-information-regarding-security-considerations-ai — novel threats, 기존 cyber practice 조정, 표준 필요성 합의. **높음(정부 종합); 한계:** RFI 응답의 요약, 규범 최종안 아님.
40. **NIST AI Agent Standards Initiative** — NIST, 2026, 공식 initiative. https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative — interoperability, identity/authorization, security eval 연구. **높음(상태); 한계:** 진행 중.
41. **NIST SP 800-218A** — NIST, 2024-07-26. https://www.nist.gov/publications/secure-software-development-practices-generative-ai-and-dual-use-foundation-models-ssdf — GenAI secure development SSDF profile. **높음; 한계:** agent-specific 구현서는 아님.

## 비소프트웨어 공학

42. **AlphaEvolve** — Google DeepMind, 2025-05-14, 공식 연구 소개. https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/ — automated evaluator+evolution, algorithm/chip/data-center use. **중상; 한계:** 자사 결과, 평가 가능한 문제에 편중.
43. **Cadence fully autonomous virtual engineer announcement** — Cadence, 2026-06-01, press release. https://newsroom.cadence.com/press-releases/press-release-details/2026/Cadence-Unveils-Industrys-First-Fully-Autonomous-Virtual-Engineer-for-Chip-Design-06-01-2026/default.aspx — EDA super agents/AgentStack. **중간; 한계:** vendor announcement, “first/fully” 독립 검증 부족.
44. **Autonomous chemistry: self-driving labs review** — Matter, 2024. https://www.sciencedirect.com/science/article/pii/S2590238524003229 — hardware/coordinator/AI agent 구조와 적용. **높음(동료검토 review); 한계:** 유료 본문 접근·분야 이질성.
45. **Autonomous mobile robots for exploratory synthetic chemistry** — Nature, 2024. https://doi.org/10.1038/s41586-024-08173-7 — 실제 mobile robot synthesis workflow와 제한. **높음; 한계:** 특정 실험실·화학 범위.
46. **A Multiagent-Driven Robotic AI Chemist** — JACS, 2025. https://pubs.acs.org/doi/abs/10.1021/jacs.4c17738 — agent workflow와 robotic chemistry task. **높음(동료검토); 한계:** abstract/지원자료 중심 접근, 일반화 제한.
47. **NVIDIA AI in Manufacturing** — NVIDIA, 지속 갱신. https://www.nvidia.com/en-us/industries/manufacturing/ — digital twin, simulation, robotics, engineering workflow 사례. **중간; 한계:** vendor/partner marketing, 독립 outcome 부족.
48. **Siemens legacy modernization with agentic workflows** — Google Cloud/Siemens, 2026-06-16. https://cloud.google.com/blog/products/ai-machine-learning/how-siemens-sliced-the-elephant-modernizing-legacy-code-with-agentic-workflows/ — knowledge graph 기반 industrial software migration pilot. **중간; 한계:** 공급자 공동 사례, 수치/대조군 제한.
