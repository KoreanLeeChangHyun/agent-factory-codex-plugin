# 그래프 엔지니어링 최신 AI 동향: 2026-08-28 스냅샷

> 상태: 기존 `report.md`를 보완하는 임시 Inquiry 문서이며 제품 사양·선정안이 아니다.

## 핵심 요약

1. 2025~2026의 가장 뚜렷한 변화는 “GraphRAG 하나”가 아니라 LLM 추출 KG, 기존 업무 KG, community hierarchy, path/subgraph, vector+graph, temporal memory, multimodal·agentic retrieval로 설계 공간이 분화한 것이다.
2. Microsoft GraphRAG도 2026년 현재 local/global/DRIFT/basic search와 LLM 중심 Standard 및 저비용 FastGraphRAG를 구분하므로, GraphRAG라는 이름만으로 알고리즘이나 비용을 비교할 수 없다([공식 methods](https://microsoft.github.io/graphrag/index/methods/), [query overview](https://microsoft.github.io/graphrag/query/overview/)).
3. KG→LLM은 구조적 근거와 제약을 제공하고 LLM→KG는 추출·schema mapping·query generation을 자동화하지만, 후자는 hallucinated edge와 entity merge 오류를 영속화하므로 증거 연결·검증·rollback이 핵심 생산 기능이다.
4. Graph Foundation Model(GFM)은 빠르게 확장되는 연구 범주지만, 서로 다른 도메인·schema·특성 공간으로의 안정적 zero/few-shot transfer라는 “foundation” 수준은 아직 제한적으로 검증됐고 많은 결과는 한 도메인 또는 제한 benchmark에 묶여 있다.
5. 대규모 GNN 엔지니어링은 새 모델보다 sampling, feature/graph snapshot, CPU-GPU 파이프라인, partition, distributed inference와 temporal leakage 방지가 성패를 좌우한다.
6. agent graph memory는 episodic·semantic·temporal 사실을 연결하는 유망한 패턴이나, 제품 저자 benchmark와 제한된 공개 데이터가 많아 긴 context·vector·SQL/FTS memory baseline을 같은 비용 조건에서 이겼다고 일반화할 수 없다.
7. 분자·재료·코드 그래프에서의 foundation/generative model은 강한 도메인 제약과 대규모 데이터 덕분에 진전했지만, 그 성과를 일반 기업 KG나 GraphRAG로 직접 전이할 수 없다.
8. 2025년 이후 benchmark는 graph construction부터 answer까지 보려는 방향으로 발전했지만 LLM judge, 다른 corpus/model/token budget, graph 구축 비용 누락 때문에 순위표보다 stage별 paired evaluation이 더 신뢰할 만하다.
9. graph-aware retrieval은 일반 RAG 공격을 없애지 않으며, 2025~2026 연구는 소량의 source 변경이나 topology 조작이 여러 질의를 오염시키는 새로운 공격면을 보였다([GraphRAG under Fire](https://arxiv.org/abs/2501.14050), [LogicPoison](https://arxiv.org/abs/2604.02954)).
10. 향후 12~24개월의 현실적 채택점은 “범용 그래프 지능”보다 schema-bound hybrid retrieval, temporal/provenance graph, guarded text-to-query, graph/feature snapshot MLOps이며, baseline을 이긴 업무 질문에 한해 점진적으로 확장하는 것이다.

## 1. 조사 방법, 기준일, 한계

조사 기준일은 2026-08-28이다. 2025~2026 논문 원문·학회 페이지·공식 repository/release·공급자 문서를 우선했고, 계보상 필요한 2023~2024 원자료를 제한적으로 포함했다. 검색 축은 GraphRAG 변형, LLM↔KG, GFM/graph transformer, temporal/distributed GNN, 생성형 과학/코드 모델, agent memory, 제품 기능, benchmark, 보안이었다. 출처별 유형·날짜·사용 주장은 [ai-latest-sources.md](./ai-latest-sources.md)에 정리했다.

한계는 다음과 같다.

- “GraphRAG”, “graph agent”, “foundation model”은 표준화된 제품/평가 등급이 아니라 논문마다 범위가 다르다.
- 2026년 자료 중 arXiv·OpenReview submission은 동료평가가 완료되지 않았거나 결과가 바뀔 수 있다. 본문에서 상태를 구분한다.
- 공급자 문서는 기능 존재의 근거이며 성능 우월성의 독립 근거가 아니다.
- 논문 간 corpus, generator, embedding, prompt, token budget, judge, graph 구축 비용이 달라 절대 점수는 직접 비교하지 않았다.
- 웹 전수조사가 아니며 비공개 production 장애·비용·negative result는 과소대표된다.
- 이 Inquiry는 구현·시험·제품 선택을 하지 않았다.

### 성숙도 표기

| 등급 | 의미 |
|---|---|
| M3 운영 가능 | 공식 지원 구현과 운영 기능이 있고 업무별 검증 후 production 후보 |
| M2 초기 실용 | 공개 구현/학회 근거가 있으나 비교·운영 데이터가 제한적 |
| M1 연구 | 논문/프로토타입 중심, 독립 재현·장기 운영 근거 부족 |
| M0 주장 | 공급자/프로젝트 주장 또는 정의가 모호해 추가 검증 필요 |

## 2. 최신 AI 분야 지도

```text
원천 문서·DB·이벤트·이미지·코드·분자
  ├─ LLM → Graph: ontology/schema 보조, entity/relation/event 추출, ER, query 생성
  ├─ Graph → LLM: KG grounding, path/subgraph/community retrieval, tool planning
  ├─ Graph ML: GNN/transformer, temporal/heterogeneous learning, embeddings/anomaly
  ├─ Graph generation: molecule/material/code/world-model graph 생성·수정
  └─ Agent memory: episode → temporal facts → semantic consolidation → retrieval
       공통 생산층: ID·time·provenance·authorization·snapshot·evaluation·deletion
```

중요한 경계는 **그래프를 검색 인덱스로 쓰는가**, **학습 입력으로 쓰는가**, **생성 대상/상태로 쓰는가**다. 같은 “graph AI”라도 데이터 일관성, latency, 평가 단위와 실패 비용이 전혀 다르다.

## 3. 2025~2026 주요 변화 타임라인

| 시점 | 확인된 사건 | 의미/주의 |
|---|---|---|
| 2025-01 | Zep temporal KG agent memory 논문 공개([arXiv](https://arxiv.org/abs/2501.13956)) | bitemporal·hybrid retrieval 관심 확대; 저자/제품 평가임 |
| 2025-02 | HippoRAG 2가 RAG를 non-parametric continual memory로 확장([공식 repo](https://github.com/OSU-NLP-Group/HippoRAG)) | path/associative retrieval과 memory 경계가 가까워짐 |
| 2025-02 | GraphStorm 0.4가 DGL GraphBolt sampling/storage 통합([AWS 공지](https://aws.amazon.com/blogs/machine-learning/faster-distributed-graph-neural-network-training-with-graphstorm-v0-4/)) | scale의 병목이 sampling·memory pipeline임을 보여 줌; 속도 수치는 공급자 workload |
| 2025-04 | AAAI temporal-aware GNN 평가가 시간 오류의 clustering을 지적([AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/34273)) | 평균 MRR/AUC만으로 운영 위험을 숨길 수 있음 |
| 2025-06 | GraphRAG-Bench 공개([논문](https://arxiv.org/abs/2506.02404), [repo](https://github.com/jeremycp3/GraphRAG-Bench)) | graph construction→retrieval→generation 평가 시도; 단일 benchmark 과적합 주의 |
| 2025-07 | ACL CypherBench([ACL](https://aclanthology.org/2025.acl-long.438/)) | 대형 modern KG의 schema/context와 text-to-Cypher 정확성 문제를 구체화 |
| 2025-07 | query-driven multimodal GraphRAG([ACL Findings](https://aclanthology.org/2025.findings-acl.1100/)) | static global KG 대신 query-local multimodal graph 구성이라는 연구 방향 |
| 2025-08 | source의 소수 단어로 graph를 오염시키는 공격 연구([arXiv](https://arxiv.org/abs/2508.04276)) | graph construction supply chain이 보안 경계임 |
| 2025-09 | SWIFT가 secondary storage를 활용한 single-machine temporal GNN system 제안([ACM](https://doi.org/10.1145/3749184)) | 모든 scale 문제가 cluster만의 문제는 아님; 논문 workload 결과 |
| 2025-11 | LightRAG가 Findings of EMNLP에 출판([ACL Anthology](https://aclanthology.org/2025.findings-emnlp.568/)) | low/high-level retrieval을 결합한 경량 구현의 학회 근거 확보 |
| 2025-12 | GraphStorm 0.5.1 release([repo](https://github.com/awslabs/graphstorm)) | 대규모 graph ML의 공식 OSS가 계속 갱신됨 |
| 2026-04 | LogicPoison이 표면 문장보다 graph 논리/topology 조작을 공격면으로 제시([arXiv](https://arxiv.org/abs/2604.02954)) | text sanitizer만으로 방어 불충분이라는 연구 가설 |
| 2026-05 | Microsoft GraphRAG 3.1.0 release([releases](https://github.com/microsoft/graphrag/releases)) | storage/provider·streaming workflow 등 engineering 진화; API/version pin 필요 |
| 2026-07 | ACL Findings가 graph-assisted LLM을 knowledge, reasoning/planning, collaboration로 정리([ACL](https://aclanthology.org/2026.findings-acl.945/)) | graph가 RAG를 넘어 agent coordination으로 확장되는 연구 분류 |
| 2026-08 | Spanner Graph 공식 문서에 node/edge KNN, node ANN과 graph traversal 결합이 구체화([Google](https://docs.cloud.google.com/spanner/docs/graph/perform-vector-similarity-search)) | 통합 relational+graph+vector 제품화; edition/edge ANN 제한 확인 필요 |

## 4. GraphRAG: 한 이름, 여러 시스템

### 유형과 원리

| 유형 | 인덱스/검색 원리 | 강한 질문 | 성숙도 | 주요 비용/실패 |
|---|---|---|---|---|
| 기존 KG 기반 | curated KG의 entity/path/query | 사실·제약·multi-hop | M3/M2 | KG coverage, entity linking, query 권한 |
| community/hierarchical | entity graph 군집과 multi-level summary | corpus 전체 theme/global summary | M2 | LLM indexing·summary 비용, update 재계산 |
| path/subgraph | seed entity에서 bounded path/subgraph를 선택 | 연결 근거, multi-hop QA | M2 | hub/fan-out, path noise, retrieval optimization |
| vector+graph hybrid | vector/keyword 후보 후 graph expand/filter 또는 역순 | 의미+관계 조건 | M3/M2 | 두 index의 version skew, top-k/depth tuning |
| temporal/dynamic | event/valid/record time으로 현재·과거 graph 검색 | 변화·기억·시간 질의 | M2 | contradiction, late event, history storage |
| multimodal | text/image/table/code entity를 공통/지역 graph로 결합 | cross-modal evidence | M1/M2 | OCR/VLM 오류, modality provenance, 큰 token 비용 |
| agentic | agent가 검색 방법·경로·query/tool을 반복 선택 | 복합 조사·계획 | M1 | loop 비용, non-determinism, tool abuse |

Microsoft의 공식 구현은 Standard indexing이 entity/relationship extraction과 entity summary에 LLM을 사용하고 FastGraphRAG는 일부를 전통 NLP로 대체해 비용을 줄인다([methods](https://microsoft.github.io/graphrag/index/methods/)). query는 local, community report map-reduce global, community 정보로 local을 확장하는 DRIFT, 비교용 basic vector RAG를 제공한다([query overview](https://microsoft.github.io/graphrag/query/overview/)). 따라서 “Microsoft GraphRAG와 vector RAG 비교”도 질문군별 local/global/basic 설정과 version을 고정해야 재현 가능하다.

LightRAG는 graph indexing에서 local·global key를 함께 쓰는 경량 계열이며 2025 EMNLP Findings 논문과 활발한 MIT repository가 있다([paper](https://aclanthology.org/2025.findings-emnlp.568/), [repo](https://github.com/HKUDS/LightRAG)). HippoRAG 2는 KG와 personalized PageRank 계열 associative retrieval을 continual memory 관점으로 확장한다([repo](https://github.com/OSU-NLP-Group/HippoRAG)). 서로 데이터 모델과 목표가 달라 같은 열의 “GraphRAG” 제품처럼 단순 비교하면 안 된다.

### 시스템 설계 영향

- **Index build를 모델 학습처럼 관리:** extraction LLM/prompt/schema/ER/embedding/community algorithm 버전과 source snapshot을 묶는다.
- **원문을 버리지 않음:** node/edge마다 evidence span과 source ACL을 연결하고 answer에는 원문 단위 citation을 조립한다.
- **query별 router:** fact lookup은 vector/keyword, entity-local은 bounded traversal, global synthesis는 community로 보내며 항상 단순 baseline fallback을 둔다.
- **incremental update 계약:** 신규 entity뿐 아니라 correction, merge/unmerge, expiry, deletion이 vector·community summary·cache까지 전파되어야 한다.
- **cost governor:** hop, expanded nodes, community reports, context tokens, LLM calls, wall-clock budget으로 종료한다.

## 5. LLM ↔ Knowledge Graph의 양방향 결합

### LLM-enhanced KG

LLM은 ontology 후보, schema mapping, entity/relation/event extraction, entity resolution 후보·설명, triple validation, 자연어→Cypher/SPARQL을 보조한다. 2025 IJCAI LLM4VKG는 virtual KG의 ontology/schema/mapping 생성에 LLM을 사용했지만 특정 benchmark 결과다([IJCAI](https://www.ijcai.org/proceedings/2025/525)). 2026 SciGraph-LLM은 scientific claim을 evidence span과 연결하는 constrained pipeline을 제안해 provenance가 후처리 부가물이 아니라 추출 계약이어야 함을 보여 준다([ACM](https://doi.org/10.1145/3779211.3793169)).

실무 원칙은 “LLM output → graph write”가 아니라 다음 gate다.

1. schema-constrained structured output;
2. source span·document hash·extractor version 필수;
3. deterministic normalization과 candidate ER;
4. SHACL/constraint·cardinality·temporal validation;
5. confidence가 아닌 calibrated acceptance/review 정책;
6. append event와 reversible merge/unmerge;
7. gold-set precision/recall 및 type별 오류 budget.

Text-to-Cypher는 자연어 접근성을 높이지만 schema가 크고 관계명이 중복/모호하면 prompt context를 넘는다. CypherBench는 11개 대형 property graph, 780만 entity, 1만+ question으로 이 문제를 평가한다([ACL 2025](https://aclanthology.org/2025.acl-long.438/)). production에서는 read-only principal, schema allowlist, AST parse, write/procedure 차단, depth/cardinality estimate, timeout/row cap, tenant predicate 주입, execution-plan gate를 거친다. 실행 성공은 의미 정확성과 같지 않으므로 result-set/denotation과 업무 answer를 따로 평가한다.

### KG-enhanced LLM

KG는 entity disambiguation, typed relations, constraint, path evidence, rule/ontology reasoning, temporal/provenance, authorization boundary를 제공한다. 하지만 LLM은 graph serialization을 정확히 해석하지 못할 수 있고, retrieved path가 상관관계일 뿐 인과 근거가 아닐 수 있다. symbolic result와 narrative generation을 분리하고, “graph에 없음”을 “거짓”으로 바꾸지 않는 open-world/closed-world 정책을 명시한다.

### 양방향 loop의 위험

LLM이 만든 edge를 다시 LLM grounding에 쓰면 자기 강화 오류가 생긴다. source-backed/curated/inferred/model-predicted edge를 서로 다른 상태로 저장하고, predicted edge가 canonical fact가 되려면 별도 승인/증거를 요구한다. ontology도 LLM이 제안할 수 있으나 domain owner가 의미·호환·migration을 소유한다.

## 6. Graph Foundation Models와 범용 표현학습

GFM은 보통 대규모 self-supervised pretraining 후 task/domain/graph로 transfer하거나 in-context/few-shot 적응하는 모델을 뜻한다. 2025 survey 자체도 universal, task-specific, domain-specific으로 범위를 나누고 structural alignment, heterogeneity, scale, evaluation을 열린 문제로 둔다([survey](https://arxiv.org/abs/2505.15116)). 이 구분은 “foundation”이라는 명칭이 실제 universal transfer를 보증하지 않음을 보여 준다.

주요 계열은 다음과 같다.

- **GNN encoder pretraining:** masking, contrastive, context prediction 후 downstream head를 fine-tune.
- **Graph transformer:** global/structured attention, positional/structural encoding으로 장거리 관계를 모델링. full attention의 O(n²), oversquashing/over-globalizing, positional transfer가 문제다.
- **Graph-to-text/LLM:** graph를 sequence/instruction으로 serialize하거나 graph encoder adapter를 LLM에 붙인다. token order, graph isomorphism, 긴 topology 손실이 문제다.
- **text-attributed graph co-training:** node/edge text와 topology를 정렬한다. 의미 transfer 가능성은 크지만 text leakage와 domain vocabulary 의존이 있다.
- **heterogeneous/dynamic GFM:** type/time을 포함하려 하지만 schema alignment와 temporal causality가 더 어렵다.
- **domain foundation model:** molecule/material/recommendation처럼 의미가 고정된 그래프에서 대규모 pretraining. 가장 강한 근거가 있으나 범용 graph transfer가 아니다.

**과장 판정 기준:** 최소한 (a) unseen graph/domain, (b) 여러 node/link/graph task, (c) zero/few-shot와 fine-tune, (d) strong non-foundation baseline, (e) compute/data scaling, (f) negative transfer·calibration을 공개해야 범용 GFM 주장에 가까워진다. 한 dataset family에서 사전학습하고 유사 task로 전이한 결과는 “pretrained graph model”로 부르는 편이 정확하다. 2026의 billion-scale GFM·scaling-law 결과도 arXiv 단계이므로 유망한 연구 신호이지 production 증거가 아니다([GraphBFF](https://arxiv.org/abs/2602.04768)).

## 7. GNN/Graph ML 엔지니어링의 최신 초점

### scale과 hardware

neighbor sampling은 계산을 줄이지만 high-degree/rare relation 신호와 학습 분포를 바꾼다. cluster/partition sampling은 locality를 높이는 대신 cross-partition feature fetch와 stale embedding을 만든다. PyG는 partitioned graph, RPC sampling/feature retrieval와 DDP 기반 분산 학습을 제공한다([PyG docs](https://pytorch-geometric.readthedocs.io/en/2.5.1/tutorial/distributed_pyg.html)). GraphStorm 0.4는 compact storage·pipelined sampling의 GraphBolt를 통합했고 0.5.1까지 공개됐지만, 공급자 속도 수치는 해당 dataset/hardware의 주장이다([0.4 공지](https://aws.amazon.com/blogs/machine-learning/faster-distributed-graph-neural-network-training-with-graphstorm-v0-4/), [repo](https://github.com/awslabs/graphstorm)).

생산 MLOps의 unit은 model file이 아니라 다음 bundle이다.

`{source offsets, graph snapshot, feature schema/values, labels/as-of policy, split, sampler/negative policy, model/code, seed, hardware, metrics}`

online graph와 training snapshot을 조용히 섞지 않는다. node/edge deletion과 consent withdrawal이 feature cache·embedding·training corpus·prediction store로 전파되는 lineage를 둔다. transductive embedding은 신규 node를 바로 처리하지 못하므로 inductive 여부와 refresh SLA를 명시한다.

### temporal graph

Temporal Graph Benchmark는 dynamic link/node property, temporal KG와 heterogeneous graph를 표준 split/evaluator로 다룬다([TGB](https://tgb.complexdatalab.com/)). TGB-Seq는 기존 dataset의 반복 edge가 단순 memory baseline을 과대평가할 수 있고 복잡한 순차 dynamics에서 모델이 약함을 보였다([ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/file/db5ca61dbc08cf5143c05ad2d1b0b2ca-Paper-Conference.pdf)). 따라서 random split을 금지하고 event-time cutoff, delayed label, cold node, no-repeat edge, volatility cluster, time-to-detect를 평가한다.

### fraud/anomaly/recommendation

GNN은 ring/heterogeneous relation을 활용하지만 label leakage, post-event feature, biased negative, adversarial actor adaptation, popular-item shortcut가 흔하다. 정확도/AUC 대신 PR-AUC, top-k recall, alert volume, investigator yield, loss-weighted calibration, subgroup/cold-start, detection delay를 사용한다. rule/gradient-boosted tree/sequence model과 동일 feature/time cutoff에서 비교한다.

## 8. 생성형 graph와 도메인 응용

| 영역 | 최신 근거 | 전이 가능한 공학 | 전이 불가능/제한 |
|---|---|---|---|
| 분자 생성 | GraphXForm은 atom/bond graph를 순차 수정해 chemical validity·substructure constraint를 반영([2025 논문](https://doi.org/10.1039/d4dd00339j)) | constrained decoding, validity gate, objective audit | valence/chemistry 규칙은 기업 KG에 그대로 전이 불가 |
| 재료 생성 | MatterGen은 diffusion 기반 inorganic material generation과 property-conditioned fine-tuning을 보고([Nature 2025](https://www.nature.com/articles/s41586-025-08628-5)) | 생성→simulation/validator→실험의 staged loop | DFT/실험 검증이 있어야 하며 일반 graph 생성 품질과 다름 |
| 분자 foundation | MolE는 약 8.42억 molecular graph self-supervised pretraining을 보고([Nature Communications](https://doi.org/10.1038/s41467-024-53751-y)) | 대규모 pretrain, atomic-environment representation | molecule이라는 단일 의미 체계에 특화 |
| 재료 graph ML | MatGL은 invariant/equivariant GNN과 pretrained potential을 제공([npj 2025](https://www.nature.com/articles/s41524-025-01742-y)) | rotation equivariance, versioned pretrained artifact | 3D 물리 대칭은 일반 KG에는 해당하지 않음 |
| 코드 graph | Code Graph Model은 repository graph를 LLM attention에 통합([NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/178ae4ba29022eb7bf509c2e27bc8ab8-Abstract-Conference.html)) | parser-derived provenance, symbol/call/dependency graph, repo snapshot | 언어 parser와 build semantics에 종속 |
| multimodal GraphRAG | query-driven local KG가 WebQA/MultimodalQA에서 연구됨([ACL 2025](https://aclanthology.org/2025.findings-acl.1100/)) | query-local graph, modality-specific evidence | unsupervised competitor 내 결과; production 일반화 미확인 |

공통 전이점은 **도메인 validator를 생성 모델 밖에 둔다**, **원 입력과 생성물을 구분한다**, **active learning/실험 feedback에 provenance를 둔다**는 것이다. 분자 validity나 compiler test처럼 강한 oracle이 없는 일반 KG는 hallucinated graph를 걸러내기 더 어렵다.

## 9. AI agent의 graph memory와 coordination

메모리를 다음처럼 분리하면 과도한 “기억” 주장을 피할 수 있다.

- working: 현재 turn/task 상태, 짧은 TTL;
- episodic: 누가 언제 무엇을 관찰/수행했는지와 원문 event;
- semantic: 여러 episode에서 승인된 안정 fact/concept;
- procedural: 도구/skill/policy, 별도 권한·version;
- temporal relation: valid time과 recorded time, contradiction/supersession.

Graphiti는 episode를 bitemporal KG로 증분 통합하고 semantic/keyword/graph hybrid retrieval을 제공한다고 공식 repo가 설명한다([Graphiti](https://github.com/getzep/graphiti)). Zep 논문의 LongMemEval/DMR 성과는 시스템 저자가 보고한 결과이므로 독립 benchmark로 재확인해야 한다([paper](https://arxiv.org/abs/2501.13956)). AriGraph는 agent가 exploration 중 semantic+episodic world-model graph를 만드는 연구 계보를 제공한다([paper](https://arxiv.org/abs/2407.04363)).

production에서는 raw episode를 보존하고 semantic consolidation을 provenance edge로 표현하며, 모순을 overwrite하지 않는다. memory write는 user/tenant scope와 consent를 확인하고 prompt가 스스로 장기 memory 정책을 바꾸지 못하게 한다. multi-agent graph는 shared task/dependency/evidence를 조정하는 데 유용할 수 있으나, lock/transaction/ownership 없이 agent들이 같은 node를 수정하면 lost update와 자기강화 오류가 난다. graph는 coordination state store일 수 있어도 consensus/authorization 시스템을 자동 대체하지 않는다.

권장 baseline은 full recent context, summary memory, vector+raw episode, SQL/FTS temporal facts다. 같은 context budget, generator, latency, write cost로 temporal QA, cross-session synthesis, contradiction, deletion, privacy를 비교한다.

## 10. 공식 구현·제품 기능 비교

| 구현/제품 | 2026-08 확인 기능 | 상태/성숙도 | 해석상 주의 |
|---|---|---|---|
| Microsoft GraphRAG 3.x | Standard/Fast indexing; local/global/DRIFT/basic; Cosmos provider와 일부 streaming workflow release | OSS M2 | research platform; index 비용·breaking/version migration 검증 |
| Neo4j GraphRAG Python | first-party KG builder, vector/graph/external retriever, LLM provider; Neo4j 2026.01 filterable vector index | M3 후보 | package 기능≠answer 우월; ANN·edition/version·Cypher guard 확인([docs](https://neo4j.com/docs/neo4j-graphrag-python/current/)) |
| Amazon Neptune/Analytics | SPARQL/Gremlin/openCypher graph; Analytics vector+graph; Neptune ML은 SageMaker/DGL GNN/KGE; GraphStorm 연동 | M3 후보 | export/train/endpoint workflow, AWS 책임경계·비용; 서비스별 기능 분리([ML docs](https://docs.aws.amazon.com/neptune/latest/userguide/machine-learning.html)) |
| Google Spanner Graph | relational+GQL graph, full-text/vector, LangChain GraphRAG, graph algorithms; node/edge KNN·node ANN | M3 후보 | 공급자 정확성/scale 주장은 독립 검증 필요; edition와 ANN edge 제한([overview](https://docs.cloud.google.com/spanner/docs/graph/overview)) |
| LightRAG | graph+vector 계열 indexing/retrieval, MIT, EMNLP 2025 paper | M2 | 빠른 release와 backend 조합이 많아 version/config pin 필수 |
| HippoRAG 2 | personalized-PageRank 계열 associative retrieval, continual memory framing | M2/M1 | 설치·index 비용, baseline/model 조건 재현 필요 |
| Graphiti | bitemporal agent KG, incremental update, hybrid retrieval, 여러 graph backend | M2 | 제품 연계 benchmark와 OSS 안정성·ER 비용 구분 |
| GraphStorm | heterogeneous graph ML, distributed train/inference, GraphBolt; 0.5.1 release | M2/M3 후보 | graph DB/RAG가 아니라 ML framework; AWS 수치 일반화 금지 |
| PyG/DGL | GNN model/sampling/distributed primitives | M3 연구·개발 기반 | production feature store/snapshot/serving는 별도 |

“Google/Vertex AI graph capability”는 하나의 Vertex graph database가 아니라 Spanner Graph의 graph/vector/full-text와 Agent Platform/모델을 연결하는 참조 구조로 보는 것이 정확하다([Google architecture](https://docs.cloud.google.com/architecture/gen-ai-graphrag-spanner)). Google Knowledge Graph Search API도 production-critical service에 부적합하다는 경고가 있어 별도 서비스와 혼동하지 않는다([공식 API](https://developers.google.com/knowledge-graph)).

## 11. 평가 프레임워크와 권장 baseline

### stage별 측정

| 단계 | 필수 지표 |
|---|---|
| graph construction | entity/relation exact+semantic precision/recall/F1, canonicalization/ER pairwise & cluster metric, unsupported-edge rate, evidence-span accuracy, schema/temporal validity, update/delete propagation |
| retrieval | Recall@k, nDCG/MRR, path/subgraph precision, evidence coverage, ACL violations=0, temporal precision, graph expansion·token 수 |
| answer | exact/F1와 task rubric, claim-level citation precision/recall, groundedness, contradiction, abstention/calibration, temporal correctness |
| system | p50/p95/p99, index wall time, LLM calls/tokens, storage/egress/GPU, update freshness, failure/retry, availability |
| business | resolution time, investigator yield, conversion/loss, human correction, harmful error rate |
| lifecycle | reproducibility, drift, rebuild/rollback, deletion SLA, incident detect/contain time |

GraphRAG-Bench는 domain-specific graph construction·retrieval·generation 평가를 넓히지만([paper](https://arxiv.org/abs/2506.02404)), 모든 production corpus를 대표하지 않는다. CypherBench는 text-to-query를 더 직접 측정하지만 answer generation이나 운영 보안 전체를 대신하지 않는다. TGB/TGB-Seq는 temporal ML을 평가하지만 GraphRAG benchmark가 아니다. benchmark 이름별 목표를 섞지 않는다.

LLM-as-judge는 blind randomized paired comparison, judge/model 다양화, human audit subset, 명시적 rubric, tie/variance/CI와 함께 쓴다. 동일 corpus, source cutoff, embedding/generator, max context, retries, temperature, hardware, caching을 고정하고 index amortization 기간을 공개한다.

### 권장 baseline ladder

1. no-retrieval long context(들어갈 때만);
2. BM25/FTS;
3. dense vector;
4. lexical+dense hybrid + reranker;
5. curated KG exact query;
6. vector seed + bounded graph expansion;
7. path/subgraph GraphRAG;
8. community/global 또는 agentic GraphRAG.

각 단계가 이전 단계를 업무 효용 또는 품질/비용 Pareto에서 이길 때만 유지한다. “graph DB를 쓰지 않은 graph algorithm”과 “graph DB에 저장한 vector-only RAG”도 구분한다.

## 12. Production 참조 아키텍처

```text
[Sources: DB/CDC, docs, images, code, events]
  -> immutable raw + source ACL/licence + content hash
  -> parsers/OCR/VLM/LLM extraction (sandbox, prompt version)
  -> schema-constrained candidate facts/events
  -> normalize + ER candidate + human/rule validation
  -> evidence/provenance + valid/record time + sensitivity
  -> append event log
       ├─ operational curated graph (authorized query)
       ├─ vector/keyword indexes (embedding version)
       ├─ community/path/summary indexes (build version)
       └─ graph/feature snapshots -> GNN train/eval/registry

Query -> identity/policy -> intent/router ->
  lexical | vector | exact KG query | bounded path | community | agent loop
  -> ACL-aware retrieval + cost/depth cap -> evidence assembler
  -> LLM (retrieved data treated as untrusted) -> claim/citation verifier
  -> response + audit/metrics/feedback

Corrections/deletion -> event log -> graph/vector/summary/cache/model lineage
```

read principal과 write/extraction principal을 분리한다. generated query는 raw driver로 바로 실행하지 않고 parser/policy/cost gate를 통과시킨다. retrieval 결과는 instruction이 아니라 untrusted data로 경계 표시한다. graph, vector, summary가 같은 `corpus_snapshot_id`를 참조하지 않으면 serving을 차단하거나 명시적으로 degraded mode로 보낸다.

## 13. 과장된 주장, 실패 모드, 보안·거버넌스

### 과장 판별

- “GraphRAG가 RAG보다 정확”: 질문군·budget·generator가 같지 않으면 미확인.
- “foundation”: unseen domain/task transfer가 없으면 pretraining model에 가깝다.
- “real-time KG”: ingestion latency만 제시하고 correction/ER/community rebuild가 없으면 불완전.
- “agent memory”: retrieval QA가 높아도 기억의 정확한 삭제·충돌·권한·long-horizon 행동 개선은 별개.
- “explainable”: 그럴듯한 path나 attention은 source-backed causal explanation이 아니다.
- “billion-scale”: node/edge 수만 있고 degree, feature, task, hardware, quality가 없으면 비교 불가.

### 주요 실패 모드와 통제

| 실패 | 영향 | 통제 |
|---|---|---|
| hallucinated/underspecified edge | 여러 path·summary·answer로 증폭 | evidence span 필수, predicate allowlist, quarantine, sample audit |
| false entity merge/split | 잘못된 연결/누락의 대규모 전파 | reversible ER, cluster gold set, uncertainty node, human review |
| stale/conflicting temporal fact | 과거/현재 답 오류 | valid+record time, supersession, point-in-time test |
| indirect prompt injection in node/text/image | instruction hijack·data exfiltration | untrusted context separation, sanitizer는 보조, tool allowlist, no secrets in context |
| graph/data poisoning | 여러 query를 공유 relation/topology로 공격 | source trust, signed ingestion, anomaly/diff review, canary queries, rebuild/rollback |
| generated-query abuse | write, tenant escape, path explosion | read-only, AST policy, mandatory tenant predicate, hop/row/time cap, procedure deny |
| authorization-blind traversal | 이웃/path로 민감 관계 유출 | retrieval 전/중 policy, edge/node/attribute ACL, count/timing leakage test |
| privacy inference/GNN leakage | membership·attribute·graph reconstruction | minimization, aggregation, DP 필요성 검토, output budget, red-team |
| embedding/model drift | relevance·ER·cluster 변화 | version isolation, shadow rebuild, paired regression, rollback |
| deletion gap | graph에서 지워도 vector/summary/model/cache에 잔존 | end-to-end lineage와 deletion receipt/SLA |

OWASP는 RAG가 prompt injection을 해결하지 않으며 external retrieved content가 indirect injection/poisoning 경로라고 명시한다([LLM Top 10 2025](https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf), [RAG Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)). GraphRAG 특화 2025 연구는 relation injection/enhancement가 shared graph를 통해 공격을 확장할 수 있음을 보고했다([GraphRAG under Fire](https://arxiv.org/abs/2501.14050)). 이 수치는 특정 실험 결과이지 보편 공격 성공률이 아니지만 threat model 포함 근거로 충분하다.

## 14. 도입 체크리스트

- [ ] 질문을 fact/local/global/path/temporal/multimodal/agentic으로 분류했는가?
- [ ] BM25, dense hybrid, curated exact-query baseline이 있는가?
- [ ] graph의 각 edge가 source span·ACL·time·extractor version을 갖는가?
- [ ] ER precision/recall, reversible merge와 owner가 있는가?
- [ ] graph/vector/community/model snapshot이 한 ID로 결속되는가?
- [ ] update·correction·late event·deletion이 모든 파생물에 전파되는가?
- [ ] Text-to-Cypher/SPARQL이 read-only AST/policy/cost gate를 거치는가?
- [ ] query hop/node/token/LLM-call/latency budget과 fallback이 있는가?
- [ ] claim-level citation, abstention, temporal correctness를 평가하는가?
- [ ] graph construction과 query 비용을 TCO에 포함했는가?
- [ ] source poisoning·indirect injection·ACL traversal·graph reconstruction red-team이 있는가?
- [ ] GNN에는 as-of split, negative policy, snapshot/feature/label lineage가 있는가?
- [ ] 공급자 benchmark를 독립 결과로 표현하지 않았는가?
- [ ] exit/export, package/version pin, license/managed responsibility를 확인했는가?

## 15. 30/60/90일 실험 계획

### 0~30일: 문제와 gold set

- 고가치 질문 50~200개를 유형별로 stratify하고 harmful error/abstention 기준을 정의한다.
- source snapshot, ACL, canonical entity와 evidence span을 포함한 작은 gold graph를 만든다.
- BM25, dense, hybrid reranker와 기존 exact-query baseline을 동일 generator/context budget으로 측정한다.
- 후보는 한 GraphRAG 패턴과 최대 두 구현으로 제한한다.
- 종료 gate: graph가 필요한 질문이 명확하지 않거나 gold ER/evidence를 만들 수 없으면 중단한다.

### 31~60일: offline paired prototype

- versioned extraction→validation→graph/vector build를 만들고 false edge·ER·temporal 오류를 stage별 측정한다.
- local/path/community 중 질문에 필요한 것만 구현하며 query cost cap을 둔다.
- paired bootstrap/CI로 answer·grounding·latency·token·index 비용을 baseline과 비교한다.
- correction/deletion/rebuild와 Text-to-query guard를 tabletop/fixture 수준 계획에 포함한다(실제 테스트 실행은 별도 Human 승인 대상).
- gate: 핵심 질문군에서 품질/비용 Pareto 개선과 source-backed answer가 없으면 확장하지 않는다.

### 61~90일: production-readiness 설계와 제한 pilot 제안

- auth-aware retrieval, audit, snapshot promotion/rollback, drift dashboard, runbook, TCO를 설계한다.
- shadow/canary pilot의 트래픽, 실패 격리, human review와 중단 조건을 문서화한다.
- prompt injection/poisoning/query abuse/privacy/deletion threat model과 책임자를 지정한다.
- GNN을 포함하면 static baseline과 temporal as-of split, online/offline feature parity를 별도 track으로 평가한다.
- 90일 결정은 채택이 아니라 `stop / revise / Human-approved limited pilot` 중 하나이며 위험 허용·제품 선택은 Human에게 남긴다.

## 16. 12~24개월 전망: 사실·추론·전망 분리

### 확인된 사실(2026-08-28)

- Microsoft GraphRAG는 3.x release와 Standard/Fast 및 여러 query method를 제공한다.
- Neo4j, Neptune, Spanner Graph는 graph+vector/AI 또는 GraphRAG 개발 기능을 공식 문서화했다.
- ACL/EMNLP/AAAI/ICLR/NeurIPS에 multimodal GraphRAG, text-to-Cypher, temporal GNN, code graph model 등 동료평가 결과가 등장했다.
- GraphRAG-Bench, CypherBench, TGB-Seq처럼 pipeline/task 특화 benchmark가 늘었다.
- 2025~2026 공격 연구는 source/relationship/topology poisoning을 구체적 공격면으로 보였다.

### 합리적 추론

- graph, vector, full-text, relational을 한 query/runtime에 묶는 제품은 데이터 이동과 consistency 비용을 줄일 수 있지만, best-of-breed 품질이나 lock-in 비용이 자동 개선되는 것은 아니다.
- full-corpus LLM graph extraction보다 schema-bound extraction, NLP/SLM 혼합, query-local graph가 비용·품질 제어 때문에 production에서 더 흔해질 가능성이 높다.
- temporal/provenance와 reversible ER가 agent memory 및 dynamic GraphRAG의 차별 기능이 될 가능성이 높다. 단순 vector memory보다 우월해서가 아니라 correction/감사 요구 때문이다.
- GFM은 먼저 molecule/material/recommendation/TAG처럼 의미와 데이터가 비교적 정렬된 영역에서 채택되고, arbitrary enterprise graph로의 universal transfer는 느릴 가능성이 높다.

### 전망(불확실)

- GQL/graph tool interface를 통한 agentic query planning이 확산될 수 있으나 semantic accuracy와 authorization 표준이 뒤처지면 read-only bounded tool로 제한될 것이다.
- graph-native long-term memory가 agent platform의 공통 구성요소가 될 수 있지만, long context·structured SQL/FTS·vector memory의 비용 하락이 graph의 필요 범위를 줄일 수도 있다.
- graph construction quality를 자동 평가·수정하는 작은 verifier/critic model과 signed provenance가 별도 제품 계층으로 성장할 수 있다.
- multi-agent coordination graph는 shared evidence/task lineage에는 유용하겠지만, 합의·transaction·identity를 대신하는 “collective intelligence graph” 주장은 향후 독립 근거가 필요하다.

## 17. 결론과 최소 후속 Inquiry

최신성의 핵심은 더 큰 그래프나 더 많은 agent가 아니라 **증거·시간·권한이 붙은 graph를 어떤 질문에 얼마의 비용으로 사용하고, 오류를 어떻게 되돌리는가**다. 2025~2026은 GraphRAG가 단일 recipe에서 다양한 retrieval/memory/agent 패턴으로 분화하고, GFM·temporal GNN·과학 graph model이 발전한 동시에 benchmark와 poisoning 연구가 과장을 제약하기 시작한 시기다. production은 curated/extracted/predicted fact를 분리하고, graph/vector/community/model snapshot을 결속하며, simple RAG와 paired evaluation을 통과한 부분만 채택해야 한다.

가장 작은 후속 Inquiry는 실제 업무 corpus와 질문 100개를 대상으로 `lexical+dense hybrid` 대 `vector→2-hop authorized graph` 대 `community/global` 세 패턴의 **평가 설계만** 작성하는 것이다. 산출물은 gold evidence/ER 기준, snapshot contract, claim-level metric, poisoning/deletion fixtures, index+query TCO 식과 Human 승인 gate여야 한다. 제품·위험 허용·pilot 실행 여부는 unresolved Human decision이다.
