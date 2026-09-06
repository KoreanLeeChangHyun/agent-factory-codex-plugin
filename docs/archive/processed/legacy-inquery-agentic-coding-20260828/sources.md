# 주석형 출처 목록

> 중복 제거된 직접 원문 URL. 접근일은 모두 2026-08-28 (Asia/Seoul). 날짜가 없는/계속 갱신되는 문서는 “지속 갱신”으로 표시했다. 신뢰도는 해당 주장에 대한 출처 적합성을 뜻하며 제품 효능의 독립 검증을 뜻하지 않는다.

## 정의·역사·구조

1. **Building effective agents** — Anthropic, 2024-12-19, 공식 기술 블로그. https://www.anthropic.com/engineering/building-effective-agents — workflow/agent 구분, tool loop, coding agent 적합성, 단순성·ACI·human review. **높음(정의/자사 설계); 한계:** 공급자 경험 기반.
2. **ReAct: Synergizing Reasoning and Acting in Language Models** — Yao et al., ICLR 2023, 논문. https://arxiv.org/abs/2210.03629 — reasoning/action 교차 loop. **높음; 한계:** coding 전용 연구 아님.
3. **Reflexion: Language Agents with Verbal Reinforcement Learning** — Shinn et al., NeurIPS 2023, 논문. https://arxiv.org/abs/2303.11366 — 언어 피드백과 episodic memory. **높음; 한계:** 당시 작은 coding benchmark 포함.
4. **Executable Code Actions Elicit Better LLM Agents (CodeAct)** — Wang et al., ICML 2024, 논문. https://arxiv.org/abs/2402.01030 — executable code action과 self-debug loop. **높음; 한계:** 실제 제품 운영 비교 아님.
5. **SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering** — Yang et al., 2024, 논문. https://arxiv.org/abs/2405.15793 — ACI가 repo 탐색·편집·test 성능에 미치는 영향. **높음; 한계:** 특정 모델/초기 SWE-bench.
6. **Introducing GitHub Copilot: your AI pair programmer** — GitHub, 2021-06-29(2022 갱신), 공식 발표. https://github.blog/news-insights/product-news/introducing-github-copilot-ai-pair-programmer/ — completion 중심 초기 역사. **높음(발표 사실); 한계:** 마케팅.
7. **Introducing the Model Context Protocol** — Anthropic, 2024-11-25, 공식 발표. https://www.anthropic.com/news/model-context-protocol — MCP 공개 시점·목적. **높음; 한계:** 보안 보증 아님.
8. **Model Context Protocol specification** — MCP project, 지속 갱신, 표준 원문. https://modelcontextprotocol.io/specification/2024-11-05/basic/index — protocol roles/transport. **높음; 한계:** 초기 revision 링크.
9. **AGENTS.md** — open format project, 지속 갱신. https://agents.md/ — repo-level agent instruction 관례와 지원 도구. **중상; 한계:** 공식 표준기구가 아닌 업계 관례/지원 목록 변동.

## 제품·공식 프로젝트

10. **Codex** — OpenAI, 지속 갱신, 공식 제품 페이지. https://openai.com/codex/ — 앱/IDE/CLI/cloud, 병렬 agents/skills. **높음(현행 기능); 한계:** 마케팅 사례·기능 변동.
11. **openai/codex** — OpenAI, 지속 갱신, 공식 저장소. https://github.com/openai/codex — CLI 소스·라이선스·설치. **높음; 한계:** cloud service 전체와 다름.
12. **Introducing the Codex app** — OpenAI, 2026-02-02(2026-03-04 갱신), 공식 발표. https://openai.com/index/introducing-the-codex-app/ — 병렬·장기 agent 방향과 Windows 갱신. **높음(발표); 한계:** 효능 주장은 공급자 자료.
13. **Running Codex safely at OpenAI** — OpenAI, 2026-05-08, 공식 security blog. https://openai.com/index/running-codex-safely/ — boundary, approval, telemetry. **높음(자사 통제); 한계:** 외부 조직에 그대로 일반화 불가.
14. **Claude Code setup / CLI reference** — Anthropic, 지속 갱신, 공식 문서. https://docs.anthropic.com/en/docs/claude-code/getting-started 및 https://docs.anthropic.com/en/docs/claude-code/cli-usage — 로컬 CLI, resume, permissions, tools. **높음; 한계:** 라이선스/서비스 조건 별도 확인.
15. **Claude Code best practices** — Anthropic, 2025-04-18, 공식 기술 블로그. https://www.anthropic.com/engineering/claude-code-best-practices — explore/plan/code/commit, context, subagent. **중상; 한계:** 공급자 권고, 독립 실험 아님.
16. **GitHub Copilot concepts / third-party coding agents** — GitHub, 지속 갱신, 공식 문서. https://docs.github.com/en/copilot/concepts 및 https://docs.github.com/en/copilot/concepts/agents/about-third-party-coding-agents — cloud agent, agents, security scans, 비용 단위. **높음; 한계:** preview/plan 변동.
17. **GitHub Agentic Workflows** — GitHub, 지속 갱신, 공식 문서. https://docs.github.com/en/copilot/concepts/agents/about-github-agentic-workflows — Markdown workflow, read-only default, safe outputs, container. **높음; 한계:** public preview.
18. **Cursor Agent / Background Agents / Security** — Cursor, 지속 갱신, 공식 문서. https://cursor.com/docs/agent/overview ; https://docs.cursor.com/background-agent ; https://prod.cursor.com/docs/agent/security — 모델·도구·instruction, remote branch, auto terminal, prompt injection 경고. **높음(제품 동작); 한계:** 이전 URL/페이지가 수시로 이동.
19. **Windsurf Cascade overview** — Windsurf, 지속 갱신, 공식 문서. https://docs.windsurf.com/windsurf/cascade/cascade — Code/Chat, tool call, planning, checkpoints, MCP. **높음; 한계:** 검색 시 비영어 locale만 안정적으로 노출되기도 함.
20. **Introducing Devin** — Cognition, 지속 갱신, 공식 문서. https://docs.devin.ai/get-started/devin-intro — autonomous workspace, write/run/test. **높음(기능); 한계:** “3시간 과제”는 공급자 경험칙.
21. **Build with Replit Agent** — Replit, 지속 갱신, 공식 문서. https://docs.replit.com/learn/build-with-agent — plan, context, review/test, checkpoints. **높음; 한계:** 모드·요금 빠른 변동.
22. **Amazon Q Developer end-of-support / Kiro transition** — AWS, 2026-04-30, 공식 블로그. https://aws.amazon.com/blogs/devops/amazon-q-developer-end-of-support-announcement/ — Kiro 기능, Q IDE 신규가입/지원 종료 일정. **높음; 한계:** 서비스 일정은 재확인 필요.
23. **Reinventing Amazon Q Developer agent** — AWS, 2024, 공식 기술 블로그. https://aws.amazon.com/blogs/devops/reinventing-the-amazon-q-developer-agent-for-software-development/ — textcode ACI, explore/action/evaluate loop. **높음(설계 설명); 한계:** 제품 효능의 독립 근거 아님.
24. **Gemini CLI repository and transition discussions** — Google, 지속 갱신/2026-05-19·06-18, 공식 저장소/announcement. https://github.com/google-gemini/gemini-cli ; https://github.com/google-gemini/gemini-cli/discussions/27274 ; https://github.com/google-gemini/gemini-cli/discussions/28017 — Apache-2.0, built-in tools, Antigravity transition, 개인 계정 종료. **높음; 한계:** repo는 존속하나 서비스 경로가 사용자군별 상이.
25. **OpenHands repository / paper** — OpenHands community, 지속 갱신; Wang et al., ICLR 2025. https://github.com/OpenHands/OpenHands ; https://arxiv.org/abs/2407.16741 — SDK/CLI/cloud, terminal/browser, MIT core와 enterprise 예외. **높음; 한계:** 최신 repo와 논문 버전 차이.
26. **Aider repository** — Aider-AI, 지속 갱신, 공식 저장소. https://github.com/Aider-AI/aider — repo map, git, lint/test, Apache-2.0. **높음; 한계:** 릴리스/유지보수 상태를 도입 시 재확인.
27. **Cline repository** — Cline, 지속 갱신, 공식 저장소. https://github.com/cline/cline — IDE/CLI/SDK/Kanban, tools, Apache-2.0 및 일부 비공개 범위. **높음; 한계:** README 기능이 매우 빠르게 변함.
28. **goose documentation** — Block/AAIF, 지속 갱신. https://block.github.io/goose/ — local desktop/CLI/API, MCP, Apache-2.0. **높음; 한계:** 일반 목적 agent.
29. **Continue repository** — Continue Dev, 2026 상태, 공식 저장소. https://github.com/continuedev/continue — Apache-2.0, CLI/IDE; read-only/비활성 유지보수 공지. **높음; 한계:** 역사적 프로젝트로 분류해야 함.

## 벤치마크·평가

30. **SWE-bench: Can Language Models Resolve Real-World GitHub Issues?** — Jimenez et al., ICLR 2024, 논문. https://arxiv.org/abs/2310.06770 — 12 Python repos의 issue/patch test. **높음; 한계:** 공개·오염·언어 편향.
31. **Introducing SWE-bench Verified** — OpenAI, 2024-08-13, 공식 annotation 보고. https://openai.com/index/introducing-swe-bench-verified/ — human-validated 500 subset와 infeasible 제거. **높음; 한계:** OpenAI가 후일 신호 저하 주장.
32. **SWE-bench official leaderboard** — SWE-bench team, 지속 갱신. https://www.swebench.com/ — 동일 mini-SWE-agent view와 variants. **중상; 한계:** 순위/제출 조건 수시 변동.
33. **SWE-bench Multilingual** — SWE-bench team, 지속 갱신. https://www.swebench.com/multilingual.html — 9개 언어, 42 repos, 300 tasks. **높음; 한계:** 작은 curated set.
34. **SWE-bench Goes Live!** — 연구 논문, 2025. https://arxiv.org/abs/2505.23419 — 1,319 fresh executable tasks, temporal contamination 대응. **높음; 한계:** 유지/환경 drift.
35. **SWE-Bench Pro** — Scale AI research, 2025-09-19. https://labs.scale.com/papers/swe_bench_pro — 1,865 tasks, 41 public/held-out/commercial repos, long horizon. **중상; 한계:** 일부 비공개로 완전 재현 불가, 상업 운영자.
36. **Separating signal from noise in coding evaluations** — OpenAI, 2026-07, 공식 분석. https://openai.com/index/separating-signal-from-noise-coding-evaluations/ — SWE-bench Verified/Pro의 설계·오염 비판. **중상; 한계:** benchmark/model 경쟁 이해관계, 독립 검증 필요.
37. **SWE-Lancer** — Miserendino et al./OpenAI, 2025-02-18, 논문/공식 소개. https://openai.com/index/swe-lancer/ — 1,488 Upwork IC/manager tasks, $1M payouts, E2E tests. **높음; 한계:** 가치·표본 대표성, public split.
38. **Terminal-Bench announcement / 2.1** — Terminal-Bench team, 2025-05-19/2026-05-06. https://www.tbench.ai/news/announcement ; https://www.tbench.ai/news/terminal-bench-2-1 — Docker CLI tasks, harness, dependency 오류 수정. **높음; 한계:** leaderboard integrity·infra drift.
39. **Terminal-Bench Challenges** — Terminal-Bench team, 2026-06-18. https://www.tbench.ai/news/terminal-bench-challenges — 장기 단일 대형 프로젝트. **높음; 한계:** 작은 표본·높은 비용.
40. **RE-Bench** — METR, 2024, official repository/paper. https://github.com/METR/RE-Bench — 7개 8시간 AI R&D tasks, human experts, MIT harness. **높음; 한계:** 일반 SWE가 아닌 위험 관련 R&D.
41. **Quantifying infrastructure noise in agentic coding evals** — Anthropic, 2026, 공식 기술 분석. https://www.anthropic.com/engineering/infrastructure-noise — 최대 6% pod errors, resource/time confound. **중상; 한계:** 자사 실험 환경.

## 보안·거버넌스

42. **AI Agent Security Cheat Sheet** — OWASP, 지속 갱신. https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html — direct/indirect injection, tool abuse, memory, identity, testing controls. **높음(실무 지침); 한계:** 표준 준수 인증 아님.
43. **Secure Coding with AI Cheat Sheet** — OWASP, 지속 갱신. https://cheatsheetseries.owasp.org/cheatsheets/Secure_Coding_with_AI_Cheat_Sheet.html — coding agent용 secure workflow. **높음; 한계:** 2026 제품 예시는 변동.
44. **LLM06:2025 Excessive Agency** — OWASP GenAI, 2025, risk taxonomy. https://genai.owasp.org/llmrisk/llm062025-excessive-agency/ — 기능·권한·자율성 최소화. **높음; 한계:** coding 전용 아님.
45. **NIST SP 800-218A** — NIST, 2024-07-26, 정부 표준 가이드. https://www.nist.gov/publications/secure-software-development-practices-generative-ai-and-dual-use-foundation-models-ssdf — GenAI/dual-use model SSDF community profile. **높음; 한계:** SP 800-218과 함께 사용, 구체 제품 설정 아님.
46. **How we contain Claude across products** — Anthropic, 2026-05-25, 공식 engineering/security blog. https://www.anthropic.com/engineering/how-we-contain-claude — ephemeral container, HITL sandbox, blast radius 논의. **중상; 한계:** 자사 architecture와 incident 서술.

## 생산성·사용 연구

47. **The Impact of AI on Developer Productivity: Evidence from GitHub Copilot** — Peng et al., 2023, controlled experiment. https://arxiv.org/abs/2302.06590 — 제한된 과제에서 55.8% 빠른 완료. **높음(내적 타당성); 한계:** 단일 과제·completion 세대·전체 SDLC 아님.
48. **Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity** — METR, 2025, RCT. https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf — 16명/246 tasks, 19% slowdown. **높음(설계); 한계:** 작은 표본·특정 도구 시점·숙련 repo.
49. **We are Changing our Developer Productivity Experiment Design** — METR, 2026-02-24, 연구 업데이트. https://metr.org/blog/2026-02-24-uplift-update/ — 후속 더 큰 pool, early-study CI와 설계 변화. **높음(자기 연구 상태); 한계:** 최종 후속 결과가 아닌 중간 업데이트.
50. **DORA 2024 / Impact of Generative AI in Software Development** — Google Cloud DORA, 2024, 대규모 설문·통계 보고. https://dora.dev/research/2024/dora-report/ ; https://dora.dev/ai/gen-ai-report/report/ — 개인 flow/만족/생산성과 delivery 안정성/throughput의 상반 연관. **중상; 한계:** 관찰 연구, 인과·연도 간 비교 주의.
51. **Agentic coding and persistent returns to expertise** — Anthropic, 2026-06-16, 자사 사용 로그 연구. https://www.anthropic.com/research/claude-code-expertise — 약 40만 sessions, planning/execution 분업과 domain expertise. **중상; 한계:** 공급자 데이터·privacy-preserving 집계, 외부 재현 제한.
52. **Building a C compiler with a team of parallel Claudes** — Anthropic/Nicholas Carlini, 2026-02-05, 사례 연구. https://www.anthropic.com/engineering/building-c-compiler — 16 agents, 약 2,000 sessions, $20k, 100k-line compiler. **중간; 한계:** 단일 고비용 stress test, 대조군 없음.
