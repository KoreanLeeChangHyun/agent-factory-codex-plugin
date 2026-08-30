# 검색 로그

> 조사 기준일/접근일: 2026-08-28 (Asia/Seoul). 비정제 Inquiry 기록이며 검색엔진의 완전성이나 미래 재현을 보장하지 않는다.

## 방법

1. 요청서의 12개 research question과 필수 구분을 검색 축으로 만들었다.
2. 용어 발견에는 일반 검색을 사용하고, 기술 주장은 논문·공식 specification/docs/repository/security/engineering blog 원문을 직접 열어 확인했다.
3. 제품 기능, 날짜, 표준 revision, benchmark 구성은 기준일 스냅샷으로 취급했다. 검색 결과 페이지 URL은 출처로 남기지 않았다.
4. 기존 `.agent-factory/inquery/agentic-coding-20260828/`은 용어·후보 URL을 찾는 임시 단서로만 읽었다. 보고서의 중요 주장에는 웹 원문을 다시 연결했다.
5. 공급자 architecture/case와 independent empirical evidence를 별도 표기했다. 긴 인용 대신 요약했다.

## 검색어 묶음과 포화 판단

| 범주 | 대표 검색어 | 확인한 원문군 | 포화 판단 |
|---|---|---|---|
| 용어 | `"agentic engineering" definition`, `agent engineering discipline`, `autonomous engineering AI agents` | IBM, ACM/ICSE workshop, 독립 실무 용례 | **부분 포화.** 세 용례 반복 확인; 표준 정의는 없음 |
| 역사/agent loop | `ReAct Reflexion tool use`, `software engineering agents history`, `computer use agent` | ReAct, Reflexion, SWE-bench/SWE-agent, vendor history | **포화.** 주요 2021–2025 전환점 반복 |
| SDLC lifecycle | `agentic SDLC requirements design testing review deployment`, `agentic workflows GitHub` | GitHub, Google/DORA/SRE, AWS docs | **부분 포화.** coding/ops 강함, requirements/product 독립 연구 약함 |
| architecture | `production agent architecture sandbox checkpoint idempotency identity`, `long running agents` | Anthropic/OpenAI/Microsoft/LangGraph/MCP | **포화.** 공통 component와 control pattern 반복 |
| protocols | `MCP spec authorization`, `A2A protocol 1.0`, `AGENTS.md`, `Agent Skills spec` | 각 공식 spec/project | **포화.** 최신 직접 원문 확인; adoption 수치는 제외 |
| frameworks | `OpenAI Agents SDK`, `Microsoft Agent Framework`, `AWS Strands AgentCore`, `LangGraph durable execution` | 공식 docs/repos | **대표 포화.** 전수 목록은 의도적으로 하지 않음 |
| observability/evals | `agent eval trajectory grader`, `OpenTelemetry AI agent semantic conventions` | Anthropic eval guide, OpenAI Evals, OTel | **부분 포화.** 관례는 진화 중 |
| benchmark | `SWE-bench Live`, `SWE-Lancer`, `Terminal-Bench`, `RE-Bench`, `METR time horizon` | papers/official benchmark sites | **포화.** 순위 대신 설계·오염·infra 한계 중심 |
| security/governance | `NIST AI agent security 2026`, `OWASP agentic threats`, `MCP token passthrough` | NIST CAISI, OWASP, MCP auth | **포화.** 주요 taxonomy 반복; 법률은 관할별 비포화 |
| organization | `DORA AI capabilities model`, `agent-native operating model platform engineering` | DORA 2024/2025, vendor operations cases | **부분 포화.** 장기 조직 성과와 RACI는 대부분 규범적 |
| productivity/ROI | `developer productivity AI RCT`, `METR experienced developers`, `DORA generative AI` | Peng RCT, METR RCT, DORA | **부분 포화.** 상반 근거 확인; agentic full-SDLC 장기 RCT 부족 |
| SRE/DevOps | `agentic SRE incident response official`, `AI DevOps agent` | Google SRE, AWS, GitHub security | **부분 포화.** 실제 내부 사례는 있으나 independent outcomes 부족 |
| physical engineering | `agentic AI EDA CAD CAE`, `self-driving laboratory agent`, `robotic chemist` | DeepMind, Cadence, Matter/Nature/JACS, NVIDIA | **비포화.** EDA/chemistry는 근거, civil/mechanical/field deployment는 희박 |

## 원문 확인과 갱신성

- MCP는 2025-06-18 architecture/authorization revision을 사용했다. 검색에서 초기 2024 spec도 나타났지만 current security 설명에 구 revision을 혼합하지 않았다.
- A2A는 repository의 latest released 1.0 specification을 확인했다. 최초 Google 발표와 Linux Foundation/재단 governance의 세부 연혁은 보고서 핵심 주장에 필요하지 않아 과도하게 열거하지 않았다.
- OpenAI, Microsoft, AWS, Google, GitHub 제품 문서는 지속 갱신되므로 기능을 2026-08-28 스냅샷으로만 기록했다. 가격은 비교하지 않았다.
- ACM DOI, arXiv, NIST publication, peer-reviewed journal DOI/abstract를 직접 URL로 보존했다.
- OpenTelemetry agent semantic convention은 완성된 ISO식 표준으로 서술하지 않고 evolving convention으로 제한했다.

## 접근 실패·불안정

- 일부 journal은 유료 본문이어서 공개 abstract/metadata와 검색 가능한 요약만 확인했다. 이 경우 `sources.md`에 제한을 기록했다.
- vendor docs의 locale·URL redirect와 빠른 갱신이 있었고, stable official landing/spec URL을 우선했다.
- 2026-08 말에 공개된 일부 자료는 검색 색인 날짜와 발행일이 어긋날 수 있어 날짜가 핵심이 아닌 주장에만 사용했다.
- private enterprise eval, incident, total cost, contract/data terms는 공개되지 않아 검증할 수 없었다.

## 제외 범위

- “top 100 agents/tools”식 SEO 목록, affiliate 비교, 검색 결과 snippet만 있는 주장은 제외했다.
- 모든 chatbot/RPA/LLM application을 agentic engineering으로 포함하지 않았다. engineering work 또는 agentic-systems engineering에 직접 연결돼야 포함했다.
- benchmark leaderboard의 최신 순위·제품 가격은 변동성이 크고 요청의 핵심이 아니어서 제외했다.
- vendor의 `10x`, `fully autonomous`, `first` 같은 표현은 독립 검증 없이 사실로 채택하지 않았다.
- 일반 로봇·전통 최적화·BPM을 LLM agent와 동일시하지 않았다.
- 관할별 법률 자문, procurement 결정, 제품 선정, risk acceptance는 Inquiry 권한 밖이다.

## 모순 처리

- Copilot 55.8% speedup과 METR 19% slowdown을 승패로 합치지 않았다. 모집단(일반 전문개발자 vs 자기 repo 숙련 OSS 개발자), task(제한 신규 과제 vs 실제 issue), 도구세대, review 범위가 달라 외적 타당성의 경계로 해석했다.
- workflow와 agent라는 말이 공급자마다 넓게 쓰여 Anthropic의 control-path 구분을 운영 정의로 사용하되 보편 표준으로 주장하지 않았다.
- `agentic engineering`은 IBM의 human-orchestrated SDLC 용례와 ACM의 agentic-system discipline 용례가 다르므로 세 용례 taxonomy로 병치했다.
- physical 영역의 vendor autonomy 주장은 peer-reviewed self-driving lab 연구의 좁은 task·bespoke integration 한계와 함께 제시했다.

## 남을 수 있는 누락

- 비영어권 연구, 특허, 유료 analyst 보고서, 사내 deployment failure, 정부/국방 자료.
- requirements engineering, formal methods, compliance agent의 독립 production 연구.
- civil/mechanical/aerospace/field robotics에서의 장기 안전·사건 데이터.
- 2026-08-28 직전 표준/제품 변경과 이후 변경.
- A2A/MCP/Skills client 간 실제 conformance·security 비교와 agent identity 법제.

## 포화 결론

software coding/architecture/protocol/security/eval 범주는 동일한 핵심 pattern과 1차 출처가 반복돼 대표 근거 수준에서 포화했다. requirements/product/organization economics와 physical engineering은 독립·장기·실패 데이터가 부족해 비포화다. 따라서 추가 일반 웹 검색보다 특정 조직의 내부 task/eval/incident 데이터를 대상으로 한 후속 Inquiry가 더 높은 정보가치를 가진다.
