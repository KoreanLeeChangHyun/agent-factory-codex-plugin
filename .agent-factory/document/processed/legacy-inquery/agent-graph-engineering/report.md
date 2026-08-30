# Agentic Graph Engineering 조사 보고서

> 조사 기준일: 2026-08-28  
> 범위: AI 에이전트/에이전틱 소프트웨어의 실행·조직 그래프. 그래프 DB, GNN, 지식 그래프, GraphRAG는 비교를 위한 경계 밖이다.  
> 상태 표기: **[확인]** 원문/공식 문서에서 관찰, **[저자 주장]** survey가 붙인 해석, **[분석]** 본 Inquiry의 비교·권고, **[전망]** 아직 검증되지 않은 예상.

## 핵심 요약 (10문장)

1. **[확인]** Feng et al.은 Graph Engineering을 과업, 지능형 구성요소, 런타임 상태 사이의 관계를 명시적 그래프로 외재화해 시스템 수준의 조직·조정·감시·복구·최적화를 수행하는 구조 중심 공학 기반으로 정의한다([arXiv:2608.21156](https://arxiv.org/abs/2608.21156)).
2. **[분석]** 여기서 graph는 지식 그래프가 아니라 여러 실행 관점—work/task, agent/capability/team/communication, state/evidence—을 연결한 운영 모델이며, 실제 런타임은 이 관점들을 하나의 거대 그래프로 물리적으로 저장할 필요가 없다.
3. **[확인]** 논문의 핵심 taxonomy는 `Task Organization → Agent Coordination → Runtime State Management`, 그리고 실행 경험을 다음 실행의 구조 변경으로 연결하는 `System Evolution`이다.
4. **[분석]** Loop Engineering은 한 에이전트가 관찰–계획–행동–검증–중단을 반복해 수렴하는 방법이고, Graph Engineering은 여러 루프·도구·사람·상태의 의존성, 병렬성, 소유권, 합류, 실패 경계를 설계하므로 대체가 아니라 포함 관계다.
5. **[확인]** 이 용어의 2026년 유행은 적어도 7월 18일 Peter Steinberger의 “loops or graphs” 게시물로 증폭됐지만 그 문장에는 “Graph Engineering”이라는 명칭도 정의도 없었고, 8월 21일 survey는 흩어진 선행 연구를 사후적으로 하나의 연구 서사에 묶었다.
6. **[분석]** DAG, Petri net, statechart, dataflow, BPMN, actor, blackboard, HTN, 분산 스케줄러가 이미 핵심 실행 의미론을 제공하므로 완전히 새 계산 모델은 아니며, 신규성은 LLM 노드의 비결정성·동적 역할/토폴로지·증거/권한/비용을 함께 다루는 통합 문제 설정과 vocabulary에 있다.
7. **[확인]** LangGraph, AutoGen GraphFlow, CrewAI Flows와 OpenAI Agents SDK는 이미 라우팅, 순환, 병렬/분기, 상태, handoff/guardrail/trace의 상당 부분을 구현하며, Temporal/Airflow/Prefect/Dagster는 내구 실행·재시도·스케줄링의 더 성숙한 기반을 제공한다.
8. **[확인]** 공개 연구는 workflow/topology 최적화, 동적 통신, 상태 트랜잭션, 복구를 각각 보이지만, 동일 예산·동일 모델에서 전체 graph discipline의 인과적 이득이나 지속적 self-evolution을 입증한 통합 benchmark는 아직 없다.
9. **[분석]** 실무 최소선은 typed node/edge, 단일 권위 상태 저장소, immutable artifact/evidence reference, 명시적 join/termination/budget, idempotency, checkpoint, 독립 verifier, human approval gate이지 “여러 에이전트” 자체가 아니다.
10. **[전망]** 향후 6–18개월에는 graph schema/trace 표준화와 내구 workflow 런타임 결합은 빠르게 진전할 가능성이 크지만, 승인 없는 self-modifying graph와 “system intelligence”의 독립적 측정은 계속 연구 단계일 가능성이 높다.

## 1. 용어 혼동 정리

이 조사에서 **agentic graph**는 실행을 조직하는 관계 구조다. 노드는 과업, 에이전트, 도구/능력, 사람, 상태 전이, 검증기 또는 artifact를 나타낼 수 있고, edge는 선행 의존성, 데이터 전달, 할당, 권한, 통신, 검증, 실패/복구 경로를 나타낸다. 반면 knowledge graph/GraphRAG는 세계의 엔터티·사실·관계를 표현하거나 검색하는 **데이터/컨텍스트 계층**이다. 후자는 전자의 한 capability 또는 data node가 될 수 있지만 동일 개념은 아니다.

또한 “그림을 그린다”와 “graph runtime을 가진다”도 다르다. 운영 그래프라면 edge가 실제 scheduling/guard/commit 의미를 갖고, 현재 node와 state version을 저장하며, 중단·재개·부분 실패·종료를 결정해야 한다. 단순 org chart, prompt 속 역할 목록, 대화 로그 시각화는 이 기준에서 graph engineering이 아니다.

## 2. 기원과 타임라인

| 시기 | 확인된 사건 | 해석과 주의 |
|---|---|---|
| 1962–1994 | Petri net, actor model, statechart, blackboard, HTN 등 동시성·상태·분산 협업·계층 분해의 선행 이론이 정립됨 | graph-shaped orchestration의 계산 아이디어는 새롭지 않다. |
| 2023–2025 | LangGraph, AutoGen, CrewAI 및 LLMCompiler, GPTSwarm, AFlow 등은 explicit graph, multi-agent topology, workflow search를 구현·연구 | 당시에는 주로 workflow, agent graph, orchestration, computational graph라 불렸다. |
| 2026-03~07 | Loop Engineering이 단일 agent의 지속 실행·증거 기반 중단을 설명하는 실무/논문 용어로 부상; [Proof-or-Stop](https://arxiv.org/abs/2607.14890), [Stop Hand-Holding](https://arxiv.org/abs/2607.00038) 등이 출현 | prompt → context → harness → loop의 계층 서사가 정리되었다. |
| 2026-07-18 | Peter Steinberger의 “Are we still talking loops or did we shift to graphs yet?” 게시물이 실무 담론을 크게 증폭([동시대 캡처·분석](https://graphslice.com/blog/loops-or-graphs/)) | 문장 자체는 용어 정의도 최초 주창 선언도 아니다. 원 X 게시물은 본 조사 도구에서 독립 열람하지 못했다. |
| 2026-07~08 | 블로그들이 loop=한 agent의 반복, graph=여러 agent/도구/사람의 topology라는 대비를 빠르게 확산 | 블로그는 용어 출현 증거이지 기술적 유효성 증거가 아니다. “2024년 유사 표현/7월 11일 ladder” 주장도 2차 자료이므로 최초 주창자로 확정하지 않는다([추적 글](https://www.aibuilderclub.com/blog/graph-engineering-peter-steinberger)). |
| 2026-08-21 | Feng et al. preprint 제출: 36인 공동 survey가 Model → Individual → System Intelligence 서사와 Graph Engineering taxonomy를 제안 | viral term을 발명했다기보다 이미 존재한 기술과 7월 담론을 폭넓은 연구 범주로 정식화한 성격이 강하다. peer review 전 preprint다. |
| 2026-08-27 | 동반 저장소 최신 확인 commit `dcf14b1...` | 논문·benchmark·library를 지속 큐레이션하므로 목록은 동적이며 품질/상태가 혼재한다. |

**최초 주창자 결론:** 확인 가능한 자료만으로 단일 최초 주창자를 지정할 수 없다. Steinberger는 2026년 wave의 촉발/증폭자로 보는 것이 안전하고, Feng et al.은 이 의미의 “Graph Engineering”을 포괄적 연구 taxonomy로 정식화한 최초급 survey 저자군으로 표현할 수 있다. “prompt → context → harness → loop → graph” 전체 ladder는 survey abstract와 2026년 7월 말 실무 글 양쪽에 나타나지만, 하나의 검증된 역사 법칙이 아니라 바깥쪽 engineering object로 초점을 옮겨가는 서사다.

## 3. 정확한 정의와 개념 모델

### 3.1 논문 정의를 운영적으로 풀기

**[확인]** 논문은 System Intelligence를 “복잡한 목표를 분해·조직하고, 이질적 계산 agent에 책임을 배분하고, 상호의존 실행을 조정하며, task lifecycle 전체에서 system-level state를 유지하는 능력”으로 정의한다. 형식적으로 개별 agent는 `Aᵢ = Loop(Fᵢ, Hᵢ; sᵢᵗ)`, agent system은 시점 `t`에서 agent team, shared resources, environment, coordination mechanism, system state의 묶음으로 놓는다. 따라서 Graph Engineering의 목적은 agent 수 증가가 아니라 **관계의 명시적 표현·제약·최적화**다.

### 3.2 무엇이 graph에 들어가는가

| 관점 | 대표 node | 대표 typed edge | 운영 의미 |
|---|---|---|---|
| 목표/과업 | goal, subtask, verifier | `depends_on`, `precedes`, `requires_evidence`, `repairs` | 준비 상태, critical path, 병렬 가능성, 완료 조건 |
| 실행 연산 | LLM call, agent loop, tool, router, join | `on_success`, `on_failure`, `routes_to`, `fan_out`, `joins` | control flow와 dispatch |
| agent/조직 | agent, role, team, human | `assigned_to`, `delegates`, `supervises`, `reviews` | 책임·분업·승인 경계 |
| capability/authority | model, tool, skill, permission, budget | `can_use`, `requires`, `substitutes`, `authorized_for` | capability-aware routing와 least privilege |
| data/artifact/evidence | file, patch, dataset, test result, citation | `produces`, `consumes`, `supports`, `invalidates` | payload가 아니라 immutable reference와 provenance 전달 |
| communication | message channel, topic, mailbox | `may_send`, `requests`, `responds`, `broadcasts` | 누가 누구에게 어떤 schema로 말하는지 |
| runtime state | event, snapshot, commitment, external effect | `causes?`, `derived_from`, `commits`, `compensates` | replay, consistency, fault localization, recovery |

중요한 구분은 dependency가 causality를 증명하지 않는다는 점이다. survey도 fault localization에서 구조·시간적 연결은 원인 후보의 탐색 범위를 좁힐 뿐 외부 evidence로 검증해야 한다고 명시한다.

### 3.3 기본 실행 어휘

- **Node:** 원자적이거나 캡슐화된 실행 단위. deterministic tool도, 비결정적 LLM/agent loop도, human task도 가능하다.
- **Edge:** 단순 화살표가 아니라 trigger/guard, 전달 artifact schema, 권한, retry/timeout, 결과 type을 가진 계약이다.
- **State:** 현재 실행 위치만이 아니라 task status, role binding, committed fact, artifact version, budget, 외부 effect를 포함한다.
- **Subgraph:** planner–workers–reviewer 또는 repair loop처럼 자체 entry/exit와 state scope를 가진 재사용 가능한 복합 node다.
- **Cycle:** 재검토·retry·repair·지속 이벤트 처리. `max_iterations`, 시간/비용, 증거 predicate 중 적어도 하나로 bounded 되어야 한다.
- **Fan-out / fan-in:** 독립 branch를 병렬 dispatch하고, join에서 all/any/quorum/timeout/quality 조건으로 합친다.
- **Router:** 관찰된 state와 typed outcome에 따라 다음 edge를 선택한다. LLM router라면 허용 destination whitelist와 fallback이 필요하다.
- **Join:** 단순 문자열 합치기가 아니라 중복, conflict, missing branch, partial failure를 해결하는 barrier/aggregator다.
- **Checkpoint:** committed state + graph version + artifact pointers + external-effect ledger의 복구 가능한 경계다.
- **Termination:** leaf 도달만으로 충분하지 않다. 목표 evidence, 미해결 blocking edge 부재, budget, 승인 상태를 함께 검사해야 한다.

### 3.4 static, dynamic, evolving

| 종류 | topology 변화 | 지속 범위 | 예 |
|---|---|---|---|
| Static graph | 배포된 node/edge 고정, 조건에 따라 경로만 다름 | 여러 run에 동일 | 고정 approval workflow, Airflow DAG |
| Dynamic graph | 한 run 동안 task decomposition, worker 수, route, edge가 생성/제거됨 | 보통 해당 run | 중간 결과로 새 조사 task 생성, 병렬 worker 증감 |
| Evolving/self-modifying graph | 실행 evidence가 graph definition 자체의 새 version을 제안·검증·commit | 후속 run에 재사용 | AFlow/GPTSwarm류 topology search, reusable coordination rule 학습 |

**[분석]** “동적”과 “진화”를 섞으면 위험하다. 조건부 edge를 탄 것은 topology 학습이 아니며, run-time temporary subgraph 생성도 후속 run의 조직을 바꾸지 않으면 evolution이 아니다. 진화에는 `observe → structural credit assignment → candidate diff → offline/shadow evaluation → approval → versioned commit 또는 rollback`이 필요하다.

## 4. Loop Engineering vs Graph Engineering

| 차원 | Loop Engineering | Graph Engineering |
|---|---|---|
| 주 객체 | 한 agent의 반복 실행 계약 | 여러 실행 단위의 관계·topology·공유 상태 |
| 핵심 질문 | 다음 행동은 무엇이며 언제 충분한가? | 누가 무엇을 언제 수행하고, 무엇을 기다리며, 어떻게 합치고 복구하는가? |
| 수렴 | self-check/external verifier와 retry | branch별 수렴 + join/gate에서 system-level coherence |
| 병렬성 | 보통 한 locus의 순차 trajectory | explicit fan-out/fan-in, dependency scheduling |
| 상태 | local context/memory/action history | scoped, versioned, persistent system state와 artifact lineage |
| 검증 | 같은 agent가 점검할 수 있음 | 독립 verifier, reviewer, human gate를 topology로 분리 가능 |
| 실패 | retry/stop | isolate, reroute, checkpoint resume, compensation, partial commit |
| 비용 위험 | infinite loop/overthinking | coordination overhead, branch explosion, duplicated context |

관계는 `Graph = composition of nodes`, 그리고 많은 agent node는 내부적으로 `Loop(LLM + Harness)`다. 즉 loop는 graph의 node 또는 cyclic subgraph이며 graph가 loop를 대체하지 않는다. 반대로 단일 loop도 수학적으로는 cyclic control-flow graph로 표현할 수 있지만, 2026년 실무 구분의 유용성은 **설계 단위**에 있다.

**Loop면 충분한 경우:** 하나의 mutable artifact, 단일 writer, 작업이 본질적으로 순차적, verifier 하나, 병렬 speedup이 작음, 같은 권한/도구 경계, 전체 재시작 비용이 낮음. **Graph가 필요한 신호:** 독립 가능한 2개 이상 branch, 서로 다른 권한/전문성, 독립 review, 장시간/비동기 wait, partial failure를 보존해야 함, 여러 외부 effect를 보상해야 함, 사람이 중간 승인해야 함, 단일 context가 상태/책임을 감당하지 못함.

## 5. Feng et al. 프레임워크 해부

### 5.1 전체 taxonomy

논문의 큰 진행은 다음과 같다.

1. **Model Intelligence:** pre/post-training과 prompt/context engineering으로 bounded inference의 능력을 만든다.
2. **Individual Intelligence:** Harness Engineering(tool, memory, skill, runtime orchestration)과 Loop Engineering(loop architecture, interaction paradigm, environment feedback)으로 지속 goal-directed agent를 만든다.
3. **System Intelligence / Graph Engineering:**
   - **Task Organization:** Goal Decomposition + Workflow Optimization
   - **Agent Coordination:** Capability Modeling + Team Organization + Multi-agent Communication
   - **Runtime State Management:** State Recording + Fault Localization + Failure Recovery
   - **System Evolution:** 위 세 구조를 실행 경험으로 지속 개선
4. **Ontology Engineering(미래 방향):** goal, capability, evidence, state, policy의 공유 의미·제약을 제공한다. Graph Engineering의 다음 대체 단계라기보다 semantic foundation이다.

### 5.2 organization graph와 execution/state graph

논문은 하나의 단일 canonical graph schema를 정의하지 않는다. 실제로는 결합된 view들이다.

- **Work Organization Graph:** semantic goal/subgoal dependency와 이를 tool/agent/verifier operator로 compile한 executable workflow.
- **Agent Capability Graph:** agent–skill–tool–permission–reliability 관계.
- **Agent Team/Organization Graph:** assignment, delegation, supervision, review, reporting의 상대적으로 안정된 책임 구조.
- **Communication Graph:** 특정 round/run에서 활성화되는 message와 feedback 경로; organization보다 동적이다.
- **State Evolution Graph:** event, version, evidence, commit, failure propagation, recovery frontier.

이 view들은 서로 제약한다. task node의 capability 요구가 team assignment를 제한하고, team 교체는 permission과 communication edge를 바꾸며, state evidence가 workflow/recovery edge를 재구성한다. 따라서 graph engineering의 실질적 난점은 그래프 저장이 아니라 **cross-view consistency**다.

### 5.3 survey가 드는 대표 방법

- Task graph: [LLMCompiler](https://arxiv.org/abs/2312.04511)은 function-call plan을 dataflow DAG로 compile해 ready node를 병렬 dispatch한다.
- Workflow search: [GPTSwarm](https://proceedings.mlr.press/v235/zhuge24a.html)은 LLM 시스템을 optimizable computational graph로, [AFlow](https://openreview.net/forum?id=z5uVAKwmjf)는 executable workflow code search로 취급한다.
- Dynamic workflow: [DyFlow](https://arxiv.org/abs/2509.26062)은 intermediate feedback으로 다음 operator subgraph를 조정한다.
- Team/communication: Magentic-One은 orchestrator ledger와 delegation, [DyTopo](https://arxiv.org/abs/2602.06039)는 round별 sparse communication edge 재구성을 탐구한다.
- Governed state: [PatchBoard](https://arxiv.org/abs/2605.29313)는 schema/role/invariant 기반 patch commit, [MemTX](https://arxiv.org/abs/2607.23929)는 tentative write와 transactional belief commit을 구분한다.
- Failure: [MAST](https://proceedings.neurips.cc/paper_files/paper/2025/hash/b1041e52d3be19f0a9bc491657488e4a-Abstract-Datasets_and_Benchmarks_Track.html)는 multi-agent failure를 system design/inter-agent alignment/task verification으로 분류한다.

### 5.4 application과 open problem

survey는 software/IT operations, scientific discovery/lab automation, healthcare, enterprise workflows, general digital agents, social/economic simulation을 적용 영역으로 분류한다. 그러나 저자들도 work organization·coordination·state management는 관찰되지만 **persistent system evolution은 제한적**이라고 평가한다. 주요 open problem은 autonomous ontology construction, graph-native capability substrate, safe self-evolution, graph-native agent OS, privacy/ethics이며, 이는 현재 완성된 discipline이 아니라 research agenda임을 보여준다.

## 6. 기존 이론·도구 비교와 신규성 평가

### 6.1 고전 모델

| 기존 개념 | 이미 제공하는 것 | Graph Engineering이 추가로 강조하는 것 | 남는 교훈 |
|---|---|---|---|
| DAG/workflow | dependency, ready scheduling, fan-out/in, retry | LLM/agent node, dynamic decomposition, evidence/authority | cycle·interaction에는 DAG만으로 부족 |
| Petri net | concurrency, synchronization, resource token, deadlock 분석 | semantic task/agent/capability와 probabilistic output | join/resource contention은 token semantics로 검증 가능 |
| FSM/statechart | guarded transition, hierarchy, orthogonal concurrency, event | LLM-generated transition proposal와 graph mutation | 모든 node가 임의 routing하면 formal analyzability 상실 |
| dataflow | value dependency, parallel execution, deterministic recompute | artifacts plus prompts/models/humans | data와 control을 구분하고 immutable value를 선호 |
| BPMN | human task, gateway, event, compensation, boundary error | nondeterministic cognitive workers와 evolving topology | 승인·보상·escalation을 새로 발명할 필요 없음 |
| actor model | isolated state, async mailbox, supervision 계열 | typed evidence flow와 global task graph | shared mutable state보다 message + single writer가 안전 |
| distributed scheduler | leases, heartbeat, idempotency, backpressure, cancellation | semantic quality gate와 agent selection | agent “협업”도 결국 failure-prone distributed execution |
| blackboard | 여러 specialist가 공유 workspace에 기여, controller가 기회를 선택 | provenance, typed patch, access scope, learned topology | 공유 board는 write governance 없으면 corruption point |
| HTN/planning | goal decomposition, methods/operators, partial order | runtime LLM decomposition·replanning·capability matching | plan과 execution state를 분리하고 precondition/effect를 명시 |
| multi-agent systems | role, protocol, negotiation, coordination topology | LLM prompt/tool/harness와 실무 trace/cost integration | “multi-agent = system intelligence”는 성립하지 않음 |

**신규성 판정:**

- **새 계산 모델인가? 아니오.** node/edge, 분기, 병렬, cycle, state, message, recovery는 수십 년 된 개념이다.
- **단순 재명명인가? 부분적으로 그렇다.** 많은 static “graph engineering” 구현은 기존 workflow orchestration에 LLM node를 넣은 것이다.
- **유용한 통합 discipline 후보인가? 조건부 예.** task topology, 조직/권한, communication, evidence lineage, runtime state, topology optimization을 하나의 설계 대상으로 묶고, 비결정적 agent의 출력과 비용을 first-class로 본다는 점은 실무상 유용하다.
- **현재 확립된 discipline인가? 아직 아니다.** 공통 schema/semantics, 인증, 표준 benchmark, 직무/채택률, peer-reviewed body of evidence가 없다. survey 자체도 preprint이며 많은 2026 인용은 preprint다.

### 6.2 현재 도구 기능 확인 (2026-08-28 공식 문서)

| 도구 | 확인된 기능 | Graph Engineering 관점의 한계/위치 |
|---|---|---|
| [LangGraph](https://docs.langchain.com/oss/python/langgraph/graph-api) | node/edge, typed shared state, conditional/cyclic route, `Command`, subgraph, parallel branch; checkpointer·interrupt·resume([interrupt docs](https://docs.langchain.com/oss/python/langgraph/interrupts)) | 가장 직접적인 agent graph runtime이지만 cross-graph ontology, capability/permission graph, safe persistent topology learning은 앱 책임 |
| [AutoGen GraphFlow](https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/graph-flow.html) | sequential, parallel, conditional, loop와 exit condition; agent=node, edge=allowed path | 공식 문서가 experimental 경고; durable transaction/evolution discipline은 제한적 |
| [CrewAI Flows v1.15.17](https://docs.crewai.com/v1.15.17/en/concepts/flows) | event-driven start/listen/router, 조건·loop·branch, structured/unstructured state, SQLite persistence, resume/fork, usage metrics | 편리한 flow abstraction; 강한 concurrent state semantics와 topology governance는 별도 설계 필요 |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/multi_agent/) | manager-as-tools와 handoff, typed handoff input/filter, input/output/tool guardrails, session, trace/span | general graph DSL보다는 code-driven orchestration primitive; handoff는 한 run 안에서 active agent를 넘기며 guardrail 적용 범위를 주의([handoff docs](https://openai.github.io/openai-agents-python/handoffs/)) |
| [Temporal](https://docs.temporal.io/workflows) | durable workflow history/replay, activity retry/timeout, signal/query/update, cancellation/compensation 패턴 | agent semantic graph는 없지만 내구 실행 substrate로 강함; deterministic workflow code 제약과 LLM call을 activity로 격리해야 함 |
| [Airflow 3.3](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html) | scheduled DAG, dependency, task state/retry/timeout, branching/trigger rule, dynamic task mapping | batch/data pipeline에 성숙; docs도 topology 안정성을 권고하므로 runtime self-rewiring/cycle형 agent에는 부적합 |
| [Prefect 3](https://docs.prefect.io/v3/concepts/flows) | Python flow/task, state, retry, concurrency, deployment/observability | dynamic Python orchestration substrate; 조직·권한·evidence schema는 앱 책임 |
| [Dagster](https://docs.dagster.io/guides/build/ops/graphs) | graph/op composition, typed data dependency, assets, partitions, run observability | data asset lineage에 강함; conversational agent/team topology와 cycle은 주 목적 아님 |

## 7. 설계 패턴과 참조 아키텍처

### 7.1 패턴

- **Planner–worker–reviewer:** planner는 task graph만 제안, scheduler가 dependency/permission을 검증해 worker를 dispatch, reviewer는 worker context와 분리하고 artifact+evidence만 검증한다.
- **Map–reduce:** homogeneous input shard를 fan-out하고 join에서 schema validation, missing shard policy, associative merge를 적용한다. LLM summarization을 reduce의 유일한 정확성 장치로 쓰지 않는다.
- **Debate–judge:** diverse candidate 후 독립 judge. 같은 model/prompt 계열이면 오류 상관관계가 높으므로 “독립”이라 부르지 말고 external evidence를 anchor로 둔다.
- **Supervisor hierarchy:** scope별 subgraph owner를 둔다. 모든 message를 root supervisor로 통과시키면 context/cost bottleneck과 single point of failure가 된다.
- **Blackboard:** immutable artifact와 append-only proposal를 공유하고 validator/single committer가 authoritative state에 반영한다.
- **Event-driven:** event type + correlation/idempotency key로 node를 깨운다. out-of-order, duplicate, late event를 정상 조건으로 처리한다.
- **Human approval gate:** irreversible action 전에 diff, evidence, cost, rollback/compensation plan을 보여주고 approval identity/time/scope를 commit한다.
- **Repair/retry subgraph:** failure class를 먼저 분류하고 transient는 bounded retry, semantic failure는 diagnose→repair→independent verify, irreversible effect는 compensation/escalation으로 분기한다.

### 7.2 최소 graph runtime/schema 예시

```yaml
graph:
  id: incident-triage
  version: 7
  entry: ingest
  invariants:
    - max_total_tokens: 300000
    - max_wall_time: 45m
    - authoritative_state_writer: state-committer
nodes:
  ingest:
    kind: deterministic_tool
    output: IncidentBundle@v2
    idempotency_key: incident_id
  investigate:
    kind: agent_subgraph
    capabilities: [read_logs, read_metrics]
    permissions: [prod:read]
    fan_out: {max: 3}
    output: HypothesisWithEvidence@v1
  join:
    kind: deterministic_join
    policy: {mode: quorum, min_success: 2, timeout: 8m}
  verify:
    kind: independent_verifier
    input: HypothesisWithEvidence@v1
    output: [verified, rejected, insufficient]
  approve:
    kind: human_gate
    required_for: [prod:write]
  remediate:
    kind: tool
    permissions: [prod:write]
    compensation: rollback-remediation
edges:
  - {from: ingest, to: investigate, on: valid}
  - {from: investigate, to: join, carries: artifact_ref}
  - {from: join, to: verify, on: quorum_met}
  - {from: verify, to: approve, on: verified}
  - {from: verify, to: investigate, on: insufficient, max_traversals: 1}
  - {from: approve, to: remediate, on: approved}
state:
  event_log: append_only
  checkpoint: after_each_commit
  artifacts: immutable_content_addressed
  concurrent_updates: compare_and_swap
termination:
  success: remediation_verified
  failure: [budget_exhausted, approval_denied, no_recovery_path]
```

참조 실행면은 `Graph Definition Registry(versioned)` → `Validator(type/permission/cycle/budget)` → `Scheduler/Router` → `Workers/Tools/Humans` → `Artifact Store` → `Event Log + State Committer` → `Verifier/Gates` → `Trace/Metrics`로 구성한다. 정의와 run state를 분리하고 모든 run은 graph version을 pin한다. node 반환값은 대화문보다 `status`, `artifact_refs`, `evidence_refs`, `state_patch`, `metrics`, `next_outcome`의 typed envelope가 낫다.

### 7.3 분산 실행 필수 규칙

- 병렬 branch는 state를 직접 덮어쓰지 않고 proposal/patch를 제출한다.
- join은 all/any/quorum을 명시하고 timeout 시 missing branch 처리와 cancellation propagation을 정한다.
- retry는 idempotency key와 attempt fencing을 사용한다. 외부 effect는 “적어도 한 번” 재실행을 가정한다.
- checkpoint는 LLM transcript만 저장하지 말고 graph version, committed artifacts, pending obligations, external-effect ledger를 저장한다.
- cancellation은 parent→child로 전파하되 이미 commit된 외부 effect는 compensation queue에 넣는다.
- deterministic node와 nondeterministic node를 구분해 replay 시 전자는 재계산, 후자는 recorded output 재사용 또는 명시적 re-sample을 선택한다.

## 8. 동적·진화형 그래프의 안전 조건

Runtime task decomposition은 허용된 node template과 edge type 안에서만 subgraph를 만들고, validator가 cycle bound, capability availability, permission flow, budget, unreachable join을 검사한 뒤 활성화해야 한다. runtime node 삭제는 이미 생성한 artifact/obligation을 고아로 만들지 않아야 하며, rewiring은 downstream input schema와 reviewer independence를 보존해야 한다.

지속적 self-improvement에는 다음 불변식이 필요하다.

1. 실행 중인 run은 pin된 graph version을 바꾸지 않는다.
2. agent는 candidate graph diff만 제안하며 production commit 권한을 갖지 않는다.
3. candidate는 syntax/type 검사, historical replay, shadow/canary, matched-budget 평가를 거친다.
4. 성공률뿐 아니라 cost, latency, safety intervention, rare failure regression을 함께 본다.
5. 변경의 source trace와 structural credit assignment를 기록한다.
6. approval, migration plan, compatibility check, rollback pointer가 없는 version은 배포하지 않는다.
7. authority, budget, termination, evidence requirement를 완화하는 변경은 human gate를 필수로 한다.

survey가 인용한 topology/workflow 최적화 결과는 이런 production governance 전체를 증명하지 않는다. 검색 공간에서 benchmark score를 높인 것과 안전한 self-modifying operational system은 다른 주장이다.

## 9. 평가와 관측성, 현재 증거 수준

### 9.1 평가 단위와 지표

| 영역 | 지표 예시 | 왜 필요한가 |
|---|---|---|
| 결과 | task success, verifier pass, correctness severity | 최소 성능 |
| 구조 | dependency validity, unreachable/dead node, cycle bound, graph edit rate | graph 자체의 유효성 |
| 병렬 | critical-path latency, work/span, parallel efficiency, join wait, straggler rate | agent 수가 실제 speedup인지 판별 |
| 조정 | handoff loss, duplicate work, message/token overhead, routing precision, aggregation conflict | coordination tax 측정 |
| 상태 | stale-read/lost-update/conflict rate, provenance completeness, replay determinism | shared state 신뢰성 |
| 검증 | verifier independence, false accept/reject, evidence coverage, evaluator disagreement | 상호 확증/게임 방지 |
| 복구 | MTTR, recovery frontier accuracy, valid-work preservation, retry amplification, compensation success | partial failure 대응 |
| 자원 | token, model/tool cost, wall time, CPU/GPU, human minutes | 더 많은 compute의 착시 제거 |
| 거버넌스 | permission denials, unauthorized edge attempts, human intervention, rollback rate | 통제 가능성 |
| 진화 | cross-task transfer, regression, version survival, structural ablation effect | 지속 improvement 검증 |

### 9.2 benchmark 현실

**[확인]** survey는 TaskBench/WorFBench/TPS-Bench류 work graph, MultiAgentBench/SILO-BENCH/MAS-BENCH류 coordination, SyncBench/MAST/Who&When/TraceElephant류 state/failure, MASEval/MAS-PromptBench/BenchAgent류 system variant 평가를 묶는다. 이는 **부분 probe**다. 논문 스스로 현재 자원이 work/coordination/state/evolution에 파편화되어 있고 persistent evolution, structural credit assignment, dynamic system evaluation이 약하다고 적는다.

**[분석]** 기존 SWE-bench, GAIA, WebArena 같은 end-task benchmark는 graph topology의 기여를 분리하지 못한다. 올바른 검증은 같은 foundation model, tool, context allowance, retry/토큰/시간 예산에서 single loop vs fixed graph vs dynamic/evolving graph를 비교하고, graph artifact·complete trace·state snapshot을 공개하며, node/edge/permission/state mechanism을 구조적으로 ablate해야 한다. “공개 graph benchmark가 존재한다”와 “Graph Engineering 전체가 정량적으로 입증됐다”는 전혀 다른 문장이다.

**증거 등급:** (A) classic orchestration semantics와 durable workflow 운영 경험—강함; (B) 개별 LLM workflow/topology 방법의 benchmark 개선—중간이나 task별; (C) heterogeneous graph가 비용 대비 일반적으로 우월—약함; (D) 안전한 persistent self-evolution과 독립적인 “system intelligence”—매우 약함/연구 의제.

## 10. 안전, 실패 모드, 거버넌스

| 실패 모드 | 메커니즘 | 최소 방어 |
|---|---|---|
| 권한 누출 | handoff가 원 agent의 credential/context를 그대로 전달 | node별 identity, capability token, deny-by-default edge, secret redaction |
| 오류 증폭/상호 확인 | 같은 모델 계열 agent들이 같은 오류를 반복 인용 | independent verifier context, diverse evidence source, external executable check |
| shared-state corruption | concurrent write, stale view, prompt가 authoritative fact를 수정 | single writer/transaction, schema validation, CAS/version, append-only event log |
| deadlock/livelock | 서로의 완료/승인을 기다리거나 review-repair가 진전 없이 순환 | wait-for graph 검사, lease/timeout, progress metric, traversal bound |
| cycle 폭주 | LLM router가 계속 retry/새 task 생성 | graph-wide budget, per-edge count, hard termination, circuit breaker |
| evaluator gaming | worker가 judge prompt/score를 보고 맞춤 출력 | evaluator isolation, hidden/external tests, evidence audit, rotating checks |
| emergent collusion | agent들이 상호 승인하거나 제한을 우회 | separation of duties, no self-approval path, immutable authority graph, human gate |
| provenance 단절 | summary/handoff 중 source와 uncertainty 소실 | content-addressed artifacts, typed evidence link, no unsupported state commit |
| partial side effect | retry가 이메일/배포/결제를 중복 실행 | idempotency key, effect ledger, transactional outbox, compensation |
| topology poisoning | 공격적 input/feedback이 dynamic edge를 위험 경로로 유도 | trusted structural signals, template whitelist, graph-diff validation, approval |

특히 OpenAI Agents SDK 공식 handoff 문서는 tool input guardrail이 handoff에 적용되지 않으며 handoff authorization은 side effect 전에 `on_handoff`에서 검사해야 한다고 주의한다. LangGraph interrupt 문서는 resume 시 node가 처음부터 재실행되므로 interrupt 이전 side effect가 idempotent해야 한다고 명시한다. 이런 세부 semantics가 “graph 그림”보다 중요하다.

## 11. 실무 적용

### 11.1 사례별 적합성

| 사례 | 유용한 graph | 주의 |
|---|---|---|
| 코딩 agent | issue decomposition → parallel code/research → deterministic tests → independent review → repair | 같은 checkout 동시 수정 방지, patch artifact/merge owner 분리 |
| 연구 agent | query decomposition → source-specialist fan-out → provenance join → contradiction review → synthesis | citation laundering과 중복 source, 날짜/peer-review 상태 보존 |
| incident response | signal ingest → parallel hypotheses → evidence gate → human approval → remediation/rollback | prod read/write 권한 분리, irreversible action compensation |
| 데이터 pipeline | asset dependency → quality checks → retry/backfill → publish | 기존 Airflow/Dagster/Prefect가 우선; LLM은 bounded node로 제한 |
| enterprise process | event → policy router → specialist → approval → audit | BPMN/Temporal과 결합하고 규정 의미를 prompt에만 두지 않음 |

### 11.2 Loop에서 Graph로 전환 판단표

다음 질문 중 **3개 이상이 예**, 특히 권한/부분 실패/승인이 하나라도 예면 graph를 검토한다.

- 독립적으로 실행 가능한 작업이 둘 이상이고 실제 latency 이득이 있는가?
- 서로 다른 tool, credential, model, 전문성이 필요한가?
- 생산자와 verifier를 독립시켜야 하는가?
- intermediate artifact를 여러 consumer가 사용하거나 join해야 하는가?
- 일부 branch 실패 시 유효한 작업을 보존해야 하는가?
- 사람이 실행 중간에 승인/수정/중단해야 하는가?
- 장시간 wait, callback, event, resume가 있는가?
- 한 agent context에서 task/role/state가 섞여 반복적 오류가 나는가?
- 외부 effect에 idempotency/compensation이 필요한가?
- topology별 비용·성능을 관측하고 바꿀 실험 계획이 있는가?

반대로 작업이 순차적이고, single writer이며, 외부 verifier 하나로 충분하고, 실패 시 cheap restart가 가능하면 bounded loop를 유지한다.

### 11.3 도입 단계

1. 현재 single loop의 tool calls, state, evidence, termination과 failure를 trace한다.
2. 먼저 deterministic boundary와 artifact contract를 만든다; agent를 늘리지 않는다.
3. 가장 명확한 한 branch만 subgraph로 분리하고 fixed topology로 운영한다.
4. checkpoint/resume, idempotency, cancellation, join timeout, human gate를 추가한다.
5. matched-budget A/B와 structural ablation으로 graph의 이득을 측정한다.
6. capability/permission/state view를 분리하고 graph versioning을 도입한다.
7. 충분한 trace가 쌓인 뒤에만 dynamic decomposition을 허용한다.
8. persistent topology evolution은 proposal-only와 shadow/canary 이후 별도 승인한다.

### 11.4 anti-pattern

- 한 agent 문제를 해결하기 전에 역할 이름만 다른 10개 agent를 만든다.
- edge를 자연어 “다음에 누구와 대화할지”로만 두고 type/guard가 없다.
- 모든 branch가 하나의 mutable dict/document를 쓴다.
- LLM router가 임의 agent/tool/permission을 생성할 수 있다.
- self-review를 independent verification이라 부른다.
- retry와 cycle에 graph-wide budget/termination이 없다.
- topology를 매 run 바꾸면서 graph version과 비교 baseline을 기록하지 않는다.
- Airflow/Temporal 같은 운영 문제를 agent framework만으로 다시 구현한다.
- 성공률만 보고 agent 수·토큰·latency·human intervention을 숨긴다.

## 12. 성숙도와 6–18개월 전망

**현재 성숙도(2026-08-28):** 용어는 preprint와 커뮤니티에서 급성장 중이고, 구성 기술은 일부 성숙했지만 통합 discipline은 초기다. static graph와 durable workflow는 production-ready 도구가 있고, dynamic task/team routing은 task별 연구·프레임워크 기능, persistent self-evolution은 실험적이다. 동반 저장소는 유용한 index지만 survey 저자 측 큐레이션이며 독립 systematic review나 품질 인증 목록은 아니다.

**[전망, 6–18개월]:**

- graph definition/run trace/artifact/evidence를 잇는 typed schema와 OpenTelemetry 계열 관측 연계가 늘어날 가능성이 높다.
- agent framework가 Temporal류 durable execution, transaction/compensation, policy engine과 결합할 것이다.
- benchmark는 fixed budget, structural perturbation, repeated-run evolution, human intervention cost를 더 많이 포함할 것이다.
- topology optimizer는 production graph를 직접 수정하기보다 candidate generation + offline replay/shadow evaluation 형태로 정착할 가능성이 높다.
- “system intelligence”는 모델 성능과 compute scaling 효과를 분리하지 못하면 마케팅 용어로 남을 위험이 있다.
- ontology engineering은 유용하더라도 모든 팀이 OWL/지식 그래프를 도입한다기보다, JSON Schema/typed contract/policy-as-code로 먼저 나타날 가능성이 높다.

## 13. 결론과 최소 후속 Inquiry

Graph Engineering은 “loop 다음의 마법”이 아니라, agent loop들을 오래된 workflow·distributed-systems 원칙 위에서 명시적으로 구성하고, LLM 특유의 비결정성·evidence·authority·cost·topology adaptation을 함께 관리하자는 이름이다. 가장 설득력 있는 부분은 task/team/communication/state graph를 분리해 관계와 실패 경계를 first-class로 만드는 것이고, 가장 약한 부분은 이것이 일반적인 system intelligence와 안전한 self-evolution을 이미 달성했다는 함의다. 실무자는 새 프레임워크부터 고르지 말고 typed artifact, state ownership, durable execution, independent verification, budget/termination을 먼저 설계해야 한다.

**최소 후속 Inquiry:** 동일 coding 또는 research task 세트에서 `bounded single loop`, `fixed planner–worker–reviewer graph`, `dynamic decomposition graph`를 동일 모델·tool·token/time budget으로 실행해 success, critical path, coordination overhead, verifier independence, recovery, human minutes를 비교하고 완전한 graph version/trace/state snapshot을 보존하는 소규모 controlled study. 이 후속은 제품 선택이나 구현 승인이 아니라 현재 가장 큰 증거 공백을 줄이는 조사 설계다.

## 조사 한계

- 기준 논문은 2026-08-21 arXiv preprint이며 peer review가 끝나지 않았다.
- 매우 넓은 survey의 517개 참고문헌을 전수 재현하지 않고 taxonomy를 지탱하는 대표 원 논문과 공식 framework 문서를 추적했다.
- 7월 social-media 원 게시물은 직접 API/페이지로 검증하지 못해 동시대 캡처와 복수 2차 기록으로 교차 확인했으며, 최초 주창자를 확정하지 않았다.
- framework 문서는 기준일 현재 web 문서다. AutoGen GraphFlow는 공식적으로 experimental이고 CrewAI 문서는 version 1.15.17로 redirect되었다.
- benchmark의 존재·범주는 확인했지만 개별 benchmark 결과를 재실행하지 않았고, 채택률·시장 점유율은 자료가 없어 제시하지 않았다.

