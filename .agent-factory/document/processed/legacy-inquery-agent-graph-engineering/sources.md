# Agentic Graph Engineering 출처 목록

> 조사 기준일: 2026-08-28. `자료 유형`의 preprint는 peer review 전으로 취급했다. 로컬 원문 cache는 이 Inquiry 작업공간의 `source-cache/`에 있으며 canonical evidence가 아니라 재검토 편의를 위한 임시 자료다.

## A. 핵심 survey와 동반 자료

| 제목 | 저자/기관 | 날짜 | URL | 자료 유형 | 사용 주장 |
|---|---|---:|---|---|---|
| Graph Engineering in the Era of LLM Agents: From Individual Intelligence to System Intelligence | Yuyuan Feng et al. (36 authors) | 2026-08-21 | https://arxiv.org/abs/2608.21156 | arXiv preprint, cs.IR | 정의, Model→Individual→System 서사, 3대 taxonomy, system evolution, benchmark/도구/application/open problem |
| Awesome-Graph-Engineering | DEEP-JLU | 확인 commit 2026-08-27 | https://github.com/DEEP-JLU/Awesome-Graph-Engineering | 동반 큐레이션 저장소 | 원 논문, benchmark, library 추적; commit `dcf14b1ada26211e99e6d3597b999f064ae0edb2` |
| 로컬 survey PDF/text | arXiv 원문 cache | 2026-08-28 수집 | `source-cache/2608.21156.pdf`, `source-cache/2608.21156.txt` | 임시 Inquiry 자료 | 전체 본문·참고문헌 직접 검토 |

## B. 용어 출현과 Loop Engineering 맥락

| 제목 | 저자/기관 | 날짜 | URL | 자료 유형 | 사용 주장 |
|---|---|---:|---|---|---|
| Are we still talking loops, or did we shift to graphs yet? | GraphSlice | 2026-07-19 | https://graphslice.com/blog/loops-or-graphs/ | 동시대 커뮤니티/회사 블로그 | Steinberger 7월 18일 게시물의 문구·시각·당시 모호한 해석; 기술 증거로는 사용 안 함 |
| Peter Steinberger's Loops or Graphs Tweet (2026) | AI Builder Club | 2026-07-28/29 | https://www.aibuilderclub.com/blog/graph-engineering-peter-steinberger | 추적 블로그 | 게시물이 “Graph Engineering”을 coin하지 않았다는 반론과 더 이른 유사 표현 주장; 최초성은 미확정 |
| Loops, Graphs, and the Layer That Matters | iii.dev | 2026-07-21 | https://iii.dev/blog/loops-graphs-and-the-layer-that-matters/ | 실무 논평 | vocabulary churn 및 “새 paradigm이 아니다”라는 반론의 동시대 증거 |
| Graph Engineering, Explained | V12 Labs | 2026-08-17 | https://www.v12labs.io/blog/2026-08-17-graph-engineering-explained | 실무 블로그 | 7~8월 실무 정의·신규성 논쟁; 유효성 증거로는 사용 안 함 |
| Proof-or-Stop | Huang et al. | 2026-07-16 | https://arxiv.org/abs/2607.14890 | arXiv preprint | evidence-gated loop, termination/budget의 loop engineering 사례 |
| Stop Hand-Holding Your Coding Agent | 연구 저자군 | 2026-07 | https://arxiv.org/abs/2607.00038 | arXiv preprint | prompt→context→harness→loop 서사와 loop가 prompt를 대체하지 않는다는 구분 |
| LoopsBench | Li et al. | 2026-07-31 | https://arxiv.org/abs/2608.00267 | arXiv preprint | harness에서 loop 평가로 확장되는 동시대 연구 흐름 |

## C. Graph Engineering 대표 원 연구

| 제목 | 저자/기관 | 날짜/상태 | URL | 사용 주장 |
|---|---|---:|---|---|
| An LLM Compiler for Parallel Function Calling | Kim et al. | ICML 2024 | https://arxiv.org/abs/2312.04511 | plan을 dataflow DAG로 compile, dependency-ready 병렬 dispatch |
| GPTSwarm: Language Agents as Optimizable Graphs | Zhuge et al. | ICML 2024, peer-reviewed | https://proceedings.mlr.press/v235/zhuge24a.html | agent computational graph의 node/edge 최적화 |
| Automated Design of Agentic Systems | Hu, Lu, Clune | ICLR 2025 | https://arxiv.org/abs/2408.08435 | code-defined agent workflow search |
| AFlow: Automating Agentic Workflow Generation | Zhang et al. | ICLR 2025 | https://openreview.net/forum?id=z5uVAKwmjf | executable workflow code를 LLM-guided search 대상으로 취급 |
| Plan-over-Graph | Zhang et al. | 2025 preprint | https://arxiv.org/abs/2502.14563 | dependency graph 위 parallelizable agent schedule |
| DyFlow | 연구 저자군 | NeurIPS 2025 | https://arxiv.org/abs/2509.26062 | intermediate feedback에 따른 runtime operator subgraph 조정 |
| EvoFlow | Zhang et al. | 2025 preprint | https://arxiv.org/abs/2502.07373 | inference 중 workflow 후보의 evolution |
| FlowSteer | Li et al. | 2026 preprint | https://arxiv.org/abs/2605.11514 | planning signal 조작이 dependency/replanning을 공격할 수 있음 |
| Magentic-One | Microsoft Research | 2024 preprint | https://arxiv.org/abs/2411.04468 | orchestrator delegation, Task/Progress Ledger, replanning |
| G-Designer | Zhang et al. | ICLR 2025 | https://arxiv.org/abs/2410.11782 | 성능·비용·robustness를 고려한 communication topology 설계 |
| DyTopo | 연구 저자군 | 2026 preprint | https://arxiv.org/abs/2602.06039 | round별 semantic need/supply 기반 sparse communication rewiring |
| PatchBoard | Zhang, Shi, Wang | 2026 preprint | https://arxiv.org/abs/2605.29313 | schema/role/invariant 기반 shared-state patch 검증 |
| MemTX | 연구 저자군 | 2026 preprint | https://arxiv.org/abs/2607.23929 | tentative write, belief commit, provenance, cascading repair |
| The Log is the Agent | 연구 저자군 | 2026 preprint | https://arxiv.org/abs/2605.21997 | event-sourced reactive graph, replay/fork |
| Why Do Multi-Agent LLM Systems Fail? (MAST) | Cemri et al. | NeurIPS 2025 D&B | https://proceedings.neurips.cc/paper_files/paper/2025/hash/b1041e52d3be19f0a9bc491657488e4a-Abstract-Datasets_and_Benchmarks_Track.html | system design, inter-agent misalignment, task verification failure taxonomy |
| MultiAgentBench | Zhu et al. | ACL 2025 | https://aclanthology.org/2025.acl-long.421/ | topology-sensitive collaboration/competition 평가의 한 예 |

## D. 공식 agent framework 문서

| 문서 | 기관 | 확인 버전/날짜 | URL | 사용 주장 |
|---|---|---:|---|---|
| LangGraph Graph API overview | LangChain | 2026-08-28 확인 | https://docs.langchain.com/oss/python/langgraph/graph-api | StateGraph, node/edge, conditional route, Command, dynamic routing |
| LangGraph Interrupts | LangChain | 2026-08-28 확인 | https://docs.langchain.com/oss/python/langgraph/interrupts | checkpointer/thread resume, human gate, node 재실행과 idempotent side effect 주의 |
| AutoGen GraphFlow | Microsoft | 2026-08-28 확인, experimental | https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/graph-flow.html | sequential/parallel/conditional/loop agent graph와 exit condition |
| CrewAI Flows | CrewAI | v1.15.17 | https://docs.crewai.com/v1.15.17/en/concepts/flows | event-driven start/listen/router, parallel start, typed state, persistence/resume/fork, token metrics |
| OpenAI Agents SDK orchestration | OpenAI | 2026-08-28 확인 | https://openai.github.io/openai-agents-python/multi_agent/ | agents-as-tools(manager)와 handoff 패턴 |
| OpenAI Agents SDK handoffs | OpenAI | 2026-08-28 확인 | https://openai.github.io/openai-agents-python/handoffs/ | typed metadata, input filter, run-local transfer, authorization/guardrail 경계 |
| OpenAI Agents SDK tracing | OpenAI | 2026-08-28 확인 | https://openai.github.io/openai-agents-python/tracing/ | LLM/tool/handoff/guardrail/custom event trace/span |
| OpenAI Agents SDK testing | OpenAI | 2026-08-28 확인 | https://openai.github.io/openai-agents-python/testing/ | deterministic provider-neutral orchestration test utility 존재 |

## E. Durable workflow/data orchestration 공식 문서

| 문서 | 기관 | 확인 버전 | URL | 사용 주장 |
|---|---|---|---|---|
| Temporal Workflow | Temporal | 2026-08-28 | https://docs.temporal.io/workflows | durable execution/replay 기반과 activity boundary 비교 |
| Airflow Dags | Apache Airflow | 3.3.0/3.3.1 | https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html | DAG task dependency, retry/timeout, topology 안정성 권고 |
| Airflow Architecture | Apache Airflow | 3.3.1 | https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/overview.html | scheduler/worker, branching/trigger rule, XCom, pools |
| Prefect Flows | Prefect | v3 docs | https://docs.prefect.io/v3/concepts/flows | Python flow/task, state/retry/concurrency/deployment |
| Dagster Op Graphs | Dagster | current docs | https://docs.dagster.io/guides/build/ops/graphs | op/graph composition과 data dependency |

## F. 고전 이론·표준

| 제목 | 저자/기관 | 날짜 | URL | 자료 유형/사용 주장 |
|---|---|---:|---|---|
| Kommunikation mit Automaten / Communication with Automata | Carl Adam Petri | 1962 (영역본 1966) | https://edoc.sub.uni-hamburg.de/informatik/volltexte/2010/155/ | 박사논문; concurrency와 information flow를 표현하는 Petri-net 계보 |
| A Universal Modular ACTOR Formalism for Artificial Intelligence | Hewitt, Bishop, Steiger | IJCAI 1973 | https://www.ijcai.org/Proceedings/73/Papers/027B.pdf | 원 논문; actor/message 기반 병렬·모듈 실행 |
| Statecharts: A Visual Formalism for Complex Systems | David Harel | 1987, peer-reviewed | https://doi.org/10.1016/0167-6423(87)90035-9 | hierarchy, concurrency, communication을 갖는 state machine 확장 |
| Complexity Results for HTN Planning | Erol, Hendler, Nau | 1994 tech report / 1996 journal | https://drum.lib.umd.edu/items/de8aba70-7f9a-4e32-bf8a-31b6a8f4a5a5 | task network decomposition과 계획 복잡도 |
| BPMN 2.0.2 | Object Management Group | 2013 | https://www.omg.org/spec/BPMN/2.0.2/ | event, gateway, human task, error/compensation의 표준 선행 모델 |
| Workflow Patterns | van der Aalst et al. | 지속 자료 | http://www.workflowpatterns.com/ | sequence, split/join, cancellation 등 workflow control pattern 비교 |

## G. 평가 자료(대표)

| 자료 | 날짜/상태 | URL | 사용 주장 |
|---|---:|---|---|
| SWE-bench | ICLR 2024 | https://arxiv.org/abs/2310.06770 | individual coding trajectory/end-task benchmark는 graph 구조 기여를 직접 분리하지 못함 |
| MultiAgentBench | ACL 2025 | https://aclanthology.org/2025.acl-long.421/ | multi-agent collaboration/competition과 topology 평가 |
| MAST | NeurIPS 2025 | 위 C 절 URL | multi-agent failure annotation/dataset |
| Who & When | ICML 2025 | https://arxiv.org/abs/2505.00212 | agent·step 수준 failure attribution |
| FlowSteer | 2026 preprint | https://arxiv.org/abs/2605.11514 | dynamic workflow의 adversarial structural risk |
| Graph Engineering survey Table 1/§7 | 2026 preprint | https://arxiv.org/abs/2608.21156 | TaskBench, TPS-Bench, SILO-BENCH, MAS-BENCH, SyncBench, MASEval, BenchAgent 등 범주와 현 공백 |

## 출처 해석 원칙

- 핵심 정의와 taxonomy는 survey **저자 주장**으로, 실제 framework 기능은 해당 **공식 문서**로, 계산/조직 모델의 선행성은 **원 논문·표준**으로 분리했다.
- 블로그는 2026년 7~8월 용어 확산과 논쟁의 증거로만 사용했다.
- GitHub 동반 저장소의 conference/preprint 표기는 원 링크와 대조했으며, 저장소 포함 자체를 품질 인증으로 취급하지 않았다.
- 개별 연구의 benchmark 개선을 Graph Engineering 전체의 독립 검증이나 실무 채택 증거로 일반화하지 않았다.

