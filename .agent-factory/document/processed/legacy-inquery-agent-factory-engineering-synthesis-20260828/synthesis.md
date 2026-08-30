# Agent Factory 엔지니어링 조사 종합

> 기준일: 2026-08-28  
> 성격: 임시 Inquiry 산출물. 구현 결정, Specification, Project Skill, 정식 프로젝트 사실이 아니다.  
> 표기: **[관찰]** 저장소 또는 원자료에서 직접 확인, **[근거 결론]** 관찰과 조사 자료를 결합한 판단, **[가설]** 실험 전에는 개선으로 단정할 수 없는 제안.

## 0. 질문, 경계, 결론

이 Inquiry는 에이전트 그래프 엔지니어링, 에이전틱 코딩, 에이전틱 엔지니어링, 루프 엔지니어링, 컨텍스트 엔지니어링, 프롬프트 엔지니어링의 겹침을 정리하고 현재 Agent Factory에 호환되는 채택 후보를 찾는다. 제품 코드·Skill·테스트·Specification·canonical fact는 수정하지 않았고, 테스트나 검증 명령도 실행하지 않았다.

핵심 결론은 세 가지다.

1. **[관찰] Agent Factory는 이미 “작은 정적 실행 그래프 + 내구 런타임 + 외부 제한 루프”의 핵심을 상당히 구현했다.** Main→Work→Review, Work↔Review revision, Human test-evidence gate가 명시적 상태 전이이고, exact-session resume, async dispatch, immutable binding, heartbeat/timeout/reconcile, independent Review, finite budgets가 기계적으로 뒷받침된다.
2. **[근거 결론] 현재의 가장 큰 공백은 더 많은 Agent나 동적 그래프가 아니라 측정 가능한 실행 계약이다.** run/loop 상태에는 모델·sandbox·해시와 사건 로그가 있으나, prompt/context 구성 manifest, 단계별 latency/token/cost/tool 결과 요약, 실제 과업 eval set과 회귀 gate는 없다. 따라서 “그래프를 확장”하기 전에 현재 경로를 관측하고 비교할 수 있어야 한다.
3. **[가설] 가장 작은 다음 구현 slice는 기존 의미론을 바꾸지 않는 `run manifest + derived metrics + offline trajectory fixture`의 얇은 수직 절편이다.** 새 Agent, 병렬 fan-out, graph DB, 장기 memory, 자동 prompt/topology 최적화 없이도 현재 Work/Review 한 건의 입력·버전·전이·시간·결과를 재현 가능하게 묶고, 고정 fixture로 계약 위반과 비용 대리 지표를 비교할 수 있다. 효과는 실험으로 확인해야 하며 우선순위와 구현 권한은 Human에게 남긴다.

## 1. 여섯 용어의 정규화

여섯 용어는 경쟁하는 유행어가 아니라 서로 다른 설계 확대경이다.

| 용어 | 정규화된 설계 객체 | 고유 질문 | Agent Factory에 주는 별도 기여 |
|---|---|---|---|
| 프롬프트 엔지니어링 | 한 모델 호출/turn의 지시, 예시, 형식 계약 | “모델에게 무엇을 어떻게 요구할까?” | 역할 계약, 금지사항, 실패/기권 조건, compact JSON과 role receipt schema를 더 명료하고 평가 가능하게 만든다. |
| 컨텍스트 엔지니어링 | 추론 시점에 조립되는 지침·요청·파일·상태·도구·provenance 전체 | “무엇을 언제 보여 주고, 무엇을 격리·압축·참조할까?” | 큰 요청은 파일로 넘기고 compact envelope만 전달하는 현재 설계를 설명하며, 향후 context manifest·JIT evidence·summary pointer의 필요성을 제시한다. |
| 루프 엔지니어링 | 한 목표를 향한 반복 행동·피드백·검증·중단 계약 | “어떻게 수렴하며 언제 멈출까?” | Work→Review→revision의 maker/checker 분리, finite budgets, unchanged-finding circuit, Human escalation을 설계한다. |
| 에이전틱 코딩 | 코드 저장소에서 문제 이해→편집→검토/검증→handoff를 수행하는 특화 agent system | “코드 변경 과업을 어떻게 안전하고 유용하게 끝낼까?” | bounded Work, unrelated change 보존, static independent Review, Human-led tests, patch/source-state binding이라는 도메인 계약을 제공한다. |
| 에이전틱 엔지니어링 | identity·tool·sandbox·workflow·eval·governance를 포함한 전체 lifecycle/운영 체계 | “agent를 조직과 운영 시스템 안에서 어떻게 책임 있게 배치할까?” | Main/Human 소유 결정, sandbox, idempotency, audit state, break-glass, approval/test boundary, 운영 SLO·eval 공백을 함께 본다. |
| 에이전트 그래프 엔지니어링 | task/agent/capability/state/evidence 관계와 실제 scheduling/guard/join/recovery 의미론 | “여러 loop·사람·도구·상태를 어떤 topology와 typed edge로 연결할까?” | 현재 암묵적 상태기계를 명시적 graph view로 문서화하고, 향후 fan-out/join 또는 capability routing을 도입할 때 필요한 조건을 제공한다. |

포함 관계를 지나치게 단순화하면 다음과 같다.

```text
prompt ⊂ context
model call + tool harness + state + stop = agent loop
coding loop ⊂ agentic coding
agentic coding ⊂ agentic engineering lifecycle
여러 loop/tool/human/evidence의 관계와 상태 전이 = agent graph
```

**[근거 결론]** Loop와 graph는 대체 관계가 아니다. 한 Work 또는 Review session은 내부적으로 loop이고, `agent_loop.py`는 두 session과 Human gate를 연결하는 작은 graph runtime이다. 또한 “graph”는 graph database, knowledge graph, GNN, GraphRAG와 다르다. 후자는 필요할 경우 context/data capability가 될 수 있으나 현재 Agent Factory의 실행 문제를 저절로 해결하지 않는다.

## 2. 현재 상태 지도

### 2.1 완전히 존재하며 보존할 관행

| 관행 | 상태 | 저장소 근거 | 판단 |
|---|---|---|---|
| 주소 지정 가능한 managed Agent | 완전 | `skills/agent/SKILL.md:16-29`, `skills/agent/scripts/agent_exec.py:919-979` | platform sub-agent 대신 exact `codex exec` session을 저장·resume하는 프로젝트 결정이 계약과 명령 생성 양쪽에 있다. |
| 비동기 dispatch와 non-blocking 수거 | 완전 | `skills/agent/SKILL.md:61-72,108-125`; `agent_exec.py`의 `spawn_worker`, `inbox`, `status`, `result` | submit/send가 background worker를 시작하고 ACK를 즉시 반환하며 unread terminal result를 조회한다. |
| 안전한 파일 handoff | 완전 | `skills/agent/SKILL.md:46-58`; `agent_exec.py:95-174,312-424` | anchored path, symlink 거부, 크기 제한, atomic write, request SHA-256, exact result path schema가 있다. |
| liveness와 복구 구분 | 완전 | `skills/agent/SKILL.md:75-103`; `agent_exec.py:860-917,1050-1199,1541-1598` | accepted/started/heartbeat/completed, start/turn/heartbeat timeout, started 여부 기반 retry, stale reconcile이 분리된다. |
| dispatch idempotency | 완전 | `skills/agent/SKILL.md:118-122`; `agent_exec.py:736-850` | immutable dispatch tuple의 exact repeat만 deduplicate하고 충돌은 fail closed 한다. |
| 독립 maker/checker | 완전 | `references/main.md:37-43`, `work.md`, `review.md`; Work/Review receipt schema | Work와 Review가 다른 exact session이고 Review는 read-only/static이며 stable finding ID를 쓴다. |
| finite semantic loop | 완전 | `references/loop.md:21-91,108-114`; `agent_loop.py:162-186,885-1019` | Work/Review/revision/elapsed/unchanged-finding 예산과 terminal reason이 있다. 무제한 model promise loop가 아니다. |
| artifact/evidence binding | 완전(해당 경로) | `references/loop.md:37-80,116-148`; `agent_loop.py:885-985,1179-1257` | original request, Work run, Review run, finding ledger, Git fingerprint, post-review test evidence를 해시와 identity로 결합한다. |
| Human-owned test/risk 결정 | 완전 | `references/main.md:23-35`, `work.md:26-37`, `review.md:17-25`, `loop.md:10-17` | Work/Review는 테스트하지 않고 Main/Human만 별도 승인·실행·evidence 첨부한다. |
| 지식/상태 종류 분리 | 완전 | `AGENTS.md:5-44`, `skills/inquery/SKILL.md:17-46`, `specification`/`gather` contracts | runtime, temporary Inquiry, Specification, paired Project Skill, gathered source를 다른 소유 영역에 둔다. |

### 2.2 부분적으로 존재하는 관행

| 관행 | 상태 | 존재하는 부분 | 부족한 부분 |
|---|---|---|---|
| typed execution graph | 부분 | role, run, dispatch, receipt, loop phase, finding, acceptance binding은 typed JSON/state transition이다. | task/capability/authority/data edge를 한 view로 표현하는 schema와 generic join/fan-out은 없다. 현재 고정 Work/Review topology에는 필수 공백이 아니다. |
| structured prompt contract | 부분 | common/role Skill, request path, result path, strict compact schema, Work/Review receipt schema가 있다. | 실제 turn에 어떤 instruction/context 파일 버전과 해시가 조립됐는지 manifest가 없고 prompt 변경 단위의 eval identity가 없다. |
| context engineering | 부분 | 큰 body를 파일로 handoff하고 역할이 필요한 저장소 evidence만 읽도록 하며 상태 종류를 분리한다. | token budget, JIT evidence selection record, compaction provenance, stale-context 신호, context item ACL/authority label은 없다. |
| observability | 부분 | raw `events.jsonl`, heartbeat, state timestamps/status/error, result/inbox가 있다. | 단계별 duration, queue/start/turn latency, token/cost/tool-call counts, outcome taxonomy dashboard/summary, trace correlation export가 없다. Heartbeat는 semantic progress가 아니다. |
| safety control plane | 부분 | filesystem sandbox 선택, path/symlink defense, exact authorization contract, started-turn replay 금지, Human gate가 있다. | tool/network/secret/egress별 policy, capability registry, risk-class routing, credential delegation log는 이 plugin 자체에서 구현하지 않는다. prompt 금지만으로 보안 경계가 되지 않는다. |
| evaluation | 부분 | contract tests가 receipt binding, dispatch collision, budget, loop finding lifecycle, evidence binding 등의 정적/단위 동작을 규정한다. | 실제 Agent task corpus, trajectory rubric, adversarial prompt/context set, repeated-trial reliability, cost/latency baseline, model-change regression gate는 없다. 이 Inquiry는 테스트를 실행하지 않았다. |
| rollback/compensation | 부분 | cancel, fail-closed, Git source fingerprint, pre-start-only replay 정책이 있다. | 외부 side effect ledger·compensating transaction은 없다. 현재 계약이 외부 action을 별도 Human 승인으로 막으므로 즉시 범위는 제한적이다. |
| context continuity | 부분 | exact session resume와 Inquiry workspace가 장기 continuity를 제공한다. | session context health/size를 직접 측정하지 않으며 structured compaction이나 session migration 정책이 없다. 프로젝트 결정상 임의 fresh replacement는 허용되지 않는다. |

### 2.3 부재하며 “부재 자체가 결함”은 아닌 항목

| 항목 | 현재 상태 | 해석 |
|---|---|---|
| parallel fan-out/fan-in | 부재 | 현재 기본 작업은 한 mutable Git workspace와 single-writer Work이므로 병렬 writer는 충돌 위험이 크다. 독립 read-only Inquiry나 별도 artifact branch가 입증될 때만 검토한다. |
| dynamic/evolving topology | 부재 | 실행 중 graph mutation이나 다음 run에 topology를 자동 승격하지 않는다. 공개 연구도 persistent self-evolution의 통합 이득을 확립하지 못했다. |
| agent capability graph/router | 부재 | 현재 role은 Main/Work/Review/Inquiry로 고정되어 단순하다. task 분포와 routing 오류 자료 없이 capability inference를 추가하면 복잡성만 늘 수 있다. |
| durable semantic/episodic memory | 부재 | session history, files, Inquiry workspace는 있지만 자동 장기 기억 저장소는 없다. poisoning, stale fact, 삭제·권한 문제를 피하는 보수적 상태다. |
| graph DB/knowledge graph/GraphRAG/GNN | 부재 | 실행 orchestration 문제와 직접 동일하지 않다. 관계 질의나 graph-native data workload가 측정되지 않았다. |
| automatic prompt/topology optimizer | 부재 | held-out eval과 production outcome이 먼저 필요하다. judge 과적합과 분포 이동 위험이 더 크다. |
| OpenTelemetry GenAI export | 부재 | raw event는 있지만 vendor-neutral span/metric export는 없다. 관측 요구와 privacy schema가 정해진 뒤 조건부 투자다. |

## 3. 채택 후보 상세

아래 후보는 현재 제약을 유지한다. “작은 변경 표면”은 권한이 아니라 향후 구현 시 예상되는 최소 경계다.

### A. Agent 행동 계층

| 후보 | 해결 문제 | 근거/합리성 | 최소 호환 변경 표면 | 의존성·위험 | 검증 신호 | 가역성 |
|---|---|---|---|---|---|---|
| A1. 역할별 입력/출력 계약 checklist 표준화 | prose 계약의 누락, Human-owned decision을 Agent가 추정하는 위험 | prompt/context 조사: 목표·근거·기권·schema가 문구보다 중요. 현재 role contract와 receipt가 이미 기반 | `references/*.md`의 중복 없는 공통 checklist와 receipt 설명 정합화; runtime 의미론 불변 | 지나친 지시 길이와 중복 충돌. checklist를 추가하면 context cost가 증가할 수 있음 | 고정 fixture에서 invalid receipt, scope expansion, missing limitation 비율 감소 | 높음; 문서만 되돌릴 수 있음 |
| A2. “관찰/결론/가설/제약” 결과 표지 | Inquiry/Review 결과에서 사실과 추측 혼합 | Inquiry 계약과 연구 보고서가 이미 이 분리를 요구 | Inquiry result guidance 또는 optional result template. 강제 canonical schema는 피함 | 템플릿 경직성, 결과 장황화 | 샘플 result에서 provenance 없는 단정과 unresolved decision 누락률 | 높음 |
| A3. Review 독립성 profile 기록 | 같은 모델/비슷한 context의 상관 오류를 “독립 Agent”만으로 과소평가 | research는 maker/checker 분리를 지지하지만 같은 model family의 correlated error를 경고 | Review dispatch/receipt metadata에 actor model/version profile reference를 기록; decision 로직은 불변 | 모델 정보를 얻지 못하거나 민감/가변적일 수 있음 | model/profile별 blocking escape와 disagreement rate 비교 | 높음 |

### B. 런타임 계층

| 후보 | 해결 문제 | 근거/합리성 | 최소 호환 변경 표면 | 의존성·위험 | 검증 신호 | 가역성 |
|---|---|---|---|---|---|---|
| B1. immutable run manifest | 실행 결과가 어떤 contract/context/model/runtime 설정으로 만들어졌는지 한 파일에서 재구성하기 어려움 | context engineering은 prompt/model/schema/version 동시 기록을 권고. 현재 state에 일부만 산재 | run 디렉터리에 append-free `manifest.json`: request/role-contract/plugin/model/sandbox/schema hashes, parent dispatch/loop binding, created time. 기존 state/response 불변 | Codex 내부 prompt 전체나 tokenization은 관찰 불가; 비밀/원문 복제 금지, hash와 safe metadata만 사용 | 동일 입력의 manifest completeness 100%, hash mismatch fail-closed, 기존 lifecycle 결과 동일 | 높음; optional artifact로 시작 가능 |
| B2. derived phase metrics | raw event/state가 있어도 queue/start/turn/result latency와 retry amplification을 비교하기 어려움 | agentic engineering/graph research는 success뿐 아니라 latency, cost, retry, resume correctness를 요구 | 기존 state/events/heartbeat에서 `metrics.json` 파생: accepted→started, started→terminal, attempts, event bytes/count, cancellation, terminal code. model token/cost는 실제 event가 있을 때만 | timestamp clock/partial event, privacy. 없는 token/cost를 추정하면 안 됨 | fixture에 대한 deterministic metric, unknown 명시율 100%, p50/p95 baseline 산출 가능 | 높음 |
| B3. structured terminal/error taxonomy 문서화 | 실패 원인과 semantic revision을 같은 retry로 오해할 위험 | runtime은 이미 started/pre-start, sandbox failure, heartbeat timeout을 구분 | 기존 error codes와 allowed transition을 machine-readable catalog 또는 reference로 노출 | catalog drift | 모든 terminal state가 한 code로 분류되고 unknown code가 CI fixture에서 탐지 | 높음 |
| B4. context-size health signal | exact resume가 길어질수록 stale/redundant context 가능, 그러나 임의 fresh session은 금지 | prompt/context 조사와 loop 조사 모두 context growth를 경고; current contract는 exact resume를 요구 | event가 제공하는 input token/context warning만 수집해 status에 “unknown/healthy/threshold” 표시; 자동 reset 금지 | API/event에 데이터가 없을 수 있음, threshold가 모델별 | revision count/context signal과 invalid outcome 상관 비교; 자동 행동 0건 | 높음 |

### C. loop/graph orchestration 계층

| 후보 | 해결 문제 | 근거/합리성 | 최소 호환 변경 표면 | 의존성·위험 | 검증 신호 | 가역성 |
|---|---|---|---|---|---|---|
| C1. 현재 topology의 명시적 graph/state-transition view | 코드는 강한 graph 의미론을 갖지만 운영자에게 phase/edge/guard가 분산되어 보임 | graph engineering의 첫 단계는 새 graph engine보다 node/edge/termination 명시 | `references/loop.md` 또는 generated static schema에 node, typed transition, guard, artifact binding을 표현; runtime은 현행 코드 | 문서와 코드 drift. 생성/정적 검사 방식 필요 | 모든 실제 phase/terminal code가 graph view에 매핑, orphan state 0 | 높음 |
| C2. join/fan-out eligibility gate | “multi-agent가 좋다”는 이유로 병렬화를 과도하게 도입할 위험 | graph 조사: 독립 branch, partial failure 보존, join ownership이 있을 때만 graph 확대 | 구현 전 Inquiry checklist: independent artifacts, single-writer 없음, join rule, budget, failure semantics, evidence binding | 잘못된 분해는 context 중복·merge 충돌·비용 증가 | pilot에서 wall time 이득과 quality/cost가 single-agent baseline보다 개선될 때만 채택 | 높음; gate 자체는 문서 |
| C3. bounded read-only Inquiry fan-out pilot | 서로 독립적인 다중 자료 조사에서 직렬 시간이 길 수 있음 | fan-out은 독립 read-only artifact에서 가장 낮은 위험. 다만 현재 managed session 원칙 유지 필수 | **후속 실험에 한해** 여러 managed Inquiry sessions를 async dispatch하고 Main이 typed provenance join; platform sub-agent 금지 유지 | source 중복, contradictory summaries, reviewer burden, four-way cost | 동일 질문의 single Inquiry 대비 coverage, contradiction detection, wall time, token/cost(관찰 가능할 때), synthesis review time | 높음 |
| C4. generic graph runtime | 다양한 topology를 요구하는 미래 과업 | 현재 loop는 특화된 작은 graph. generic schema는 확장성을 줄 수 있음 | later: versioned node/edge/guard/artifact schema와 durable scheduler adapter | 큰 복잡성, 기존 mature workflow 의미론 재구현, migration 위험 | 최소 2~3개의 서로 다른 승인된 topology가 현재 코드에서 중복/제약을 보일 때만 | 중간 |

### D. context/prompt construction 계층

| 후보 | 해결 문제 | 근거/합리성 | 최소 호환 변경 표면 | 의존성·위험 | 검증 신호 | 가역성 |
|---|---|---|---|---|---|---|
| D1. context manifest와 provenance pointer | Agent가 어떤 파일을 실제 입력 근거로 삼았는지 request/result만으로 불명확 | JIT context, authority/freshness, summary→original pointer가 권장됨 | request envelope에 optional `contextItems[]` sidecar: path/hash/type/authority/scope/required flag. 원문 복제 금지 | manifest 작성 부담, mutable file race, path privacy | sampled runs의 required evidence hash coverage와 stale/missing detection | 높음 |
| D2. instruction precedence/conflict check | AGENTS, Skill common/role, request 사이 충돌 또는 stale instruction 가능 | context 조사: 데이터와 명령 분리, 계층 명시. 현재 build prompt는 읽을 파일만 지정 | dispatch 전에 known contract paths와 request boundary의 identity/hash만 확인; 의미 conflict 자동 판정은 하지 않고 명시적 충돌 표지만 | 자연어 conflict detector의 false positive. LLM 판정을 security gate로 쓰지 않음 | deliberate conflicting fixture에서 fail/escalate, 정상 fixture false-positive율 | 높음 |
| D3. JIT evidence budget experiment | 긴 context에 모든 파일을 넣으면 위치/잡음 비용, 너무 적으면 근거 누락 | Lost-in-the-Middle 및 coding agent의 search-first 권고; 현재는 “필요한 evidence만 inspect”라는 행동 계약뿐 | 작은 eval에서 full-pack vs path manifest+JIT read 비교; runtime 기본값 변경 없음 | event token 데이터 부재, task sample 편향 | task success, evidence recall, invalid citation, wall time, input tokens(실측 가능 시) | 높음 |
| D4. structured compaction proposal | long-running exact session의 context rot | 요약+원본 pointer와 typed decision state가 연구 권고 | later: Agent가 compaction artifact를 제안하고 runtime/Human이 검증·참조; session ID는 유지 | 요약 손실, 승인/부정/숫자 왜곡, Codex session 내부 state 제어 한계 | source-pointer drill-down 성공, critical fact preservation set, regression | 중간 |

### E. evaluation 계층

| 후보 | 해결 문제 | 근거/합리성 | 최소 호환 변경 표면 | 의존성·위험 | 검증 신호 | 가역성 |
|---|---|---|---|---|---|---|
| E1. Agent Factory trajectory fixture set | unit contract는 강하지만 실제 역할 행동·scope discipline·handoff 품질 회귀를 측정하지 못함 | agentic coding/engineering은 final output 외 trajectory, tool, recovery, Human burden을 평가하라고 권고 | 별도 eval fixtures: bounded work request, Human decision, injected source text, stale heartbeat, unchanged finding, required evidence. 테스트 실행 권한 정책은 Human이 별도로 결정 | gold label 비용, model nondeterminism, 공개 benchmark 일반화 한계 | pass@1이 아니라 반복 success distribution, scope violation, invalid transition, review edit minutes | 높음 |
| E2. baseline ladder | 새 feature 효과를 feature 없는 현재 경로와 비교하지 못함 | graph/agent 연구는 same model/budget baseline을 요구 | `manual/current single Work+Review/candidate` 3단계 paired comparison 설계 | run cost, task contamination | 성공당 wall time·Human review minutes·defect escape·retry amplification | 높음 |
| E3. adversarial context/safety set | prompt injection, malicious tool text, path traversal 등 공격 회귀가 일부 unit path에만 한정 | context/agentic engineering의 반복 위험 | 로컬 synthetic request/document fixtures; network나 external action 없이 expected refusal/escalation만 평가 | 공격셋이 실제 위협을 대표하지 못할 수 있음 | instruction takeover 0, unauthorized action intent 0, provenance loss rate | 높음 |
| E4. LLM judge 보조 평가 | 자유형 result 품질을 대규모로 보기 어려움 | judge는 유용하지만 편향·상관 오류가 있음 | deterministic schema/path checks 우선, judge는 blind Human anchor sample로 보정한 보조 점수 | self-preference, style bias, data leakage | Human agreement/confusion matrix와 drift; judge 단독 release gate 금지 | 높음 |

### F. safety와 observability 계층

| 후보 | 해결 문제 | 근거/합리성 | 최소 호환 변경 표면 | 의존성·위험 | 검증 신호 | 가역성 |
|---|---|---|---|---|---|---|
| F1. authority/capability 선언 sidecar | `sandbox` 하나로 tool/network/path/side effect 권한을 충분히 설명하지 못함 | least privilege, typed tool gateway, planner≠authority가 공통 근거 | run manifest에 requested/actual sandbox와 declared external/destructive/test authorities를 명시; runtime이 실제 enforce할 수 없는 항목은 `contract-only` 표시 | 거짓 안전감. enforcement 여부를 반드시 분리 | contract-only와 enforced field 혼동 0, unauthorized request escalation rate | 높음 |
| F2. event redaction/retention policy | raw JSONL/result가 민감 prompt/tool data를 담을 수 있음 | agentic engineering/OTel 연구는 observability와 data minimization을 함께 요구 | 수집 field catalog, size/retention/access 정책; 원문 기본 복제 금지. 실제 삭제는 별도 Human 정책 필요 | 디버깅 정보 손실, 기존 runtime compatibility | 민감 fixture leak 0, 필요한 incident field completeness | 중간~높음 |
| F3. lifecycle SLO view | liveness가 있어도 semantic health와 운영 병목을 한눈에 보기 어려움 | heartbeat는 process liveness일 뿐 progress 아님; agent metrics stack 권고 | B2 metrics를 status/inbox에서 요약: queue/start/turn/terminal, retry, cancellation, Human escalation reason | dashboard가 correctness를 가장할 수 있음 | stuck-run detection time, unknown terminal reasons, operator diagnosis time | 높음 |
| F4. side-effect ledger/compensation | 미래 외부 action에서 at-least-once/retry가 중복 효과를 낼 수 있음 | distributed workflow/graph/agentic engineering의 핵심 통제 | **외부 action을 실제 허용하는 별도 기능이 승인될 때만** idempotency key, pre/post state, commit/compensate record | 도메인별 compensation 불가능, 권한 확대 위험 | duplicate external effects 0, compensation drill 성공률 | 낮음~중간; 외부 통합 뒤에는 migration 비용 큼 |

## 4. 우선순위

### 4.1 지금 유지·표준화

다음은 이미 존재하며, 새 연구 유행 때문에 약화하면 안 된다.

- managed addressable `codex exec` session과 exact ID resume; platform sub-agent로 대체하지 않는다.
- Main/Human의 product·risk·test 권한, Work/Review의 테스트 금지, 별도 post-Review evidence gate.
- Work와 독립 Review의 서로 다른 session, static/read-only Review, stable finding lifecycle.
- async ACK/inbox, per-session serialization, dispatch idempotency, atomic anchored file handoff.
- accepted/started/heartbeat/completed 구분, pre-start-only replay, timeout/cancel/reconcile.
- finite Work/Review/revision/time/unchanged-finding budgets와 machine stop reason.
- request/receipt/run/source-state/test-evidence의 exact binding과 fail-closed behavior.
- runtime/Inquiry/Specification/Project Skill/Gather 상태 소유권 분리.

표준화 범위는 문서-코드 간 같은 이름, terminal/error taxonomy, 현재 loop graph view까지다. 기능 확대가 아니다.

### 4.2 작은 다음 실험

1. **Run manifest + derived phase metrics (B1+B2).** 현재 의미론을 바꾸지 않고 관측 기반을 만든다.
2. **작은 trajectory fixture와 baseline ladder (E1+E2).** 실제 Agent 행동을 5~10개의 대표 fixture로 반복 측정한다. 실행 여부와 명령은 Human이 별도 승인해야 한다.
3. **Context manifest/JIT A/B (D1+D3).** 동일 과업에서 full context와 path/hash+JIT를 비교한다.
4. **Adversarial context fixture (E3).** source document 속 지시가 role/request authority를 탈취하지 않는지 측정한다.
5. **현재 loop topology의 machine-readable/static view (C1).** 코드와 계약의 orphan transition을 찾는 용도로만 시작한다.

### 4.3 이후 조건부 투자

- read-only Inquiry fan-out은 독립 branch와 typed join이 명확하고 single Inquiry baseline 대비 coverage/latency/비용 개선이 관찰될 때.
- generic graph runtime은 최소 두세 개의 승인된 서로 다른 topology가 현재 특화 loop에서 실제 중복·제약을 만들 때.
- structured compaction은 exact resume session에서 context health 악화가 실측되고 critical fact preservation eval이 있을 때.
- OpenTelemetry export는 소비자, privacy/retention schema, 필요한 span이 정해질 때.
- capability router는 task distribution과 routing ground truth가 축적될 때.
- side-effect ledger는 Agent Factory가 외부 action을 수행하도록 별도 승인된 뒤, 도메인별 idempotency/compensation을 설계할 때.

### 4.4 거절 또는 유예

- **unbounded Ralph/self-referential loop:** finite budget, external verifier, Human stop 경계와 충돌한다.
- **model-authored completion phrase를 terminal authority로 사용:** 현재 receipt/binding/Review gate보다 약하다.
- **managed session을 platform sub-agent나 `resume --last`로 대체:** 주소 지정·재개·감사라는 명시적 프로젝트 결정과 충돌한다.
- **Work/Review가 자율 테스트:** Human-led test authorization과 역할 분리에 충돌한다.
- **병렬 Agent가 같은 mutable workspace를 동시 편집:** single-writer/independent Review와 충돌하고 merge ownership이 없다.
- **승인 없는 self-modifying/evolving graph:** 증거 수준이 낮고 versioned evaluation/approval/rollback이 없다.
- **graph DB/GraphRAG/GNN을 orchestration 해법으로 선도입:** 문제–표현 적합성 증거가 없다.
- **자동 장기 memory 쓰기:** provenance/TTL/권한/poisoning/삭제 정책과 eval이 없다.
- **자동 prompt/topology optimization을 먼저 도입:** held-out eval과 baseline이 없어 과적합을 판별할 수 없다.
- **모든 tool call에 일률적 approval을 붙여 안전을 주장:** approval fatigue를 만들며 실제 least-privilege enforcement를 대체하지 못한다.

## 5. 가장 작은 일관된 다음 구현 slice

### 제안: “측정 가능한 managed turn” 수직 절편

**[가설]** 다음 slice는 graph 확장이 아니라 현재 한 managed turn을 재현·비교 가능하게 만드는 것이다.

최소 구성:

1. run 생성 시 기존 request/state/response/receipt와 나란히 immutable `manifest.json`을 둔다.
2. manifest는 원문 prompt나 secret를 복제하지 않고 `agent/role/run`, request hash, common/role contract path+hash, plugin version, selected model/sandbox, response/receipt schema hash, dispatch/loop parent binding만 기록한다.
3. terminal publish 시 기존 events/state에서 `metrics.json`을 파생한다. accepted→started, started→terminal, attempts, cancel/reconcile, event count/bytes, terminal/error code를 기록하고 token/cost는 관찰 가능한 실제 필드가 없으면 `unknown`으로 둔다.
4. 5~10개 synthetic offline fixture로 manifest completeness, hash mismatch, phase metrics, scope/human-decision/Review-binding trajectory를 확인하는 평가 설계를 작성한다. **실제 테스트 실행은 이 Inquiry가 승인하지 않으며 Human이 별도로 선택한다.**
5. 기존 compact terminal JSON, result/receipt contract, session ID, retry, loop transition은 바꾸지 않는다.

이 slice가 먼저인 이유:

- prompt/context/graph/eval/observability 후보가 공통으로 필요한 run identity와 baseline을 제공한다.
- 새 Agent나 topology 없이 선택적 artifact 두 개로 시작할 수 있어 가역성이 높다.
- “좋아졌다”는 주장을 하지 않고, 다음 실험에서 성공·시간·재시도·context 버전을 비교할 수 있게 한다.
- 기존 explicit constraints와 충돌하지 않는다.

진입/중단 기준:

| 기준 | 최소 신호 |
|---|---|
| 호환성 | 기존 state/result/receipt/loop semantics가 불변이고 manifest/metrics를 읽지 않는 소비자도 동작 |
| 완전성 | fixture의 모든 terminal run에 필수 metadata가 있고 unknown은 명시됨 |
| 무결성 | contract/schema/request hash 변경이 탐지되고 symlink/path 안전 규칙 재사용 |
| 개인정보 | prompt/result 원문을 새 artifact에 복제하지 않음 |
| 유용성 | 운영자가 raw JSONL 전체를 읽지 않고 queue/start/turn/retry/terminal을 설명 가능 |
| 중단 | manifest maintenance가 drift하거나 metrics가 실제 결정을 바꾸지 못하면 optional artifact를 제거 |

**Human 미결정:** 이 slice의 제품 우선순위, metadata 보존 기간, model identifier 공개 범위, 어떤 fixture를 실제로 실행할지, 테스트 명령과 acceptance threshold는 Human 소유다.

## 6. 모순과 충돌

1. **fresh context 권고 vs exact-session resume.** 일부 long-running agent 연구는 context reset의 이점을 보고하지만 Agent Factory는 same Inquiry/Work/Review에 exact session resume를 명시한다. 따라서 자동 새 session으로 바꾸지 않는다. 먼저 context health를 관찰하고, 문제가 확인되면 same-session compaction 또는 Human decision을 연구한다.
2. **agentic coding의 자동 test loop vs Human-led tests.** 일반 coding agent 문헌은 test feedback을 핵심 loop로 보지만 이 프로젝트는 Work/Review 테스트를 명시적으로 금지한다. 호환 가능한 형태는 Review 뒤 Human/Main이 별도 승인·실행한 evidence를 binding하는 현재 gate다.
3. **graph 병렬성 vs single mutable workspace.** graph 연구는 fan-out을 권하지만 한 Git workspace에 여러 writer를 두면 partial commit과 merge ownership이 불명확하다. read-only Inquiry 또는 분리된 immutable artifact에서만 먼저 실험한다.
4. **self-evolution vs 승인/감사.** topology optimizer 연구는 가능성을 보이지만 통합된 causal benefit과 safe persistent evolution은 확립되지 않았다. candidate diff→offline eval→Human approval→versioned commit/rollback 없이는 도입하지 않는다.
5. **더 많은 telemetry vs context/privacy 최소화.** raw prompt/tool/result를 모두 저장하면 디버깅은 쉬워지지만 secret·PII·retention 위험이 커진다. 최초 slice는 hash와 derived metadata 중심이어야 한다.
6. **generic graph abstraction vs 현재의 특화 loop.** 일반 schema는 멋진 통합점을 제공하지만 현재는 하나의 강하게 규정된 topology가 대부분이다. premature abstraction은 기존 fail-closed invariant를 약화할 수 있다.

## 7. 한계와 미해결 사항

- 공개 연구의 일부는 2026년 preprint·vendor engineering post이며 독립 장기 검증이 부족하다. 특히 persistent graph evolution과 multi-agent productivity는 확립된 사실이 아니다.
- 이 Inquiry는 저장소를 정적으로 읽었고 테스트, build, runtime 실행, benchmark, 비용 측정을 하지 않았다. 코드 경로의 실제 운영 성공률을 증명하지 않는다.
- raw `events.jsonl`이 제공할 수 있는 token/model/tool detail은 실제 Codex event version에 따라 다를 수 있다. 본 보고서는 없는 값을 있다고 가정하지 않았다.
- repository tests는 계약 의도를 보여 주는 정적 architecture evidence로만 보았다. pass/fail 상태를 주장하지 않는다.
- Human 업무 분포, 평균 review time, escaped defect, 실제 비용이 없어 후보 우선순위의 ROI는 계산할 수 없다.
- 네트워크·secret·tool 권한은 Codex host/runtime와 배포 환경에도 의존한다. plugin 문서와 filesystem sandbox만으로 전체 security posture를 결론 내릴 수 없다.

## 8. 추적성 표

| 결론/후보 | 조사 근거 | 저장소 근거 |
|---|---|---|
| Loop는 graph의 node/subgraph이며 graph는 관계·join·state를 설계 | `.agent-factory/inquery/agent-graph-engineering/report.md:40-98,177-254`; adjacent `sources.md` | `skills/agent/references/loop.md`; `skills/agent/scripts/agent_loop.py` |
| dynamic/self-evolving graph의 이득은 미확립 | `agent-graph-engineering/report.md:254-310,364-390` | 자동 topology mutation 코드 없음; versioned Human gate는 loop evidence에 한정 |
| 일반 graph DB/GNN/GraphRAG와 agent execution graph는 분리 | `agent-graph-engineering/report.md:20-39`; `graph-engineering/report.md`; `ai-non-rag-report.md`; `ai-latest-report.md:174-188` | runtime은 filesystem JSON state/dispatch로 실행하며 graph data engine 의존 없음 |
| bounded maker/checker loop가 무제한 Ralph loop보다 적합 | `loop-engineering-20260828/evidence-and-observations.md:10-170` | `references/work.md`, `review.md`, `loop.md`; receipt/finding ledger |
| coding agent는 model+ACI+harness 결합 결과이며 Human review 부담도 측정해야 함 | `.agent-factory/inquery/agentic-coding-20260828/report.md:17-84,112-198,232-263`; `sources.md` | bounded Work/Review, Human test boundary, current lack of task eval |
| agentic engineering은 identity/sandbox/state/eval/governance 전체 lifecycle | `.agent-factory/inquery/agentic-engineering-20260828/report.md:17-107,129-210,281-329`; `sources.md` | `skills/agent/SKILL.md`, Main role, runtime timeouts/sandbox/state |
| prompt는 context 일부이고 task contract/schema가 핵심 | `.agent-factory/inquery/prompt-context-engineering-20260828/report-ko.md:5-46,55-106`; `source-catalog.md` | common+role contract, `build_prompt`, exact response/receipt JSON schema |
| JIT context, provenance, compaction+original pointer, versioned eval 필요 | `prompt-context.../report-ko.md:91-177,203-258` | file handoff와 request hash는 존재; context manifest/token budget/eval corpus는 부재 |
| exact managed session/async/atomic/heartbeat/reconcile는 보존 대상 | local research 전체의 durable workflow 권고 | `skills/agent/SKILL.md:16-155`; `agent_exec.py` |
| run manifest와 phase metrics가 가장 작은 다음 slice | 위 context/eval/observability 근거를 현재 공백에 적용한 **가설** | state/events/heartbeat에 원자료가 있으나 종합 manifest/derived metric은 없음 |

주요 local source catalog:

- `.agent-factory/inquery/agent-graph-engineering/sources.md`
- `.agent-factory/inquery/graph-engineering/sources.md`
- `.agent-factory/inquery/graph-engineering/ai-non-rag-sources.md`
- `.agent-factory/inquery/graph-engineering/ai-latest-sources.md`
- `.agent-factory/inquery/agentic-coding-20260828/sources.md`
- `.agent-factory/inquery/agentic-engineering-20260828/sources.md`
- `.agent-factory/inquery/prompt-context-engineering-20260828/source-catalog.md`

## 9. 가장 작은 유용한 후속 Inquiry

제품 구현 전에 한 가지 후속 Inquiry만 한다면, **현재 managed Work→Review 경로의 5~10개 대표 task에 대한 관측 schema와 paired baseline 실험 설계**가 가장 작고 유용하다.

후속 질문은 다음으로 제한한다.

> “현재 event/state에서 안정적으로 추출 가능한 필드는 무엇이며, run manifest/phase metrics가 실제로 Human 진단 시간과 trajectory 비교 가능성을 개선하는가?”

산출물은 (a) 필드 availability matrix, (b) 개인정보/보존 threat model, (c) 5~10개 fixture와 rubric, (d) current-vs-manifest paired protocol, (e) 중단 기준이다. 테스트 실행과 제품 채택은 별도 Human 승인으로 남긴다.

