# AI 관점의 그래프 엔지니어링: 비-RAG 기술·시스템·운영 조사

- 조사 기준일: 2026-08-28
- 조사 성격: 의사결정 전 기술 지형 조사(구현·테스트·제품 선정 아님)
- 범위 경계: RAG, GraphRAG, 문서 검색 증강 생성, 벡터 검색 기반 답변 생성은 명시적으로 제외한다.

## 요약

1. 그래프 AI의 핵심 가치는 “관계가 신호이자 제약”인 문제를 node/edge/graph 예측, 동적 사건 예측, 구조 생성, 인과 추론, 조합최적화로 직접 모델링하는 데 있다.
2. 2025–2026년의 중심축은 단일 GNN 정확도 경쟁보다 그래프 Transformer·고차/이종/동적 학습, 그래프 파운데이션 모델(GFM), 과학 그래프 생성, 그래프 월드 모델, 대규모 sampling/feature serving으로 이동했다.
3. 성숙도는 균일하지 않다. 정적 동종 GNN과 표준 예측은 **성숙**, 이종·시간 그래프와 대규모 분산 학습은 **성장**, 범용 GFM·그래프 월드 모델·LLM 기반 인과 그래프 구축은 **탐색** 단계다.
4. 그래프 모델은 tabular·sequence·전통 휴리스틱보다 항상 우월하지 않으며, 동일 정보량·동일 계산 예산·시간 누출 방지 split에서 강한 비그래프 기준선과 비교해야 한다.
5. 생산 병목은 모델보다 identity resolution, 사건 시간 의미, 음성 간선 샘플링, 파티션 경계, feature freshness, 학습–서빙 그래프 일치성인 경우가 많다.
6. 분자·재료·단백질 생성은 대칭성과 물리·화학 제약을 모델에 넣는 대표적 성장 영역이지만, 생성 타당성이 합성 가능성·실험 성공을 보장하지 않는다.
7. 지식 그래프 AI의 비-RAG 핵심은 link prediction, entity alignment, 규칙·신경기호 추론, 스키마 매핑, text-to-graph query이며, 답변 증강 파이프라인과 구분해야 한다.
8. 운영 평가는 평균 정확도 외에 시간별 안정성, subgroup 오류, calibration, 비용·지연, privacy leakage, 구조적 공격과 재현성을 함께 다뤄야 한다.
9. 12–24개월 전망은 GFM의 제한적 도메인 전이와 분산 graph store/feature store 통합은 진전되지만, 하나의 범용 그래프 모델이 모든 스키마·과업을 대체할 가능성은 낮다는 것이다.

## 1. 조사 질문, 방법과 한계

이 조사는 “AI 시스템에서 그래프가 언제 필요한가, 어떤 모델·시스템을 어떻게 평가하고 운영해야 하는가”를 묻는다. 2025–2026 학회 원문과 공식 프레임워크 문서를 우선하고, 2024 이전 자료는 기반 개념이나 장기 산업 사례에만 사용했다. 프리프린트와 공급사 벤치마크는 상태를 표시했다. 상세 서지는 `ai-non-rag-sources.md`에 기록했다.

포함 범위는 GDL/GNN, hypergraph·heterophily, heterogeneous·temporal graph, GFM, KG 학습·신경기호 추론, 그래프 생성 AI, causal graph, graph world model, graph RL/조합최적화, 대규모 학습·서빙, 벤치마크·MLOps·안전이다. 제외 범위는 검색 결과를 생성 답변에 주입하는 모든 RAG 변형이다. 문헌의 성능 숫자는 데이터·split·hardware가 달라 본 보고서에서 재랭킹하지 않았다.

성숙도 표기:

- **성숙**: 반복되는 공개 과업, 안정된 도구, 생산 패턴이 존재.
- **성장**: 유효한 연구·도구가 있으나 schema/scale별 비용과 결과가 크게 달라짐.
- **탐색**: 최근 논문 중심이며 재현성·전이성·운영 표준이 부족.

## 2. 문제–표현–모델–시스템 지도

| 층 | 핵심 질문 | 대표 객체 | 주요 실패 |
|---|---|---|---|
| 의미/데이터 | node·edge·event의 의미와 identity는 안정적인가 | typed property graph, hypergraph, temporal event stream | 중복 entity, 미래 정보, 삭제·동의 미반영 |
| 표현 | 어떤 대칭성과 관계 차수를 보존할 것인가 | adjacency, relation type, timestamp, motif, coordinates | 과도한 단순화, positional encoding 누출 |
| 학습 | 국소 메시지, 전역 attention, 규칙, 생성 중 무엇이 필요한가 | GNN, graph Transformer, neural-symbolic, diffusion | over-smoothing, over-squashing, shortcut |
| 과업 | 예측 단위와 action은 무엇인가 | node/edge/graph/event, subgraph, ranking, policy | 잘못된 negative, proxy target |
| 시스템 | 샘플·특징·embedding을 어떻게 일관되게 제공하는가 | graph store, sampler, feature store, trainer, serving | stale feature, partition skew, train–serve skew |
| 운영 | 누구에게 어떤 손실과 위험이 생기는가 | temporal/subgroup metrics, lineage, audit | 평균 지표 착시, membership leakage |

GDL은 대칭성 아래의 불변·등변 함수를 설계한다는 관점에서 grid, set, graph, manifold 모델을 잇는다. 그래프에서 permutation equivariance는 node 순서 변경에 출력 순서가 함께 바뀌게 하고, graph-level 출력은 순서에 불변이어야 한다. 이는 좌표 회전·병진 등변성이 중요한 분자/재료 모델과도 연결된다([Geometric Deep Learning](https://geometricdeeplearning.com/)).

## 3. 모델·과업군과 성숙도

| 기술군 | 원리/적합 과업 | 강점 | 한계·검증 포인트 | 성숙도 |
|---|---|---|---|---|
| message-passing GNN | 이웃 집계; node 분류, link 예측, graph 회귀 | 국소 관계 inductive bias, sparse 계산 | 깊이에 따른 smoothing, 먼 거리 정보 병목, 동질성 가정 | 성숙 |
| graph Transformer | 구조/위치 encoding과 attention | 장거리 상호작용, 표현력 | O(n²) 또는 sparse 근사, encoding 민감도, 비용 | 성장 |
| heterogeneous GNN | node/edge type별 변환과 aggregation | 다중 관계·스키마 반영 | 희소 relation, type explosion, 신규 type 전이 | 성장 |
| temporal/dynamic GNN | timestamp/event 순서, memory, temporal neighbor | churn·fraud·interaction evolution | 미래 누출, 반복 간선 shortcut, delayed label | 성장 |
| hypergraph/higher-order | 하나의 관계가 3개 이상 객체 결합 | group/co-authorship/reaction 표현 | incidence 변환 손실, 큰 hyperedge 비용, 표준 부족 | 성장 |
| neural-symbolic KG | embedding/GNN + 규칙·제약 | 설명 경로, 논리 일관성 가능 | 불완전 규칙, rule confidence, open-world 오류 | 성장 |
| GFM | 다중 graph/task 사전학습·적응 | label 효율·전이 잠재력 | schema 정렬, negative transfer, 규모 주장 재현 | 탐색 |
| graph diffusion/autoregressive generation | node/edge/coordinate를 생성·denoise | 분자·재료·단백질 설계 | validity≠utility, 3D/물리 검증 비용 | 성장(과학), 탐색(범용) |
| causal graph/graph world model | 구조적 인과·intervention·state transition | 개입·계획을 구조로 표현 | 식별 가정, latent confounder, simulator gap | 탐색 |
| graph RL/NCO | graph state에서 순차 action/policy | routing·placement 등 가변 크기 | feasibility, 최악 사례, heuristic 대비 불안정 | 성장/탐색 |

### 3.1 GNN에서 그래프 Transformer와 고차 학습으로

message passing은 강한 기본선이지만, 멀리 떨어진 node 사이 신호가 좁은 cut을 통과하면 over-squashing이 발생한다. graph Transformer는 attention과 structural/positional encoding으로 이를 완화할 수 있으나, 더 비싸며 encoding 선택이 결과를 좌우한다. NeurIPS 2025 분석은 “Transformer”라는 이름보다 구조 주입 방식과 실험 조건을 분해해서 볼 필요를 뒷받침한다([A Closer Look at Graph Transformers](https://proceedings.neurips.cc/paper_files/paper/2025/file/c7e4746c7341a2c329e43ab55714db55-Paper-Conference.pdf)).

pairwise edge로 충분하지 않은 reaction, 팀, 세션, 공동구매는 hyperedge가 자연스럽다. 2025년에는 hypergraph encoding과 heterophilic hypergraph가 별도 평가 대상으로 부상했고, DHG-Bench는 효과성뿐 아니라 효율·강건성·공정성까지 비교하려 했다. 다만 DHG-Bench는 프리프린트이므로 표준 확정으로 보지 않는다([NeurIPS 2025](https://papers.nips.cc/paper_files/paper/2025/hash/fe2223207c5801afa8c4325bd831e159-Abstract-Conference.html), [DHG-Bench](https://arxiv.org/abs/2508.12244)).

### 3.2 이종·시간 그래프

이종 그래프의 어려움은 relation 수가 아니라 의미가 다른 관계마다 observation process와 label delay가 다르다는 점이다. relation별 파라미터는 표현력을 높이는 대신 희소 type을 과적합한다. basis sharing, relation grouping, meta-path는 후보지만 business semantics가 없는 meta-path 탐색은 shortcut을 만들 수 있다.

시간 그래프에서는 다음을 분리해야 한다.

- event time, ingestion time, label availability time
- 지속 edge와 순간 event
- node/edge feature의 effective-from/effective-to
- inductive 신규 node와 transductive 기존 node

TGB-Seq는 반복 간선이 기존 벤치마크를 쉽게 만들 수 있다고 지적한다. 따라서 random edge split은 피하고, 시간 순서 split·cold-start cohort·변동성 구간별 성능을 함께 봐야 한다([TGB-Seq](https://proceedings.iclr.cc/paper_files/paper/2025/file/db5ca61dbc08cf5143c05ad2d1b0b2ca-Paper-Conference.pdf), [Temporal-Aware Evaluation](https://ojs.aaai.org/index.php/AAAI/article/view/34273)).

### 3.3 그래프 파운데이션 모델

GFM은 아직 하나의 합의된 제품 범주가 아니다. 최소한 (a) graph 구조 사전학습, (b) 여러 graph/schema 간 전이, (c) 여러 node/edge/graph 과업 적응, (d) 언어·속성 결합 중 무엇을 지원하는지 명시해야 한다. GOFA는 자기지도 사전학습·과업 유연성·graph awareness를 지향하고, GIT는 30개 이상 그래프와 5개 도메인에서 task-tree 기반 전이를 평가했다([GOFA](https://proceedings.iclr.cc/paper_files/paper/2025/hash/652c104b5b0652a03684efeaf805463b-Abstract-Conference.html), [GIT](https://proceedings.mlr.press/v267/wang25eq.html)).

2026 GraphBFF의 14억 파라미터·대규모 샘플·스케일링 결과는 방향 신호지만 프리프린트 주장이다. 모델 크기보다 schema vocabulary, pretraining leakage, target graph overlap, adapter 비용, 작은 supervised baseline 대비 이득을 먼저 검증해야 한다([GraphBFF](https://arxiv.org/abs/2602.04768)).

### 3.4 지식 그래프 AI — 비-RAG 경계

본 범위에서 KG는 답변 검색용 context가 아니라 학습·추론 대상이다. 핵심 과업은 entity resolution/alignment, relation extraction, link prediction, ontology/schema mapping, rule induction, constraint checking, multi-hop proof/path scoring, text-to-Cypher다. AAAI 2025의 rule-guided GNN은 낮거나 불균일한 규칙 신뢰도를 모델에 반영하며, 2025 neural-symbolic survey는 논리적으로 informed embedding, logical constraint, rule learning을 주요 결합축으로 정리한다([Rule-Guided GNN](https://ojs.aaai.org/index.php/AAAI/article/view/33394), [survey](https://pubmed.ncbi.nlm.nih.gov/39024082/)).

LLM은 schema mapping, KG construction, graph query generation의 parser/planner로 사용할 수 있다. 그러나 생성된 triple/query는 schema validation, referential integrity, execution sandbox, provenance, human review가 필요하다. CypherBench와 LLM4VKG는 이 영역의 평가 자원을 제공하지만, 자연어 답변 생성 성능으로 혼동하면 안 된다([CypherBench](https://aclanthology.org/2025.acl-long.438/), [LLM4VKG](https://www.ijcai.org/proceedings/2025/525)).

### 3.5 그래프 생성 AI

생성 단위는 2D topology만이 아니다. 분자에서는 원자·결합·valence, 재료에서는 원자종·3D 좌표·lattice·periodicity, 단백질에서는 residue/atom 관계와 global geometry가 결합된다. MatterGen은 원자 종류·좌표·격자에 확산을 적용하고 periodic symmetry를 모델링하며, GraphXForm은 원자·결합을 반복적으로 생성하면서 제약을 적용한다([MatterGen](https://doi.org/10.1038/s41586-025-08628-5), [GraphXForm](https://doi.org/10.1039/D4DD00339J)).

평가 사다리는 `syntax/valence validity → uniqueness/novelty → property predictor → 물리 simulation → synthesis feasibility → wet-lab` 순이어야 한다. 앞 단계 성공을 뒤 단계 성공으로 표현하면 안 된다. 단백질 diffusion과 docking 역시 구조 품질, binding proxy, 실제 affinity를 구분해야 한다([geometry-aware diffusion](https://www.nature.com/articles/s42256-025-01059-x), [RAPiDock](https://www.nature.com/articles/s42256-025-01077-9)).

### 3.6 인과 그래프, 월드 모델, RL·조합최적화

상관 graph를 causal DAG로 해석하려면 causal sufficiency, faithfulness, intervention availability 같은 식별 가정이 필요하다. NeurIPS 2025 연구는 잠재변수 아래 hard intervention에서의 동치·식별을 다뤘고, Neural Causal Graphs와 CausalGraphBench는 각각 학습 표현과 LLM graph construction 평가를 확장했다([NeurIPS 2025](https://proceedings.nips.cc/paper_files/paper/2025/hash/6ff3e124a89678abb0dd5ffc322f0700-Abstract-Conference.html), [CausalGraphBench](https://aclanthology.org/2025.acl-srw.16.pdf)). 자동 생성 causal edge에는 “원인”이 아니라 “가설” 상태가 기본이어야 한다.

Graph World Models는 node/edge 상태와 action node를 사용해 환경 전이를 모델링하고 ICML 2025의 6개 과업에서 zero/few-shot 가능성을 보고했다. 이는 유망하지만 simulation fidelity와 실제 정책 안전성은 별도 문제다([Graph World Models](https://proceedings.mlr.press/v267/feng25p.html)).

graph RL/NCO는 route, schedule, placement, allocation을 순차 구성한다. 정책은 빠른 amortized inference가 장점이지만, classical solver/heuristic의 feasibility guarantee와 최악 사례 성능을 대체하지 못할 수 있다. 비교는 동일 wall-clock, repair 비용 포함 objective, constraint violation, distribution shift, small-instance optimality gap으로 수행해야 한다. chip placement는 유명한 산업 사례이나 새로운 조직에서는 독립 기준선 검증 없이 일반화하지 않는다([Nature 2021](https://www.nature.com/articles/s41586-021-03544-w), [2025 routing review](https://doi.org/10.1016/j.tre.2025.104278)).

## 4. 대규모 학습·서빙 아키텍처

권장 논리 흐름은 다음과 같다.

`원천 event/snapshot → identity·schema·temporal validation → versioned graph/feature store → split manifest → sampler → trainer → registry → batch/online inference → decision system → outcome/incident feedback`

중요 계약:

1. **Graph snapshot 계약**: node/edge ID namespace, schema version, event-time cutoff, 삭제·동의 tombstone, lineage hash.
2. **Sampling 계약**: fanout, relation/time constraints, negative population, seed, replacement 여부를 artifact로 저장.
3. **Feature 계약**: 정의·owner·freshness SLA·availability time·offline/online 변환 동일성.
4. **Model 계약**: graph/schema/split/sampler/code/container/checkpoint의 결합 버전.
5. **Serving 계약**: 신규 node 정책, missing neighbor fallback, latency budget, abstention, batch/online parity.

| 프레임워크/연동 | 적합점 | 운영상 확인사항 |
|---|---|---|
| PyTorch Geometric | PyTorch 생태계, sampler/graph store/feature store 분리, 분산 학습 | 버전 호환, custom op, partition·RPC 장애 |
| DGL/GraphBolt | item→negative→subgraph→feature fetch 데이터 파이프라인 | sampler semantics, CPU/GPU overlap, feature cache 일관성 |
| cuGraph-PyG/WholeGraph | GPU graph analytics·sampling, 분산 feature memory | GPU topology, spill/remote access, RAPIDS 호환 |
| GraphStorm | 대규모 분산 GNN application scaffold | AWS 중심 운영 가정, version pinning; 공급사 속도 주장 독립 검증 |
| Jraph | JAX 연구 코드 이해·기존 자산 유지 | 공식 저장소가 2025-05-21 archived; 신규 핵심 의존은 신중 |
| Neptune ML | managed graph export→SageMaker/DGL 흐름 | export snapshot, IAM, 재학습·비용·vendor boundary |
| Neo4j GDS | property graph 내 pipeline형 node/link/graph ML | 지원 algorithm/scale, in-database memory projection, 재현 artifact |

DGL GraphBolt은 sampling과 feature fetch 단계를 명시적으로 구성하며, PyG 분산 문서는 graph/feature store와 sampler 구성을 제공한다. WholeGraph은 분산 GPU·host·storage memory를 다룬다([DGL](https://www.dgl.ai/dgl_docs/stochastic_training/index.html), [PyG](https://pytorch-geometric.readthedocs.io/en/2.5.1/tutorial/distributed_pyg.html), [WholeGraph](https://docs.nvidia.com/cugraph/26.08/wholegraph/basics/wholegraph_intro/)). 어떤 도구도 partition skew, hot node, temporal cutoff를 자동으로 해결한다고 가정해서는 안 된다.

### 규모별 병목

- **메모리**: adjacency보다 high-dimensional feature/optimizer state가 더 클 수 있다. dtype, cache, remote fetch를 별도 계측한다.
- **샘플링**: high-degree node와 relation imbalance가 batch variance와 bias를 만든다. full-neighbor “정답” 비교가 가능한 소규모 slice가 필요하다.
- **파티션**: edge cut 최소화만으로 부족하다. type/time locality, hotness, update locality를 포함한다.
- **통신**: bytes/step, cache hit, sampler wait, straggler p95를 모델 FLOPs와 함께 본다.
- **온라인 추론**: 매 요청 neighborhood expansion은 tail latency를 키운다. embedding precompute와 incremental update의 허용 stale window를 명시한다.

## 5. 벤치마크와 평가 설계

| 과업 | 기본 지표 | 반드시 추가할 지표/분할 |
|---|---|---|
| node 분류 | AUROC/F1 | class·degree·type·time subgroup, calibration |
| link 예측 | MRR/Hits@K/AUPRC | negative policy, filtered setting, 신규 node, temporal cutoff |
| graph 회귀 | MAE/RMSE | scaffold/group split, uncertainty, out-of-domain |
| temporal event | time-aware MRR/AUPRC | burst/quiet window, recurrence-stripped, delayed label |
| 생성 | validity/uniqueness/novelty | constraint violation, diversity, property uncertainty, simulation/experiment |
| causal discovery | SHD/SID, edge precision/recall | intervention family, latent confounder, equivalence class |
| routing/placement | objective gap | feasibility, wall-clock, repair cost, shift, worst-case tail |
| 시스템 | throughput/latency | bytes/step, peak memory, cost, energy, cache hit, recovery time |

OGB는 application-specific split과 evaluator를 제공하지만 leaderboard 비교에서도 external data와 설정 차이를 확인해야 한다([OGB](https://ogb.stanford.edu/), [leaderboard policy](https://ogb.stanford.edu/docs/leader_overview/)). 시간 그래프에는 TGB 2.0/TGB-Seq를 사용하되, 내부 observation process와 맞지 않으면 내부 time-forward benchmark를 별도로 만든다.

필수 기준선은 다음과 같다.

- feature-only MLP/GBDT/linear model
- degree, common-neighbor, PageRank 같은 graph heuristic
- simple shallow GNN
- sequence model(시간 과업)
- exact/approximate solver와 산업 휴리스틱(최적화)
- parameter·latency·memory budget을 맞춘 모델

ablation은 topology 제거, edge type shuffle, timestamp shuffle, feature 제거, positional encoding 제거, sampler 변경을 포함한다. topology shuffle 후에도 성능이 유지되면 그래프가 아니라 node feature shortcut을 학습했을 가능성이 높다.

## 6. MLOps, 안전, 공정성, 거버넌스

### 재현성과 관측성

- dataset snapshot, split manifest, sampler seed/config, dependency/container, hardware topology를 registry에 연결한다.
- overall metric뿐 아니라 degree/type/time/subgroup slice와 confidence interval을 저장한다.
- online에서는 graph freshness lag, unknown ID, missing feature, neighborhood size, embedding drift, downstream action rate를 감시한다.
- rollback은 모델만이 아니라 graph/feature/schema 버전까지 atomic하게 되돌릴 수 있어야 한다.

### 공격·개인정보 위험

그래프는 한 사람의 삭제가 이웃 표현에도 잔류할 수 있고, adjacency 자체가 민감 정보다. membership inference, link inference, poisoning, Sybil insertion, evasion edge perturbation, model extraction을 threat model에 넣는다. 2025년 GNN membership-inference 연구는 구조와 표현에서 학습 참여 여부가 노출될 수 있음을 재확인한다([IEEE TDSC](https://doi.org/10.1109/TDSC.2025.3586251)).

통제는 최소 권한 graph/feature access, raw identifier 분리, provenance와 consent, bounded neighborhood, adversarial edge validation, rate limiting, privacy deletion propagation, model/embedding 재생성 정책을 포함한다. differential privacy는 privacy budget뿐 아니라 degree별 utility 손실을 평가한다.

### 공정성과 설명

평균 demographic parity/equal opportunity만으로는 topology가 만드는 local disparity를 놓칠 수 있다. local homophily·degree·community별 FPR/FNR을 확인한다([SIAM SDM 2025](https://epubs.siam.org/doi/10.1137/1.9781611978520.65)). FairGSE의 높은 subgroup FPR 관찰은 프리프린트 신호이므로 내부 slice audit의 동기로만 사용한다([FairGSE](https://arxiv.org/abs/2511.12132)).

GNN 설명은 influential subgraph/feature/counterfactual로 나뉘며, 설명 안정성, fidelity, sparsity, human usefulness를 분리한다. attention weight를 인과 설명으로 간주하지 않는다([ACM survey](https://doi.org/10.1145/3711122)).

## 7. 도메인 적합성

| 도메인 | 그래프 단위/과업 | 높은 가치 조건 | 경계 |
|---|---|---|---|
| 사기·AML | account/device/transaction; event/link risk | 공동 행위와 관계 확산이 핵심 | 조사 label 지연, 집단 proxy 차별 |
| 추천·광고 | user/item/session; ranking/link | 상호작용·cold-start 관계 활용 | popularity feedback, consent |
| 공급망 | supplier/part/site; disruption propagation | multi-tier dependency가 관찰됨 | 누락 edge, 외부 충격 |
| 사이버보안 | identity/host/process/event; anomaly/path | 공격 경로와 lateral movement | 고속 변화, adversarial poisoning |
| 신약·재료 | atom/residue/lattice; property/generation | 대칭성과 물리 제약이 본질 | 실험 검증 비용, 합성 가능성 |
| 교통·물류 | road/order/vehicle; ETA/routing | topology와 시간 제약 | solver guarantee, 수요 shift |
| 제조·칩 | component/net/operation; placement/schedule | 명시적 connectivity·constraint | feasibility, 최악 사례 |
| 지식 운영 | entity/relation/schema; alignment/rule/query | 구조적 정합·감사 필요 | KG 불완전성, LLM triple 환각 |

그래프를 쓰지 않을 조건도 명확하다. 관계가 불안정하거나 관측되지 않고, feature-only baseline이 동일 성능·더 낮은 비용을 내며, decision이 graph neighborhood를 정당하게 사용할 수 없거나, latency/삭제 요구를 만족하지 못하면 tabular/sequence/solver가 낫다.

## 8. 2025–2026 변화 타임라인

| 시점 | 관찰된 변화 | 판독 |
|---|---|---|
| 2025 Q1 | MatterGen, G2PT 프리프린트, GraphStorm v0.4 | 과학 생성과 대규모 graph ML 양축 강화 |
| 2025 상반기 | ICLR GOFA/GIT 계열, graph Transformer·causal graph 연구 | 범용성·구조 추론 주장 증가, 전이 검증 필요 |
| 2025-05 | Jraph 공식 저장소 archive | JAX 그래프 생태계 선택 시 유지보수 리스크 신호 |
| 2025 하반기 | TGB-Seq, Graph World Models, higher-order·생성 graph 연구 | 시간 shortcut, 계획·고차 구조가 새 평가 축 |
| 2025 말 | GraphStorm 0.5.x, GraphBFF 전조 | framework 개선과 모델 대형화 병행 |
| 2026 초 | GraphBFF·SciGraph-LLM 등 공개 | billion-scale GFM·자동 KG 구축 주장 확대; 프리프린트/워크숍 성숙도 주의 |
| 2026-08 기준 | cuGraph/WholeGraph·PyG·DGL 분산 경로 지속 | 모델보다 sampling/feature/storage 통합이 실용 차별점 |

## 9. 과장 주장과 실패 모드 판별표

| 주장 | 질문 | 반증/통과 조건 |
|---|---|---|
| “GNN이 관계를 이해한다” | topology 제거 시 성능은? | feature-only·shuffled-edge 대비 유의한 이득 |
| “범용 GFM” | unseen schema/domain/task인가? | pretraining overlap 공개, zero/few-shot·small supervised 비교 |
| “billion-scale” | node/edge/parameter/sample 중 무엇인가? | end-to-end cost, failure recovery, exact scale 정의 |
| “실시간 temporal” | event/ingest/label time이 분리됐나? | point-in-time join, tail latency, update lag 공개 |
| “설명 가능” | 설명이 faithful·stable한가? | deletion/counterfactual test와 사용자 평가 |
| “공정” | local/community subgroup은? | degree/type/time 교차 slice에서 FPR/FNR 제한 |
| “분자를 생성” | valid가 synthesizable인가? | simulation·retrosynthesis·실험 단계 결과 분리 |
| “causal graph 발견” | intervention/latent 가정은? | equivalence class와 식별 불가능 edge 표시 |
| “solver를 대체” | feasibility·최악 사례·repair 포함? | 동일 wall-clock의 exact/heuristic 기준선보다 우수 |
| “GPU로 N배 빠름” | hardware, cache, accuracy가 같은가? | end-to-end independent benchmark; 공급사 microbenchmark 분리 |

주요 실패 모드는 schema drift, entity merge/split 오류, time leakage, negative sampling mismatch, disconnected cold-start node, oversmoothing/over-squashing, hot-node partition skew, stale embedding, feedback loop, edge poisoning, subgroup harm, non-deterministic sampling, deletion 미전파다.

## 10. 역할과 검토 체크리스트

| 역할 | 책임 |
|---|---|
| 도메인 owner | node/edge 의미, intervention/action, 손실 정의 |
| graph data engineer | identity, schema, temporal lineage, snapshot/CDC |
| ML scientist | baseline, split, model, uncertainty, ablation |
| ML/platform engineer | sampler, feature serving, registry, deployment/rollback |
| security/privacy | threat model, access, deletion, attack test |
| risk/fairness | subgroup·community 평가, human escalation |
| SRE/FinOps | tail latency, capacity, recovery, cost/energy |

검토 게이트:

- [ ] 그래프가 필요한 관계 가설과 non-graph baseline이 문서화됐는가?
- [ ] ID, edge direction/type, event time, label availability가 정의됐는가?
- [ ] random split이 아닌 실제 배포 경계를 재현하는가?
- [ ] negative sampling이 온라인 후보 모집단과 같은가?
- [ ] 모델 metric과 decision/business metric을 구분했는가?
- [ ] degree/type/time/subgroup, OOD, cold-start 평가가 있는가?
- [ ] graph/schema/feature/sampler/model 버전이 함께 재현되는가?
- [ ] 삭제·동의 변경이 neighbor embedding까지 전파되는가?
- [ ] poisoning, membership/link inference, Sybil 위협을 평가했는가?
- [ ] 생성/최적화 결과에 domain constraint와 fallback이 있는가?
- [ ] 공급사·프리프린트 주장을 독립 검증 대상으로 표시했는가?

## 11. 제안하는 30/60/90일 검증 계획

이는 구현 지시가 아니라 다음 의사결정을 위한 검증 순서다.

### 0–30일: 문제·데이터 적합성

- 한 과업과 한 배포 시점을 고정하고 graph schema/temporal contract를 작성한다.
- leakage audit와 entity-resolution 오차 표본을 만든다.
- feature-only, heuristic, shallow GNN을 동일 split·budget에서 비교하는 실험 명세를 만든다.
- risk owner, 금지 edge/feature, 삭제 SLA, success/stop 기준을 정한다.

통과 기준 예: graph baseline이 실무적으로 의미 있는 uplift를 내고, label/time leakage가 없으며, graph 구축·서빙 비용 상한이 승인됨.

### 31–60일: 모델·시스템 후보 축소

- GNN/graph Transformer/temporal 또는 heterogeneous 후보를 최대 2–3개로 제한한다.
- topology/timestamp/relation ablation, cold-start·OOD·subgroup 평가를 명세한다.
- sampler/feature cache/partition의 end-to-end cost·tail latency 측정 계획을 수립한다.
- explainability, privacy attack, edge poisoning, fallback 검증 항목을 승인한다.

### 61–90일: 운영 준비 여부 판단

- shadow/canary 설계, human override, abstention, rollback과 incident runbook을 검토한다.
- graph/feature/model atomic versioning과 deletion propagation evidence를 요구한다.
- 모델 uplift에서 graph 유지·GPU·운영·검토 비용을 뺀 순가치를 계산한다.
- 결과에 따라 `중단 / 제한적 pilot / 추가 연구` 중 하나를 결정한다.

## 12. 12–24개월 전망

### 확인된 사실

- 2025 주요 학회에 GOFA, task-tree GFM, graph world model, higher-order learning, temporal benchmark 연구가 등장했다.
- PyG, DGL/GraphBolt, cuGraph/WholeGraph, GraphStorm은 분산 sampling/feature/graph 처리 경로를 제공한다.
- Jraph 공식 저장소는 2025-05-21 archived 상태다.
- 재료·분자·단백질 그래프 생성이 peer-reviewed 과학 저널에서 계속 발표됐다.

### 근거 기반 추론

- GFM은 당분간 완전 범용 모델보다 동일 산업·유사 schema 묶음에서 pretrain→adapter 형태가 더 실용적일 가능성이 높다.
- 경쟁력은 모델 파라미터 수보다 point-in-time graph/feature 품질과 sampling/serving 통합에서 갈릴 가능성이 높다.
- LLM–graph 결합은 답변 검색보다 schema mapping, graph construction, query/program generation, hypothesis graph 생성에서 먼저 통제 가능한 가치를 낼 수 있다.
- temporal benchmark는 반복 간선 shortcut을 줄이고 실제 volatility/cold-start를 반영하는 방향으로 강화될 것이다.

### 예측과 불확실성

- **높은 가능성**: graph store–feature store–sampler interface 표준화와 GPU/분산 memory 최적화가 진전된다.
- **중간 가능성**: 도메인 GFM이 label 효율을 개선하지만, 데이터·schema가 크게 다른 zero-shot 전이는 제한된다.
- **중간 가능성**: 과학 생성 모델이 simulation/active learning loop와 더 밀접하게 결합된다. wet-lab 성공률 개선 폭은 불확실하다.
- **낮은 가능성**: 하나의 범용 graph model이 24개월 내 KG, 분자, fraud, routing을 별도 조정 없이 지배한다.
- **주요 불확실성**: 공개 pretraining corpus 중복, 독립 재현, energy/cost, 규제상 관계 데이터 사용, 동적 graph의 삭제·동의 처리.

## 결론

그래프 AI는 관계와 구조가 실제 의사결정 신호인 곳에서 강력하지만, “그래프가 있으니 GNN”은 충분한 근거가 아니다. 첫 판단은 graph necessity와 temporal/data contract, 두 번째는 강한 비그래프·휴리스틱 기준선, 세 번째는 운영 비용·안전의 순서여야 한다. 2025–2026 연구는 GFM, 고차/시간 학습, 과학 생성, world model로 넓어졌지만 범용성과 규모 주장은 아직 서로 다른 schema·과업·시스템 조건에서 독립 검증해야 한다. 후속 조사는 실제 후보 도메인 하나를 정한 뒤 schema, 배포 시점, 의사결정 비용을 입력으로 한 증거 매트릭스 형태가 가장 유용하다.
