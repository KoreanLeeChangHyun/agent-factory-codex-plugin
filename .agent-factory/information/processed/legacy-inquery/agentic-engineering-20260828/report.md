# 에이전틱 엔지니어링 공개 웹 종합 조사

> 상태: AI가 작성한 비정제 Inquiry 작업물. 조사 기준일 2026-08-28 (Asia/Seoul). 공개 원문을 범주별로 확인했으나 웹 전체의 완전 열거가 아니며, 제품·규제·표준·벤치마크는 계속 변한다. 아래에서 **관찰**, **분석**, **제안**, **한계**, **Human-owned 결정**을 구분한다.

## Executive summary

**관찰.** `agentic engineering`은 아직 단일 표준어가 아니다. 2026년 공개 용례는 적어도 세 갈래다. IBM은 전문 엔지니어가 AI agent를 SDLC에서 오케스트레이션·감독하는 방식으로 정의한다 ([IBM](https://www.ibm.com/think/topics/agentic-engineering)). ICSE 2026의 첫 Agentic Engineering workshop은 목표지향 자율 시스템 자체의 설계·개발·운영과 이를 production-ready로 만드는 엄격한 software engineering을 연구대상으로 둔다 ([ACM](https://doi.org/10.1145/3786167)). DORA는 정책, 내부 데이터·플랫폼, 작은 batch, 사용자 중심성과 rollback을 조직 역량으로 묶는다 ([DORA 2025](https://cloud.google.com/blog/products/ai-machine-learning/introducing-doras-inaugural-ai-capabilities-model)). 즉 요청서의 세 용례—agent가 엔지니어링을 함, agentic system을 공학함, 인간·agent 조직을 재설계함—은 실제 사용을 잘 포착하지만 합의된 규격 정의는 아니다.

**분석.** 가장 유용한 포괄 정의는 다음이다. **에이전틱 엔지니어링은 확률적·도구사용 agent를 (a) 엔지니어링 수명주기의 실행 주체로 사용하고, (b) 그 agentic system을 신뢰성 있게 설계·평가·운영하며, (c) 이를 수용하도록 팀·플랫폼·통제를 재설계하는 실무·학문 영역**이다. agentic coding은 구현 중심 하위영역이고, agent engineering은 보통 (b)에 좁게 쓰이며, AI engineering은 데이터·모델·ML 시스템 전반을 포함해 더 넓지만 agent의 위임·행동 loop를 필수로 하지 않는다.

**강한 결론.** 모델 능력만으로 production outcome을 설명할 수 없다. 목표/수용기준, 도구 인터페이스, 컨텍스트, 상태·재시도, 최소권한 identity, sandbox/egress, approval, deterministic verifier, trace/eval, rollback을 포함한 harness와 조직 운영역량이 함께 필요하다. Anthropic도 workflow(코드가 경로를 결정)와 agent(모델이 경로와 도구를 동적으로 결정)를 구분하며, 복잡성은 측정 가능한 이득이 있을 때만 추가하라고 한다 ([원문](https://www.anthropic.com/engineering/building-effective-agents)).

**혼재된 결론.** 생산성은 작업·전문성·도구세대·검토비용에 따라 방향까지 바뀐다. 제한 과제 Copilot RCT는 55.8% 빠름을, 자기 저장소에 익숙한 숙련 OSS 개발자 RCT는 19% 느림을 보였다 ([Peng et al.](https://arxiv.org/abs/2302.06590), [METR](https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf)). 공급자 demo, benchmark pass rate, 생성 LOC를 end-to-end 가치로 읽을 수 없다.

**아직 모르는 것.** 장기 결함률·보안사건·유지보수성, review queue의 한계, novice 학습, 대규모 multi-agent의 순효과, 물리 엔지니어링의 안전·재현성, agent 간 identity/delegation 표준의 상호운용성과 책임법리는 독립적 장기 근거가 부족하다.

## 1. 용어 taxonomy와 경계

| 용어 | 주된 대상/행위 | agent 필수? | 이 조사에서의 관계 |
|---|---|---:|---|
| deterministic workflow | 코드가 고정 경로·분기를 실행 | 아니오 | 예측 가능성이 높은 기준선; agent와 혼합 가능 |
| AI assistant/copilot | 사람이 다음 행동을 선택, AI가 제안 | 아니오 | delegation 이전 단계 |
| delegated agent | 목표·경계 안에서 모델이 다음 도구/단계를 선택 | 예 | 에이전틱 엔지니어링의 기본 실행 단위 |
| autonomous/long-running agent | 비동기·지속 상태·복구를 갖고 장시간 수행 | 예 | 더 큰 blast radius와 운영 요구 |
| agentic coding | 저장소 탐색–편집–실행–테스트 loop | 예 | implementation 및 일부 review/test의 하위영역 |
| software engineering agent | 실제 issue/SDLC task를 수행하는 연구·제품 agent | 예 | 적용 객체의 이름 |
| agent engineering / agentic systems engineering | 목표지향 agent의 설계·평가·운영 discipline | 예 | 두 번째 용례; ICSE workshop 정의와 가장 가깝다 |
| AI engineering | 모델·데이터·RAG·MLOps·AI product 전체 공학 | 아니오 | 더 넓은 인접 discipline; agency는 선택사항 |
| autonomous engineering | 자율 소프트웨어 또는 CAD/EDA/실험실까지 포함하는 표현 | 대체로 | 물리영역에서 쓰이나 자동화와 LLM agent를 혼동하기 쉽다 |
| agent-native operating model | 역할·프로세스·platform·governance를 agent를 전제로 설계 | 예 | 세 번째 용례; 아직 규범적 표현이 많다 |

### 반드시 분리할 축

- **copilot → delegated → autonomous**: 사람의 행동 선택이 모델로 옮겨갈수록 승인·중단·복구가 중요해진다.
- **single → multi-agent**: 역할 분리는 병렬성과 전문화를 주지만, 공유 오판·충돌·비용·책임 모호성을 추가한다. multi-agent가 기본적으로 우월하다는 독립 근거는 없다.
- **local interactive → remote asynchronous → production-embedded**: 후자로 갈수록 durable state, queue, scoped service identity, egress, audit, incident response가 필요하다.
- **model → harness/system → organization capability**: benchmark는 이 셋을 고정하지 않으면 비교가 깨진다.
- **SDK/framework / product / protocol / observability**: LangGraph는 runtime, Codex는 end-user+runtime 제품, MCP/A2A는 wire/interaction 규약, OpenTelemetry는 telemetry 관례다. 서로 대체재가 아니다.

### 에이전틱 코딩과의 관계

코딩 agent의 전형적 loop—repo 검색, patch, shell/test, 실패 수정, diff/PR—는 agentic engineering의 가장 성숙한 부분이다. 실행 가능한 테스트라는 환경 피드백이 있고 SWE-bench 같은 task set이 있기 때문이다 ([SWE-bench](https://arxiv.org/abs/2310.06770), [SWE-agent](https://arxiv.org/abs/2405.15793)). 그러나 requirements의 가치 판단, architecture trade-off, production risk acceptance, incident command는 완전 자동 verifier가 약하다. 그러므로 “코딩 성능이 SDLC 전체 자율성으로 자연스럽게 확장된다”는 주장은 아직 가설이다.

## 2. 역사와 기술적 전환점

| 시기 | 관찰된 이정표 | 엔지니어링 의미 |
|---|---|---|
| 이전 토대 | expert system, workflow/BPM, CI/CD, RPA, multi-agent systems, MLOps/SRE | LLM 이전에도 자율/자동화 공학은 존재; 새로움은 자연어 모델의 범용 판단·도구사용 |
| 2021 | GitHub Copilot preview, OpenAI Codex 기반 pair programmer ([GitHub](https://github.blog/news-insights/product-news/introducing-github-copilot-ai-pair-programmer/)) | completion의 대중화 |
| 2022–2023 | ReAct의 reasoning/action 교차, Reflexion의 언어적 피드백, SWE-bench의 실제 issue 평가 ([ReAct](https://arxiv.org/abs/2210.03629), [Reflexion](https://arxiv.org/abs/2303.11366)) | 단일 응답에서 환경 feedback loop로 이동 |
| 2024 | SWE-agent/CodeAct/OpenHands, computer use, SWE-bench Verified, MCP 공개 | ACI·sandbox·tool protocol이 모델 외 성능요소로 부상 |
| 2025 | cloud/background coding agents, OpenAI Agents SDK, Google A2A, Agent Skills; long-running harness·trace grading 확대 | 로컬 대화에서 비동기 위임·상호운용·절차 패키징으로 이동 |
| 2026-08 | A2A 1.0, NIST Agent Standards Initiative/보안 RFI 분석, 장기 sandbox/checkpoint SDK, agentic SRE 사례, ICSE Agentic Engineering workshop | 제품 경쟁과 함께 identity·security·eval·운영 discipline이 제도화 중 |

MCP는 host–client–server 구조에서 resources/prompts/tools를 연결하며 host가 consent·policy를 담당한다 ([architecture](https://modelcontextprotocol.io/specification/2025-06-18/architecture)). A2A는 opaque agent 간 capability discovery, message/task/artifact, async/HITL 상호작용을 정의한다 ([1.0 spec](https://github.com/a2aproject/A2A/blob/main/docs/specification.md)). AGENTS.md는 저장소 지침의 단순 Markdown 관례이고 ([agents.md](https://agents.md/)), Agent Skills는 `SKILL.md`와 scripts/references/assets를 묶어 점진 로드하는 형식이다 ([spec](https://agentskills.io/specification)). 네 가지 모두 상호운용/컨텍스트를 개선하지만 correctness나 authorization을 자동 보증하지 않는다.

## 3. 전체 engineering lifecycle map

| 단계 | agent 입력 → 행위 → 산출물 | 권장 Human gate | 검증·대표 근거 |
|---|---|---|---|
| discovery/requirements | 인터뷰·tickets·analytics → 군집화, 모순·가정 탐색, story/acceptance criteria 초안 | 문제·우선순위·사용자 영향·완료조건 승인 | traceable requirement→test 링크, stakeholder review; 가치 판단은 자동점수로 대체 불가 |
| product planning | 목표·용량·dependency → breakdown, 일정/위험 시나리오 | roadmap·budget·commitment | 과거 추정 대비 calibration, dependency check |
| architecture/design/modeling | NFR, ADR, code/diagram → 대안 생성, threat/data-flow/model 초안 | architecture·data boundary·risk acceptance | constraint checker, simulation/prototype, ADR 독립 검토 |
| implementation/coding | spec+repo+instructions → 탐색·편집·build/test 반복 → diff/PR | scope·nontrivial diff·merge | unit/integration/type/lint, regression, reviewer; SWE-agent는 ACI 영향 확인 |
| testing/QA | spec·risk·code → test 생성, flaky 분류, UI/browser 탐색 | test oracle와 coverage risk | mutation/property/metamorphic test, hidden test, human exploratory testing |
| formal verification | model/spec/contract → invariant·proof/script 초안 | proof obligation과 assumptions | kernel/proof checker/SMT가 최종 판정; 자연어 설명은 증거 아님 |
| code review/security/compliance | diff/SBOM/policy → review finding, taint/secret/license 조사 | finding disposition·waiver | SAST/DAST/SCA, reproducible finding, two-person approval; OWASP/NIST mapping |
| CI/CD/release | PR+pipeline+change record → failure triage, release note, staged plan | signing, prod deploy, exception | hermetic CI, provenance/attestation, canary, policy-as-code, rollback rehearsal |
| operations/SRE/incident | alerts/logs/topology/runbook → correlate, hypothesis, query, bounded mitigation | novel/high-risk action, incident command | SLO/error budget, dry-run, pre/post condition, canary/rollback; Google은 L2 인간승인과 bounded L3를 보고 ([SRE](https://sre.google/resources/practices-and-processes/ai-engineering-reliable-operations/)) |
| FinOps | usage/billing/topology → anomaly·rightsizing proposal | budget·service trade-off | invoice reconciliation, workload benchmark, savings after quality normalization |
| maintenance/migration/debt | dependency/EOL/code history → inventory, codemod, compatibility repair | migration plan·deprecation | dual-run, parity test, rollback, sampled human review |
| documentation/knowledge | code/ADR/incident → docs/runbook/changelog update | externally binding docs | link checker, executable snippets, owner/freshness review |

**관찰.** GitHub Agentic Workflows는 issue triage, documentation, code quality를 비동기로 처리하되 write를 명시적으로 승인된 safe output으로 제한한다 ([GitHub](https://github.blog/ai-and-ml/automate-repository-tasks-with-github-agentic-workflows/)). Google SRE 사례는 standing human credential을 금지하고 dry-run, risk 평가, progressive authorization, kill switch를 둔다. 둘 모두 “모델이 직접 broad credential로 모든 것을 실행”하는 형태가 아니다.

## 4. 참조 아키텍처와 실행/제어 loop

```text
사람/이벤트/요구사항
  ↓ goal + constraints + acceptance + risk class
API/queue/scheduler ─ identity/delegation ─ policy/budget/rate limit
  ↓ durable run id, idempotency key, lease
orchestrator/state machine ↔ checkpoint/event store/memory/RAG
  ↓ route/plan          ↕ provenance + context filtering
model/router/planner → typed tool gateway → sandbox / SaaS / CI / prod
  ↑ observation              ↓ scoped token, egress, timeout, dry-run
  └── evaluator/verifier ← artifact/result/pre-post state
             ↓ fail/repair/escalate/stop
trace + logs + metrics + cost + audit → offline/online eval → release gate
             ↓
artifact/PR/decision proposal → Human approval → side effect/deploy
```

### 구성 원칙

1. **모델/router/planner**: task/risk별 model 선택, structured output, termination 조건을 둔다. planner 텍스트 자체는 권한이 아니다.
2. **도구/ACI**: 좁고 typed하며 결과·오류가 명확한 도구가 좋다. shell/browser/computer use는 큰 권한으로 보고 별도 sandbox/egress를 둔다.
3. **context/retrieval/memory**: authoritative source와 untrusted content를 표시하고 provenance·TTL·owner를 저장한다. scratch state, session checkpoint, durable organizational knowledge를 분리한다.
4. **state/workflow**: run/step/tool-call 상태, lease, timeout, retry budget, compensation을 명시한다. at-least-once delivery를 전제로 side effect에 idempotency key와 deduplication을 둔다.
5. **identity/permissions**: user, agent service identity, tool credential, downstream resource audience를 분리한다. MCP는 token audience binding과 token passthrough 금지를 요구한다 ([authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)).
6. **sandbox/approval**: ephemeral filesystem/process, allowlisted mounts, deny-by-default network, secret broker, time/token/CPU limit. approval UI는 실제 concrete action·diff·target·risk를 신뢰된 UI에서 보여야 한다.
7. **evaluator**: deterministic oracle 우선, model judge는 rubric·calibration·human audit를 사용한다. actor와 critic을 분리해도 공통 모델/컨텍스트로 인한 상관오류는 남는다.
8. **telemetry/policy**: model/version/prompt/tool/arguments hash/result/latency/token/cost/approval/side effect를 민감정보 최소화와 함께 trace한다. OpenTelemetry의 GenAI/agent semantic convention은 진행 중인 공통 기반이지 완성된 보증 규격이 아니다 ([OTel](https://opentelemetry.io/blog/2025/ai-agent-observability/)).
9. **failure recovery**: checkpoint/rehydration, bounded retry, circuit breaker, dead-letter queue, rollback/compensating transaction, Human escalation, global stop을 설계한다. OpenAI Agents SDK는 2026년 controlled sandbox와 snapshot/rehydration을 공식 소개했다 ([OpenAI](https://openai.com/index/the-next-evolution-of-the-agents-sdk/)).
10. **multi-agent**: delegation contract에 goal, input provenance, allowed tools, budget, expected artifact, completion/timeout, accountability를 포함한다. A2A transport 성공은 상대 agent의 신뢰성을 뜻하지 않는다.

## 5. 생태계 비교: 제품·SDK·framework·protocol·standard

대표성 기준은 (a) 공식 원문, (b) 서로 다른 계층, (c) 널리 관찰되는 설계 패턴이다. 전수 목록이나 2026-08 이후 기능 보장은 아니다.

| 항목 | 분류 | 핵심 추상화/강점 | 경계·주의 |
|---|---|---|---|
| OpenAI Agents SDK | SDK/harness | tools, handoff, guardrail, tracing, HITL, sandbox/checkpoint | 서비스·모델 변화; model judge와 trace가 correctness 보증은 아님 |
| Anthropic Claude Agent SDK/Claude Code | SDK+end-user product | tool loop, hooks/skills, subagent, permissions, MCP | 공급자 기능·권한 설정; shell/network blast radius |
| Google ADK | SDK/orchestration | model/tool/agent composition, workflow/multi-agent, Google ecosystem | 공식 사례 효능은 독립 검증과 분리 |
| Microsoft Agent Framework | SDK/runtime | AutoGen+Semantic Kernel 후속; workflow, memory, HITL, checkpoint, hosting ([docs](https://learn.microsoft.com/en-gb/agent-framework/)) | migration·preview/GA 상태를 버전별 확인 |
| AWS Strands + Bedrock AgentCore | OSS SDK+managed runtime | model/tool loop, multi-agent, runtime, identity/observability | AWS 결합과 서비스별 데이터·비용 경계 |
| LangGraph | framework/runtime | graph state, durable execution, checkpoint, streaming, HITL ([docs](https://langchain-ai.github.io/langgraph/index.html)) | 저수준 orchestration; security/quality를 대신하지 않음 |
| OpenHands/SWE-agent | OSS agent/harness | software engineering sandbox/ACI, research/eval reproducibility | 제품 운영과 benchmark harness를 구분 |
| MCP | protocol/spec | host-client-server, tools/resources/prompts, OAuth transport | agent-to-tool/context; 구현체 신뢰·tool safety는 별도 |
| A2A 1.0 | protocol/spec | agent card, message/task/artifact, async/stream/HITL, opaque interop | agent-to-agent; semantic trust, payment, liability는 미해결 |
| AGENTS.md | repo convention | build/test/style/security instructions의 scoped Markdown | 강제 schema 없음; stale/conflicting instruction 위험 |
| Agent Skills | open format | reusable instructions+scripts+references/assets, progressive disclosure | activation/tool reliability와 supply-chain review 필요 |
| OpenTelemetry GenAI | observability convention | vendor-neutral spans/metrics/attributes 방향 | sensitive prompt/tool data, 아직 진화 중 |
| NIST AI RMF/SSDF 218A/Agent initiative | governance guidance/initiative | lifecycle risk, secure development, agent security·identity 표준화 | 구체 구현·인증을 자동 제공하지 않음 |

**분석.** MCP와 A2A는 각각 “agent가 tool/data를 호출”과 “독립 agent가 task를 교환”에 초점이 다르다. Agent Skills/AGENTS.md는 wire protocol이 아니라 version-controlled procedural context다. Framework는 application control flow를, end-user product는 UX/hosting/model bundle을 제공한다. procurement에서 이 계층을 한 줄의 “agent platform”으로 비교하면 lock-in과 통제 공백을 놓친다.

## 6. 평가 프레임워크

### 지표 stack

| 층 | 질문 | 대표 지표 |
|---|---|---|
| capability | 이 분포의 task를 풀 수 있는가 | success/pass@1, calibrated confidence, task horizon |
| trajectory/tool | 올바른 상태·도구·인수를 썼는가 | valid tool-call, unnecessary step, policy violation, recovery rate |
| reliability | 반복·변형·장애에도 되는가 | variance, p50/p95 success, retry amplification, resume correctness |
| security/safety | 적대 입력과 권한 경계에서 안전한가 | injection success, exfiltration, forbidden action, approval bypass |
| efficiency | 성공 하나에 무엇을 쓰는가 | wall time, tokens, tool/compute $, queue time, p95 latency |
| human system | 사람 부담을 줄이는가 | clarification/review/edit minutes, acceptance, interruption, cognitive load |
| maintainability | 바뀐 모델·도구·코드에서 유지되는가 | regression count, instruction complexity, trace debuggability, portability |
| production outcome | 사업/서비스가 개선됐는가 | lead time, change failure, defects, SLO, incident loss, customer outcome |

### 설계

- **offline**: 실제 task distribution에서 golden/holdout/adversarial set을 version하고, model+harness+tool image+budget+seed/attempt 정책을 고정한다. exact/state verifier를 우선하고 rubric grader는 blind human sample로 보정한다.
- **trajectory eval**: final answer만 보지 말고 source 선택, tool args, privilege, redundant steps, recovery, stopping을 grade한다. Anthropic은 agent eval을 task, trial, grader, transcript/outcome 구조로 설명한다 ([2026 guide](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)).
- **online**: shadow → suggestion-only → canary → bounded autonomy 순으로 rollout하고 SLO/error budget/circuit breaker를 둔다. user outcome과 harm near-miss를 수집하되 privacy를 최소화한다.
- **red team**: direct/indirect injection, malicious tool/MCP, poisoned memory, tool output spoofing, confused deputy, secret canary, resource exhaustion, colluding agents, deceptive approval UI를 포함한다.
- **regression**: model snapshot, prompt/instruction, tool schema, retrieval index, framework, dependency, policy 변경마다 재실행한다. 평균 외 p5 task classes와 p95 cost/latency를 본다.

### benchmark 비교와 한계

| benchmark | 측정 | 유용성 | 일반화 한계 |
|---|---|---|---|
| SWE-bench/Verified/Live | issue→repo patch가 tests 통과 | end-to-end coding loop | Python/repo 편향, public contamination, test oracle 불완전 |
| SWE-Lancer | 실제 freelance IC/manager task | 경제적 규모와 full-stack | 한 시장·과거 project, private setup 재현성 |
| Terminal-Bench | container terminal task | tool/CLI/infra 능력 | image drift, timeout/compute, verifier gaming |
| RE-Bench | 8시간 ML R&D 환경과 human 비교 | 장기 open-ended 연구 | 7 tasks, AI R&D에 편중 |
| METR time horizon | human task time별 50% success horizon | 장기능력 추세 | 직업 대체시간·production outcome과 다름 |

리더보드는 model만의 순위가 아니다. scaffold, attempts/best-of-N, token/time/compute, tool image, network, setup failure 제외, contamination, evaluator error를 함께 공개해야 한다. demo success와 production outcome을 분리한다.

## 7. 위험–통제–증거 매트릭스

| 위험 | 실패 예 | 예방/탐지/복구 통제 | 확인 증거 |
|---|---|---|---|
| indirect prompt injection | issue/web/log가 agent에게 secret 전송 지시 | untrusted label, content/tool separation, egress deny, scoped secret, adversarial eval | blocked trace, canary non-egress |
| excessive agency | read task에 delete/send/deploy 가능 | 최소 기능·권한·자율성, typed safe output, risk approval | IAM diff, denied calls, approval record; [OWASP](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) |
| identity/confused deputy | user token을 downstream에 passthrough | agent identity, audience-bound short token, delegation chain, no passthrough | token aud/log, MCP conformance |
| data/secrets exfiltration | repo/customer data가 prompt/log/network로 유출 | classification, redaction, secret broker, egress, retention/region controls | DLP alert, access/log audit |
| memory/context poisoning | 악성 지침이 세션 간 지속 | provenance, signed/owner-approved durable memory, TTL, write policy, snapshot/rollback | memory diff/hash, restore drill |
| tool/MCP supply chain | server update가 tool schema/behavior 변경 | registry, pin/signature/SBOM, sandbox, schema diff, kill switch | attestation, allowlist, revocation |
| insecure output/action | generated SQL/script/config 실행 | parse/type/schema, parameterization, dry-run, invariant/precondition | verifier output, staged diff |
| multi-agent cascade | 동일 오판 복제·무한 delegation | depth/fanout/budget limit, independent verifier, circuit breaker | delegation graph, spend cap |
| availability/cost | retry loop·tool storm | timeout, retry budget+jitter, quota, idempotency, DLQ | p95 cost, duplicate-side-effect test |
| audit/privacy | CoT에 민감정보, 책임자 불명 | event-level audit, data minimization, named owner, approval separation | immutable event/retention audit |
| license/IP/provenance | 비호환 code/data 생성 | approved sources, license/SBOM scan, provenance record, human legal review | scan/attribution/waiver |
| model/vendor drift | update 후 behavior regression/EOL | pinned version where possible, eval gate, exportable state/instructions, fallback | release comparison, restore test |
| physical safety | robot/EDA output가 장비·사람 손상 | simulation/digital twin, interlock, envelope, two-person gate, emergency stop | hazard analysis, hardware interlock test |

NIST의 2026 RFI 응답 분석은 기존 cybersecurity 원칙이 여전히 유효하지만 agent에 맞게 조정돼야 한다는 광범위한 합의를 보고했다 ([NIST](https://www.nist.gov/publications/summary-analysis-responses-request-information-regarding-security-considerations-ai)). 이는 아직 세부 compliance 표준이 완성됐다는 뜻이 아니다. 법률/IP는 관할·계약·데이터 흐름에 따라 달라지므로 법적 책임·라이선스 위험 수용은 Human/legal owner 결정이다.

## 8. 조직 operating model, RACI와 승인 경계

**관찰.** DORA의 2025 AI Capabilities Model은 명확한 AI policy, 내부 context/data, 작은 batch, user-centricity, version-control safety net, internal platform을 핵심 조건으로 제시한다. agent 도입은 개인 prompt 교육만의 문제가 아니다.

**제안: 역할 재설계.** Product/engineering은 목표·수용기준과 system ownership을, platform은 sandbox/gateway/identity/eval/telemetry를, security/privacy/legal은 policy·threat model·exception을, data/ML은 model/router/RAG drift를, SRE는 runtime SLO와 incident/kill switch를 맡는다. “agent owner”는 모델 답변의 저자가 아니라 결과와 운영 risk의 accountable human이다.

| 결정/행위 | Product | Eng owner | Agent/platform | Security/legal | SRE/change owner |
|---|---|---|---|---|---|
| 문제·priority·acceptance | A/R | C | I | C | I |
| task 실행·draft artifact | C | A | R | I | I |
| architecture/data boundary | C | A/R | C | C | C |
| tool/skill/MCP 등록 | I | C | R | A/C | C |
| code review/merge | I | A/R | C | C(고위험) | I |
| production deploy | I | R | C | C | A |
| bounded auto-remediation | I | C | R | C | A |
| exception/risk acceptance | A(제품) | C | I | A(보안/법) | A(운영) |

`A`는 최종 accountable human이며 agent에 배정하지 않는다. 조직별 법적 책임에 맞게 바꿔야 한다.

### platform과 governance backlog

- approved model/tool/MCP/skill catalog, owner·version·scope·expiry·SBOM·evaluation을 관리한다.
- repository instructions는 코드처럼 review/version하며 가까운 scope가 우선하되 policy보다 높지 않게 한다.
- policy-as-code는 allowed tool/identity/network/path/side-effect/risk class를 enforce하고 exception은 만료시킨다.
- review burden을 capacity planning에 넣고 PR 크기, sampling, risk routing, independent reviewer를 설계한다.
- procurement는 data use/retention/region, model/provider change, audit export, identity, sandbox, SLA/EOL, portability, total cost를 평가한다.
- build-vs-buy는 차별화 task/eval/control plane은 내부 소유, commodity model/runtime은 교체 가능 경계로 두는 방식이 일반적 출발점이나 Human 결정이다.

## 9. 경제성·생산성 근거와 ROI

**독립/준독립 실증.** Peng et al.의 95명 제한 JavaScript 과제 RCT는 Copilot 조건이 55.8% 빠르다고 보고했다. METR의 16명·246개 실제 mature OSS task RCT는 2025년 초 AI 허용이 19% 느렸다고 보고했다(95% CI +2%~+39%). DORA 관찰연구는 개인/문서/리뷰 효과와 delivery 결과가 조직 역량에 의해 매개됨을 보여주지만 인과 RCT가 아니다. 표본, task, 비교군, 도구세대, review 범위가 달라 숫자를 합산할 수 없다.

**공급자 사례.** Google SRE, Siemens migration, Cadence EDA, vendor customer claims는 실제 architecture와 가능성을 보여주지만 대조군·selection·측정 정의가 제한된다. 공급자 주장을 market-wide ROI로 승격하지 않는다.

### 비용/ROI 계산 프레임

`순가치 = (절약 인간시간 × fully-loaded 시간가치 + 품질/매출/위험회피 가치) - (모델+tool+compute+storage+network 비용 + 설정/대기 + 검토/수정 + platform/governance + 교육/전환 + 실패·incident 기대손실)`

`성공당 비용 = 전체 기간 비용 / human-accepted, production-valid 성공 수`

task class별 baseline과 treatment를 무작위/교차 비교하고 median/p90 lead time, first-pass acceptance, human edit/review minutes, escaped defect/security finding, rollback, success당 비용을 최소 4–8주 측정한다. 병렬 agent는 wall-clock을 줄여도 compute·review queue를 늘릴 수 있다. LOC, token 가격, seat adoption은 outcome이 아니다.

## 10. 소프트웨어 밖의 적용

| 영역 | 확인 가능한 적용 | 근거 수준·한계 |
|---|---|---|
| EDA/hardware | AlphaEvolve가 evaluator와 진화 탐색으로 data center scheduling, chip design, kernel/algorithm 최적화에 사용됨 ([DeepMind](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)); Cadence는 2026 virtual engineer/AI super agents를 발표 ([Cadence](https://newsroom.cadence.com/press-releases/press-release-details/2026/Cadence-Unveils-Industrys-First-Fully-Autonomous-Virtual-Engineer-for-Chip-Design-06-01-2026/default.aspx)) | DeepMind은 자동 evaluator가 명확한 문제에 강함; Cadence는 vendor announcement. signoff, PPA, fabrication safety와 human accountability가 남음 |
| CAD/CAE/manufacturing | digital twin에서 simulation workflow와 robot fleet를 시험하는 vendor 생태계 ([NVIDIA](https://www.nvidia.com/en-us/industries/manufacturing/)) | 주로 공급자/partner 사례; open-ended physical change의 독립 성과 부족 |
| robotics | perception/planning/tool action, digital twin→bounded deployment | sim-to-real gap, sensor/actuator fault, real-time·functional safety 때문에 software agent보다 gate가 강해야 함 |
| chemistry/materials | self-driving lab이 AI decision+coordinator software+robotics로 closed-loop optimization; mobile robots의 실제 합성 사례 ([Matter review](https://www.sciencedirect.com/science/article/pii/S2590238524003229), [Nature](https://doi.org/10.1038/s41586-024-08173-7)) | 특정 reaction/instrument·scalar objective에 한정, bespoke integration·안전·재현성; “자율 발견”과 동일시 금지 |
| scientific/ML research | AlphaEvolve, RE-Bench, literature/code/experiment agent | 자동 verifier가 가능한 영역에 편중; novelty·causality·reproducibility는 expert gate 필요 |
| civil/chemical/process | planning/simulation/document/compliance assist 가능 | 공개 agentic production outcome이 희박; safety-critical physical actuation을 과장하지 않음 |

**결론.** 물리 영역은 실제 적용이 존재하지만 대부분 좁은 objective, structured simulator/EDA/lab API, 높은 자동검증 가능성에 기대고 있다. 일반 자연어 agent가 전체 물리 엔지니어링 수명주기를 자율 수행한다는 강한 근거는 없다.

## 11. 성숙도 모델과 30/60/90일 playbook — 규범적 제안

| 수준 | 업무/자율성 | 필수 통제 | 승급 증거 |
|---|---|---|---|
| L0 금지/비관리 | shadow AI, 결과 불명 | inventory, temporary freeze on high-risk actions | owner·data-flow 파악 |
| L1 assistant | read/summarize/draft, 사람이 실행 | policy, approved accounts, logging, no secrets | quality baseline, no material side effect |
| L2 delegated sandbox | small code/test/docs task, PR까지 | sandbox, scoped tools, eval, mandatory review | task-class success·review cost·security gate |
| L3 async workflow | queue/checkpoint/retry, bounded write | identity, idempotency, safe output, SLO/on-call | resume/rollback/chaos drill, p95 cost |
| L4 bounded production agent | well-defined low-risk auto action | runtime risk engine, canary, circuit breaker, kill switch | statistically sustained production SLO, incident review |
| L5 adaptive ecosystem | multi-agent/cross-org/physical autonomy | delegation trust, continuous assurance, external audit | 아직 일반 권고 불가; domain-specific safety case 필요 |

### 30일

1. 3–5개 task class와 baseline(time, quality, review, cost)을 정한다.
2. data/tool/identity flow와 threat model, prohibited actions, named accountable owner를 만든다.
3. read-only 또는 sandbox pilot, 30–100개 internal eval, injection/secret tests를 구축한다.
4. 한 model/product 구매가 아니라 artifact/trace export와 rollback을 확인한다.

### 60일

1. 한 팀에서 작은 delegated PR/analysis workflow를 운영하고 review time까지 측정한다.
2. ephemeral sandbox, scoped service identity, egress/secret broker, versioned instructions/skills, OTel-style trace를 platform paved road로 만든다.
3. model/harness/tool update regression과 failed-run triage, kill switch drill을 수행한다.

### 90일

1. evidence가 양수인 task class만 async로 확대하고 write/deploy는 risk-tier approval을 둔다.
2. canary/shadow, SLO/error budget, cost budget, incident/rollback runbook, quarterly catalog review를 운영한다.
3. executive review에서 net ROI, escaped defects, security near-miss, human burden, vendor dependency를 함께 판단한다.

**Human-owned 결정.** 어느 단계까지 자율성을 허용할지, 허용 데이터·공급자, error budget, 법적 책임, workforce 변화, physical/production risk 수용은 이 Inquiry가 선택하지 않는다.

## 12. 역할별 학습 경로

- **모든 엔지니어**: deterministic workflow vs agent, ReAct/tool loop, Git/diff/test/rollback, prompt injection·least privilege, evidence 읽기를 익힌다.
- **software/product engineer**: acceptance criteria→small task→agent execution→test/evidence→review를 반복하고 repo instruction·skill을 version한다. SWE-agent/bench 한계로 harness를 이해한다.
- **agent/ML engineer**: model routing, tool schema, context/RAG, state/checkpoint, eval dataset/grader calibration, drift, cost를 학습한다.
- **platform/SRE**: queue/lease/idempotency, sandbox/container, identity/token audience, telemetry/SLO, chaos/rollback/kill switch를 소유한다.
- **security/privacy/legal**: OWASP agent threats, MCP/A2A trust boundary, data retention/provenance/SBOM/license, red-team과 approval UX를 다룬다.
- **manager/procurement**: DORA capability, task-level experiment, total-cost/lock-in, review capacity, change management를 학습하고 속도 주장보다 outcome을 요구한다.
- **physical/domain engineer**: simulator/EDA/lab verifier와 hazard analysis를 먼저 설계하며 domain signoff와 interlock을 agent에게 위임하지 않는다.

## 13. Anti-patterns와 실패 모드

1. “최신/큰 모델이면 된다”: tool/context/identity/eval/organization을 누락한다.
2. 고정 workflow를 agent라 부르거나, 반대로 모든 분기를 LLM에 맡긴다.
3. broad human credential, ambient secret, unrestricted egress로 autonomy를 얻는다.
4. 자연어 완료 선언·critic agent·benchmark pass를 독립 검증으로 착각한다.
5. multi-agent를 조직도처럼 늘리고 shared state, budget, termination, merge ownership을 두지 않는다.
6. stale memory/instruction/skill/MCP를 검증 없이 신뢰한다.
7. retry로 side effect를 중복하고 idempotency/compensation을 두지 않는다.
8. 모든 tool call approval로 안전하다고 믿어 approval fatigue와 deceptive dialog를 만든다.
9. 생성량/seat/token만 측정하고 review·defect·incident·customer outcome을 숨긴다.
10. vendor case study와 independent evidence, demo와 production, software와 physical safety를 섞는다.
11. agent가 만든 코드/설계를 사람이 이해·소유하지 못한 채 merge/deploy한다.
12. maturity level을 구매 제품 이름으로 정의하고 승급 증거를 요구하지 않는다.

## 14. 결론, 모순, 한계, 후속 Inquiry

### 근거가 강한 결론

- workflow와 model-directed agent는 다른 control regime이며 후자는 latency/cost/compounding error를 늘린다.
- coding·tool use·structured environments에서 유의미한 능력이 확인됐지만 model+ACI+harness가 결합된 결과다.
- 최소권한, sandbox, explicit approval, deterministic verification, trace/eval, rollback은 반복되는 공식·학술 근거다.
- MCP/A2A/AGENTS.md/Skills/OTel은 서로 다른 계층의 상호운용 기반이며 안전·정확성을 단독 보장하지 않는다.
- 실제 생산성은 task/user/system에 이질적이므로 내부 controlled measurement가 필요하다.

### 혼재된 결론

- multi-agent/long-running 방식이 단일 agent보다 순생산성이 높은지.
- 생성 속도 증가가 delivery throughput·stability·maintainability로 이어지는지.
- model judge/agent critic가 인간 검토를 얼마나 줄일 수 있는지.
- agent-native 조직이 역할을 대체하는지, 고판단·review/platform 역할을 늘리는지.
- EDA/chemistry/vendor 사례가 다른 물리 도메인에 일반화되는지.

### 아직 모르는 것과 연구 공백

- 1–3년 escaped defect/security/maintenance와 ownership 효과.
- 대형 사설 multi-repo, regulated environment, novice/education의 독립 장기 RCT.
- cross-agent identity/delegation, liability, audit semantics의 실전 상호운용.
- memory poisoning·tool supply-chain 공격의 표준화된 production benchmark.
- physical agent의 near-miss/incident 공개 자료와 safety case 비교.
- 인간 review capacity가 병렬 agent scaling에 만드는 실제 병목.

### 조사 한계

공개 웹과 접근 가능한 원문만 사용했다. 2026-08-28이라는 미래 지향 스냅샷에서 검색 색인·문서 갱신일이 불안정한 자료가 있다. 유료 논문은 abstract/공개 metadata 범위로 제한됐고, private enterprise failure와 계약·가격은 거의 공개되지 않는다. software evidence가 압도적으로 많아 civil/mechanical/physical 영역은 비포화다. 기존 `agentic-coding-20260828` Inquiry는 탐색 단서로만 보았고 중요한 웹 주장은 원문에 다시 연결했다.

### 가장 작은 유용한 후속 Inquiry

한 조직·한 저장소·3개 task class를 정해 4주간 **human-only vs assistant vs delegated-agent**를 교차 배정하고, 완료시간·review/edit minutes·defect/security·success당 비용·사용자 outcome을 수집하는 내부 pilot 설계 Inquiry가 가장 작고 유용하다. 조직 맥락이 없으면 일반 웹 조사를 더 넓히는 것보다 추가 가치가 낮다.
