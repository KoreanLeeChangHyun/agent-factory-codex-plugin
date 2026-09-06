# Inquiry request: 에이전틱 엔지니어링 공개 웹 종합 조사

## Human request

에이전틱 엔지니어링을 전부 조사해서 정리한다.

## 기준과 용어 경계

- 조사 기준일: 2026-08-28 (Asia/Seoul).
- "전부"는 웹 전체의 문자적 완전 열거가 아니라 공개 접근 가능한 핵심·권위·대표 근거를 범주별 검색 포화까지 체계적으로 조사한다는 뜻으로 해석한다. 누락 가능성과 비포화 영역을 명시한다.
- `agentic engineering`이 아직 단일 표준 정의가 아닐 수 있으므로 최소 세 용례를 분리해 검증한다.
  1. AI agents가 요구사항, 설계, 구현, 검증, 배포, 운영, 유지보수 등 엔지니어링 일을 수행하는 방식.
  2. 신뢰할 수 있는 agentic systems 자체를 설계·구축·평가·운영하는 engineering discipline.
  3. 인간·에이전트가 함께 일하도록 팀, 프로세스, 플랫폼, 통제, 경제 모델을 재설계하는 agent-native operating model.
- 앞선 `agentic coding` 조사보다 범위를 넓힌다. 코딩은 하위 영역으로 요약·연결하고, requirements/design/testing/DevOps/SRE/data/ML/security/product/physical engineering과 수명주기 전체를 다룬다. 다만 근거가 희박한 물리·하드웨어 영역은 과장하지 않는다.
- 일반적인 "AI agent" 전체 조사로 흩어지지 말고 engineering work와 engineering discipline에 직접 연결되는 근거를 우선한다.
- 기술 사실은 논문, 공식 문서, 표준, 공식 저장소, 공식 기술·보안 블로그를 우선한다. 시장/조직 사례는 신뢰도 높은 독립 연구와 공급자 사례를 구분한다.
- 검색 결과 페이지가 아닌 직접 원문 URL을 보존하며, 실제 원문을 열어 주장 지지 여부를 확인한다.
- 가격, 기능, 규제, 제품 상태, benchmark처럼 변동 가능한 사실에는 기준일과 출처를 붙인다.

## Research questions

1. `agentic engineering`이라는 용어는 누가 어떤 뜻으로 쓰며, 인접 개념(agentic coding, AI engineering, agent engineering, software engineering agents, autonomous engineering, agentic AI systems engineering)과 어떻게 다른가?
2. 2026-08-28까지의 역사와 기술적 전환점은 무엇인가? foundation models, tool use, ReAct, computer use, MCP/A2A/AGENTS.md/Agent Skills, coding agents, long-running/multi-agent systems, eval/observability를 포함한다.
3. 엔지니어링 수명주기 각 단계에서 agent가 하는 일, 입력·출력, Human gate, 검증 방법, 대표 도구/사례는 무엇인가?
   - discovery/requirements/product planning
   - architecture/design/modeling
   - implementation/coding
   - testing/formal verification/QA
   - code review/security/compliance
   - CI/CD/release/deployment
   - operations/SRE/incident response/FinOps
   - maintenance/migration/technical debt/documentation
4. agentic system을 공학적으로 만드는 참조 아키텍처는 무엇인가? model/router/planner, tools, memory/context, retrieval, state/workflow, identity, permissions, sandbox, human approval, evaluator, telemetry, policy, queues/retries/idempotency, multi-agent coordination, failure recovery를 포함한다.
5. 플랫폼·프로토콜·표준·프레임워크 생태계는 무엇인가? MCP, A2A, OpenAI/Anthropic/Google/Microsoft/AWS 계열 agent SDK·orchestration, LangGraph/AutoGen/Semantic Kernel 등 공식 근거가 있는 대표 프레임워크, OpenTelemetry/agent observability 관련 표준을 포함하되 마케팅 목록화는 피한다.
6. 평가 체계는 어떻게 설계해야 하는가? capability/task success, trajectory/tool correctness, reliability, security, latency, cost, human time, maintainability, production outcome, online/offline eval, adversarial/red-team, regression, benchmark limitations을 포함한다.
7. 안전·보안·거버넌스·법률/IP 위험과 통제는 무엇인가? prompt injection, excessive agency, identity/delegation, secrets/data exfiltration, supply chain, memory poisoning, insecure output, auditability, privacy, model/vendor risk, license/provenance, 책임·승인을 포함한다.
8. 조직/운영 모델은 어떻게 바뀌는가? 역할, 팀 topology, platform engineering, policy-as-code, repository instructions, skill/catalog governance, review burden, training, change management, procurement, build-vs-buy를 포함한다.
9. 경제성과 생산성의 실증 근거는 무엇인가? task-level speed, end-to-end delivery, defect/security/maintenance, expert vs novice, hidden review cost, inference/tool/infra cost, ROI 모델과 상반 결과를 구분한다.
10. 소프트웨어 밖의 엔지니어링(EDA/hardware, CAD/CAE, robotics, manufacturing, scientific/chemical/civil 등)에서 확인 가능한 실제 agentic 적용과 한계는 무엇인가?
11. 조직 성숙도 모델, 도입 로드맵, 참조 operating playbook, 역할별 학습 경로는 어떻게 구성할 수 있는가?
12. 근거가 강한 결론, 혼재된 결론, 아직 모르는 것과 향후 연구 공백은 무엇인가?

## 조사 시 반드시 비교할 구분

- deterministic workflow vs model-directed agent
- copilot/assistant vs delegated agent vs autonomous/long-running agent
- single-agent vs multi-agent
- local interactive vs remote asynchronous vs production-embedded agent
- agent framework/SDK vs end-user product vs protocol/standard vs evaluation/observability platform
- model capability vs harness/system capability vs organizational capability
- demo/benchmark success vs production outcome
- vendor case study vs independent empirical evidence
- software engineering applications vs agentic-systems engineering discipline

## Required output

Workspace: `/home/deus/workspace/agent-factory/plugin/.agent-factory/inquery/agentic-engineering-20260828/`

Create unrefined Markdown working material:

- `report.md`: 한국어 종합 보고서. 관찰된 사실, 분석, 가설/제안, 한계, Human-owned 결정을 구분하고 중요 주장 바로 옆에 직접 링크를 둔다.
- `sources.md`: 중복 제거한 주석형 출처 목록. 번호, 제목, 발행 주체/저자, 날짜/갱신성, 유형, 직접 URL, 접근일, 뒷받침하는 주장, 신뢰도와 한계를 기록한다.
- `search-log.md`: 검색어 묶음, 범주별 포화 판단, 원문 확인 방식, 접근 실패/불안정, 제외 범위, 모순 처리, 남을 수 있는 누락을 기록한다.

`report.md`에는 최소 다음을 포함한다.

- executive summary와 용어 taxonomy
- 에이전틱 코딩과 에이전틱 엔지니어링의 관계
- 2021–2026 중심 연대표와 이전 토대
- 전체 engineering lifecycle map
- 참조 아키텍처와 실행/제어 loop
- 제품·SDK·framework·protocol·standard 비교표
- 평가 프레임워크와 지표/벤치마크 비교
- 위험–통제–증거 매트릭스
- 조직 operating model과 RACI/승인 경계 예시
- 단계별 maturity model 및 30/60/90일 도입 로드맵(규범적 제안임을 표시)
- 비용/ROI 계산 프레임
- 소프트웨어 외 적용 현황
- 역할별 학습 로드맵
- anti-patterns와 실패 모드
- 근거가 강한 결론 / 혼재된 결론 / 아직 모르는 것
- 조사 한계와 가장 작은 유용한 후속 Inquiry

## Quality bar

- 핵심 범주마다 복수의 1차/공식 출처로 교차 확인하고, 공급자 효능 주장은 독립 근거와 분리한다.
- 제품/프레임워크의 전수 목록을 가장하지 말고 대표성 기준을 명시한다.
- 아직 확립되지 않은 용어 정의나 maturity model은 관찰된 사실이 아니라 분석/제안으로 표시한다.
- 수치에는 모집단, 과업, 비교군, 시점, 측정치와 한계를 붙인다.
- benchmark leaderboard 순위보다 평가 설계, contamination, budget, infra, reproducibility를 설명한다.
- 긴 원문 인용은 피하고 충실한 요약과 직접 링크를 사용한다.
- 기존 `.agent-factory/inquery/agentic-coding-20260828/`은 비정제 임시 참고자료로만 취급한다. 필요한 웹 주장에는 원 출처를 다시 연결하고, 기존 Inquiry를 정식 근거처럼 승격하지 않는다.
- 제품 변경, Specification/Project Skill 승격, 테스트/검증 명령 실행, Human-owned 제품 선택·위험 수용·배포 승인을 하지 않는다.
