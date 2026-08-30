# 조사 요청: Loop Engineering 이후의 Agentic Graph Engineering

## 사용자 정정

사용자가 말한 "그래프 엔지니어링"은 그래프 데이터베이스, GNN, 지식 그래프 또는 GraphRAG가 아니다. **AI 에이전트/에이전틱 소프트웨어 엔지니어링에서 Loop Engineering 다음 단계로 2026년에 제시된 Graph Engineering**을 뜻한다.

## 핵심 기준 자료

- Feng et al., *Graph Engineering in the Era of LLM Agents: From Individual Intelligence to System Intelligence*, arXiv:2608.21156, 2026-08-21: https://arxiv.org/abs/2608.21156
- 동반 자료 저장소: https://github.com/DEEP-JLU/Awesome-Graph-Engineering

논문 전체와 저장소를 직접 확인하고, 이들이 인용하는 주요 원 논문·프레임워크도 추적한다. 조사 기준일은 2026-08-28이다.

## 조사 목표

새 용어의 정확한 정의와 등장 맥락, Loop Engineering과의 차이·포함 관계, 핵심 구성요소, 실제 구현 가능성, 기존 workflow/DAG/state-machine/multi-agent orchestration과 비교했을 때의 신규성, 현재 증거 수준과 실무 적용법을 한국어로 정리한다.

## 조사 범위

1. **기원과 타임라인**
   - prompt → context → harness → loop → graph engineering이라는 서사가 어디에서 어떻게 등장했는지
   - 2026년 7~8월 실무 담론과 2026-08-21 논문의 관계
   - 최초 주창자를 확인할 수 있으면 근거와 함께 기록하되 확인 불가능하면 단정하지 않는다.
2. **정의**
   - graph가 무엇을 나타내는지: task, agent, tool/capability, data/artifact, state, evidence, authority/gate, communication, dependency, feedback
   - node, edge, state, subgraph, cycle, fan-out/fan-in, router, join, checkpoint, termination의 의미
   - static graph, dynamic graph, evolving/self-modifying graph의 구분
   - workflow/control-flow graph와 knowledge graph의 구분
3. **Loop Engineering과의 관계**
   - loop가 해결하는 문제와 graph가 해결하는 문제
   - graph가 loop를 대체하는지, loop가 graph의 node/subgraph인지
   - 단일 agent convergence와 multi-agent/system intelligence의 차이
   - 언제 loop면 충분하고 언제 graph가 필요한지
4. **논문의 프레임워크 해부**
   - system intelligence의 정의
   - graph construction, orchestration, communication, state evolution, learning/adaptation 등의 분류
   - organization graph와 execution/task/state graph의 관계
   - 논문이 제안하는 taxonomy, design principle, application, open problem을 정확히 요약
5. **기존 개념과의 비교/신규성 검증**
   - DAG workflow, Petri net, finite state machine/statechart, dataflow, BPMN, actor model, distributed systems scheduler, blackboard architecture, HTN/planning, multi-agent systems
   - LangGraph, AutoGen GraphFlow, CrewAI Flows, OpenAI Agents SDK handoff/guardrails, Temporal/Airflow/Prefect/Dagster 등과 개념적으로 비교하되 현재 공식 문서로 실제 기능을 확인
   - 새로운 엔지니어링 discipline인지, 기존 orchestration practices의 재명명/통합인지 근거와 반론을 함께 제시
6. **설계 패턴**
   - planner–worker–reviewer, map–reduce, debate/judge, supervisor hierarchy, blackboard, event-driven, human approval gate, repair/retry subgraph
   - typed edge/outcome, state ownership, artifact/evidence passing, deterministic/non-deterministic node, permissions/budget
   - 병렬 실행과 join, partial failure, idempotency, checkpoint/resume, cancellation, compensation
7. **동적·진화형 그래프**
   - runtime task decomposition, node/edge 생성·제거·재배선
   - topology optimization/self-improvement 주장
   - 안전한 불변식, 승인, provenance, rollback, graph versioning
8. **평가와 관측성**
   - task success뿐 아니라 critical path, parallel efficiency, handoff loss, coordination overhead, token/cost, state consistency, verifier independence, recovery, human intervention
   - 기존 agent benchmark가 graph engineering을 충분히 평가하는지
   - 공개 benchmark/정량 증거가 실제로 존재하는지
9. **안전·거버넌스**
   - 권한 누출, 상호 확인에 의한 오류 증폭, shared-state corruption, deadlock/livelock, cycle 폭주, evaluator gaming, emergent collusion, provenance 단절
   - least privilege, single-writer/transaction, typed contract, external evidence anchor, budget/termination, human gate
10. **실무 적용**
   - 코딩 에이전트, 연구 에이전트, 운영/incident response, 데이터 파이프라인 등 사례
   - 최소 graph runtime/schema 예시
   - Loop에서 Graph로 전환할지 판단하는 체크리스트
   - 도입 단계와 anti-pattern
11. **성숙도와 전망**
   - 2026-08-28 현재 preprint/커뮤니티 용어라는 상태
   - 확인된 사실, 저자 주장, 분석적 추론, 전망을 명시적으로 구분
   - 6~18개월 연구·도구 전망

## 출처 규칙

- 웹 검색을 실제로 수행한다.
- 핵심 survey 원문과 동반 저장소를 우선하고, 인용된 원 논문 및 프레임워크 공식 문서를 직접 확인한다.
- 블로그·커뮤니티 자료는 용어 출현과 실무 담론의 증거로만 사용한다.
- 공급자·저자 주장과 독립 검증을 구분한다.
- 날짜, 버전, peer-review/preprint 상태를 표시한다.
- 기술적 주장 근처에 클릭 가능한 URL을 둔다.
- 이 분야가 매우 최신이므로 존재하지 않는 표준·벤치마크·채택률을 만들어내지 않는다.

## 결과물

1. `.agent-factory/inquery/agent-graph-engineering/report.md`
   - 10문장 이내 핵심 요약
   - 용어 혼동 정리
   - 기원/타임라인
   - 정확한 정의와 개념 모델
   - Loop vs Graph 비교표
   - 핵심 논문 taxonomy 해부
   - 기존 이론·도구 비교와 신규성 평가
   - 설계 패턴 및 참조 아키텍처
   - 평가 지표와 현재 증거 수준
   - 안전·실패 모드·거버넌스
   - 적용 판단표, 체크리스트, 도입 단계
   - 성숙도와 6~18개월 전망
   - 결론과 최소 후속 Inquiry
2. `.agent-factory/inquery/agent-graph-engineering/sources.md`
   - 범주별 제목, 저자/기관, 날짜, URL, 자료 유형, 어떤 주장에 사용했는지
3. 관리 런 result에는 핵심 결론, 산출물 경로, 한계와 후속 조사를 간결히 기록한다.

이것은 새롭고 독립적인 Inquiry다. 기존 `.agent-factory/inquery/graph-engineering/` 자료는 수정하지 않는다. Specification/Project Skill로 승격하거나 구현·테스트·제품 선택을 하지 않는다.
