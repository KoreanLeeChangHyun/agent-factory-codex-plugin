# 그래프 엔지니어링 종합 조사

> 조사 기준일: 2026-08-28  
> 상태: 임시 Inquiry 자료. 제품 사양이나 채택 결정이 아니다.

## 핵심 요약

1. 그래프 엔지니어링은 관계가 핵심인 데이터를 그래프로 모델링하고, 식별·수집·저장·질의·분석·학습·운영·거버넌스하는 전체 시스템 공학이다.
2. 그래프 이론은 수학적 토대, 그래프 분석은 계산 작업, 지식 그래프는 의미와 식별을 강조하는 데이터 자산, GNN은 그래프를 입력으로 삼는 ML이며, 이들은 그래프 엔지니어링의 일부 또는 인접 분야이지 동의어가 아니다.
3. 속성 그래프는 애플리케이션 탐색과 풍부한 노드/엣지 속성에, RDF는 전역 식별·상호운용·명시적 의미론에, 하이퍼그래프는 3개 이상 객체의 원자적 관계에 강하지만 어느 모델도 모든 워크로드를 지배하지 않는다.
4. 저장소 선택보다 먼저 질문, 일관성, 시간 의미, 식별자, 데이터 품질 SLO와 대표 쿼리의 비용 상한을 정의해야 한다.
5. OLTP 이웃 탐색, 전역 OLAP 알고리즘, 스트리밍 증분 계산, GNN 학습은 서로 다른 실행 특성을 가지므로 한 엔진에 억지로 합치기보다 목적별 평면과 재현 가능한 스냅샷 경계를 두는 편이 안전하다.
6. GQL은 2024년 최초 ISO 속성 그래프 언어 표준이고 SQL/PGQ는 SQL 안에서 속성 그래프 패턴을 다루며, RDF 계열의 현재 안정 기반은 SPARQL 1.1·OWL 2·SHACL 1.0이고 RDF/SPARQL/SHACL 1.2는 2026년에도 단계가 서로 다른 초안·후보 표준이다.
7. 엔티티 해소, provenance, 유효시간과 기록시간, 삭제/정정 전파가 없는 그래프는 연결은 많아져도 신뢰할 수 있는 지식이 되지 않는다.
8. 벡터+그래프 및 GraphRAG는 의미적 후보 검색과 구조적 제약·근거 연결을 결합하지만, LLM 추출 오류·비용·평가 난이도를 새로 도입하므로 일반 RAG보다 항상 우월하다고 볼 근거는 없다.
9. 제품 비교는 이름이나 비감사 벤치마크가 아니라 실제 데이터 분포와 읽기/쓰기 혼합을 반영한 LDBC 계열 워크로드, 장애·복구·비용·운영성 검증으로 해야 한다.
10. 가장 낮은 위험의 도입법은 한 가지 고가치 질문과 작은 골든 데이터셋에서 시작해 관계형/검색 기준선과 비교하고, 품질·성능·운영 게이트를 통과할 때만 범위를 넓히는 것이다.

## 1. 범위, 방법, 한계

여기서 **그래프 엔지니어링**은 공식 단일 학문명이라기보다 실제 시스템을 만드는 실무적 우산 용어로 정의한다. 검색은 한국어·영어 키워드로 표준기관, 프로젝트/제품 공식 문서, 원 논문, 공식 벤치마크를 우선했고 블로그는 공식 연구팀의 구현 설명에 한정했다. 기능은 문서에 확인된 범주로만 적고 시장점유율이나 절대 성능 순위는 다루지 않았다. 사용한 자료와 주장 연결은 [sources.md](./sources.md)에 있다.

“웹의 모든 데이터”는 불가능하다. 웹은 무한·변동·접근제한·중복·비색인 자료를 포함하며, 2026-08-28의 상태도 이후 바뀐다. 이 조사는 대표성과 권위를 기준으로 한 **재현 가능한 목적 표본**이지 체계적 문헌고찰이나 전수조사가 아니다. 특히 제품 버전별 세부 기능, 가격, 관리형 서비스 지역, 라이선스 조항은 구매 시점에 다시 확인해야 한다. 성능 수치는 하드웨어·데이터 분포·쿼리·웜업·일관성 조건 없이는 이전할 수 없어 기재하지 않았다.

## 2. 분야 지도와 경계

| 층 | 핵심 질문 | 대표 산출물 | 그래프 엔지니어링과의 관계 |
|---|---|---|---|
| 그래프 이론 | 연결성·경로·색칠·매칭의 성질은? | 정리, 복잡도, 알고리즘 | 수학적 토대 |
| 그래프 데이터 엔지니어링 | 관계 데이터를 어떻게 안정적으로 공급하는가? | CDC/ETL, ID 매핑, 품질 규칙 | 생산 기반 |
| 그래프 DB/질의 | 어떤 모델·인덱스·실행계획으로 읽고 쓰는가? | 스키마, 쿼리, 저장/복구 | 운영 코어 |
| 지식 그래프/시맨틱 웹 | 식별자·어휘·의미·추론을 어떻게 공유하는가? | RDF, ontology, shapes, provenance | 의미 관리 특화 |
| 그래프 분석 | 구조에서 설명 가능한 신호를 어떻게 계산하는가? | 경로, 중심성, 커뮤니티, 컴포넌트 | OLAP 작업 |
| Graph ML/GNN | 구조와 특성으로 무엇을 예측하는가? | 임베딩, 노드/링크/그래프 예측 | 통계적 학습 작업 |
| GraphRAG | LLM의 검색·조직·생성을 그래프로 어떻게 보강하는가? | 그래프 인덱스, 근거 서브그래프, 답변 | 생성형 AI 응용 |

그래프가 유용한 충분조건은 “조인이 많다”가 아니다. 핵심 질문이 다단계 연결, 가변 깊이 경로, 패턴, 공동 이웃, 영향 전파 또는 관계 자체의 속성을 요구하고 그 구조가 반복 사용될 때 가치가 크다. 반대로 고정된 집계, 단순 키 조회, 소수의 안정적 조인, 강한 표준 BI 생태계만 필요한 경우 관계형/열형 저장소가 더 단순할 수 있다.

## 3. 데이터 모델

### 3.1 속성 그래프(property graph)

노드와 엣지는 식별자·레이블/타입·키-값 속성을 가지며 엣지는 보통 방향성이 있다. 관계에 금액, 역할, 신뢰도, 시간 같은 속성을 직접 붙여 경로 패턴을 자연스럽게 표현한다. Cypher/GQL 계열의 ASCII-art 패턴과 Gremlin 탐색이 대표적이다. 장점은 애플리케이션 친화적 모델링과 로컬 탐색이고, 약점은 제품 간 타입·null·멀티값·스키마·언어 지원 차이와 전역 의미/식별 규약의 부재다.

### 3.2 RDF/semantic graph

RDF는 IRI, blank node, literal로 이루어진 주어-술어-목적어 triple의 집합이며 dataset은 named graph를 포함한다. 공개 어휘 재사용, 웹 전역 식별, SPARQL federation, RDFS/OWL entailment에 강하다. RDF 1.2 후보 권고안은 triple term과 reification을 추가해 진술에 출처·시간·확신도를 붙이는 경로를 개선한다. 단, RDF 1.2는 기준일에 Candidate Recommendation이고 SHACL/SPARQL 1.2도 진행 중이므로 1.1/1.0과 혼동하면 안 된다. 추론은 “누락된 사실을 마법처럼 채우는 것”이 아니라 선택한 의미론이 논리적으로 함의하는 결과를 계산하는 것이며 표현력이 커질수록 비용과 설명 난도가 증가한다. OWL 2 EL/QL/RL은 각각 대규모 ontology, 관계형 질의 재작성, 규칙 기반 RDF 처리에 맞춰 표현력과 계산성을 교환한다.

### 3.3 하이퍼그래프와 대안 표현

일반 엣지가 두 끝점을 잇는다면 하이퍼엣지는 여러 노드의 고차 관계를 하나의 원자적 관계로 표현한다(예: 사람-직책-회사-기간이 함께 성립하는 임명 사건). 이진 엣지로 평탄화하면 원래 공동 참여 의미를 잃거나 조합 폭발이 생길 수 있다. 반대로 하이퍼그래프의 저장·질의·시각화·제품 상호운용 생태계는 좁다. 실무에서는 사건/관계 노드를 만든 reification, RDF reifier, 또는 별도 관계 테이블로 변환하는 편이 흔하다. 변환 시 원자성·순서·역할·중복의 의미를 문서화해야 한다.

### 3.4 선택 기준

| 기준 | 속성 그래프 | RDF | 하이퍼그래프 |
|---|---|---|---|
| 주된 강점 | 경로 탐색, 관계 속성, 앱 개발 | 전역 ID, 어휘/추론, 데이터 교환 | n-ary 관계의 원형 보존 |
| 스키마 | 암시적/선택적 제약이 흔함 | RDFS/OWL 의미 + SHACL 검증 | 구현별 상이 |
| 표준 언어 | GQL; SQL/PGQ는 SQL 결합 | SPARQL, RDF, OWL, SHACL | 지배적 범용 표준 부재 |
| 주요 위험 | 벤더 방언, supernode | 추론/모델 복잡성, triple 팽창 | 도구·운영 성숙도 |
| 적합한 시작 | 운영 관계 앱 | 통합 KG/연결 데이터 | 고차 관계가 본질적일 때 |

## 4. 저장, 인덱싱, 분산 실행

그래프 저장은 대체로 (a) 노드/엣지 레코드와 인접 포인터, (b) key-value/열 패밀리에 adjacency list, (c) 관계형 테이블과 graph view, (d) RDF SPO/POS/OSP 등 다중 순열 인덱스, (e) sparse matrix/CSR로 구현된다. 인덱스는 시작점 선택에 중요하지만 경로 확장 전체를 공짜로 만들지 않는다. 레이블/타입+식별키의 복합 인덱스, 유일성 제약, 텍스트·공간·시간·벡터 인덱스를 질문에서 역설계한다.

분산 그래프의 난점은 엣지가 파티션을 가로지를 때 네트워크 hop과 분산 조인이 늘고, 고차수 supernode가 핫스팟을 만드는 점이다. hash ID 분할은 균등하지만 locality가 나빠질 수 있고, community/업무키 분할은 locality는 좋지만 skew·재분할이 어렵다. edge-cut, vertex-cut/복제, workload-aware placement는 읽기 locality, 쓰기 fan-out, 저장 중복, 일관성을 맞바꾼다. 따라서 “수평 확장 지원”은 충분한 평가 항목이 아니다. 실제 top-k 고차수, cross-partition 비율, p95/p99 hop 수, 재균형 시간과 장애 중의 의미를 측정해야 한다.

### 실행 평면

| 평면 | 작업 | 최적화 초점 | 주의점 |
|---|---|---|---|
| OLTP | 점 조회, 짧은 가변경로, 쓰기 | 낮은 tail latency, ACID, 선택적 시작점 | 무제한 경로, fan-out 폭발 |
| OLAP | PageRank, WCC, 커뮤니티, 대규모 패턴 | 순차 처리량, 병렬성, 스냅샷 | 운영 복제본과 자원 격리 |
| BSP/vertex-centric | 반복 메시지 전달 | 파티션, checkpoint, 동기화 | straggler와 반복 장벽; Pregel이 고전적 모델 |
| sparse linear algebra | 행렬/벡터 primitive | CSR/CSC, semiring, CPU/GPU | 속성·동적 업데이트 변환 비용 |
| streaming | 엣지/노드 변화의 증분 뷰 | event time, idempotency, 상태/복구 | 늦은 이벤트, 삭제/정정, 순서 |

운영 그래프를 분석 엔진으로 무제한 복제하기보다 CDC/event log → 정규화/해소 → idempotent upsert → 버전 스냅샷 → 분석/ML publish 흐름을 둔다. Flink 같은 상태 기반 스트리밍 엔진은 event time과 checkpoint를 제공하지만, 그것이 그래프 수준 정확성을 자동 보장하지는 않는다. 엣지 두 끝점의 도착 순서, orphan 보류, tombstone, 재처리 시 결정론을 별도로 설계한다.

## 5. 표준과 쿼리 언어

| 기술 | 상태(2026-08-28) | 모델/스타일 | 강점 | 이식성 주의 |
|---|---|---|---|---|
| GQL | ISO/IEC 39075:2024 | 속성 그래프, 선언형 패턴/변경 | 최초의 독립 ISO 그래프 DB 언어 | 제품의 전체 적합성/버전 확인 필요 |
| SQL/PGQ | ISO/IEC 9075-16:2023, 2026 Corrigendum | 관계형 위 property graph query | 기존 SQL 데이터/도구와 결합 | 그래프 DML·제품 구현 범위 차이 |
| Cypher/openCypher | 제품 언어/공개 사양, GQL의 선행 영향 | 선언형 패턴 | 가독성, 생태계 | Cypher 버전과 openCypher/GQL은 동일하지 않음 |
| Gremlin | Apache TinkerPop | 명령형/함수형 traversal | 단계 조합, OLTP와 OLAP 추상화 | provider별 step 최적화/지원 차이 |
| SPARQL 1.1 | W3C Recommendation(2013) | RDF graph pattern | federation, property path, update | entailment regime와 endpoint 제한 명시 |
| RDF 1.2 | Candidate Recommendation(2026-04) | triple/dataset, triple term | 상호운용 모델과 진술 annotation 개선 | 아직 최종 Recommendation 아님 |
| OWL 2 | W3C Recommendation(2012) | ontology/description logic | 형식 의미와 추론 | profile별 계산성과 open-world 의미 |
| SHACL 1.0/1.2 | 1.0 Recommendation(2017); 1.2 WD(2026) | RDF shape validation/rules | 품질 계약과 검증 보고 | 추론 전/후 검증 순서, 1.2 초안 상태 |
| GraphBLAS | 포럼 API 명세 | sparse linear algebra | 알고리즘 primitive/병렬화 | DB 질의 언어가 아님 |

언어 선정은 문법 취향보다 모델 적합성, parameter binding, explain/profile, timeout/cancellation, typed result, transaction, driver, 표준 적합성 테스트를 본다. LLM이 쿼리를 생성할 때는 read-only 계정, allowlist, 깊이/결과/시간/비용 상한, 파싱과 정적 검증이 필수다.

## 6. 알고리즘, GNN, 벡터+그래프, GraphRAG

### 그래프 분석

- 탐색/경로: BFS/DFS, 최단경로, k-shortest, reachability. 가중치의 음수 여부, 방향, 단순경로 정의를 먼저 고정한다.
- 구조: degree, connected/strongly connected components, articulation/bridge, motif/triangle. 데이터 오류로 생긴 hub가 결과를 지배할 수 있다.
- 중요도/영향: PageRank, eigenvector, betweenness. “중심”은 정의별 의미가 다르고 인과성이 아니다.
- 군집: Louvain/Leiden, label propagation. resolution과 seed에 민감하므로 안정성·업무 해석을 검증한다.
- 유사도/추천: common neighbors, Jaccard, Adamic-Adar, random walk, embedding. 인기 편향과 신규 사용자 문제를 측정한다.

알고리즘 결과에는 graph snapshot ID, 방향/가중치, 필터, 구현/버전, 파라미터, seed, 코드 hash를 붙인다. LDBC Graphalytics는 BFS·WCC·PageRank 같은 분석 작업을, SNB Interactive/BI는 거래성 이웃 질의와 집계·조인 중심 분석을 구분한다. 공식 결과라면 감사 여부도 확인한다.

### GNN/graph ML

GNN은 이웃 메시지를 집계해 표현을 갱신하며 노드 분류, 링크 예측, 그래프 분류에 쓴다. 그래프 DB의 질의/ACID를 대체하지 않고 feature·label·split·학습/추론 파이프라인을 추가한다. 핵심 위험은 시간 누수(미래 엣지가 train에 포함), 이웃/라벨 누수, 허위 negative sampling, degree 편향, inductive/transductive 혼동, oversmoothing, oversquashing, 대규모 이웃 샘플링 비용, drift다. OGB처럼 고정 split과 evaluator를 사용하되 최종 평가는 실제 시간·업무 비용·baseline을 반영한다. 설명 가능성은 attention weight나 path 하나를 곧바로 원인으로 간주해서는 안 된다.

### vector + graph

벡터는 의미적으로 가까운 후보를 잘 찾고, 그래프는 타입·권한·시간·경로·출처 제약과 관계적 확장을 잘한다. 대표 흐름은 `(1) vector top-k → (2) graph constraint/traversal → (3) rerank` 또는 `(1) entity linking → (2) bounded subgraph → (3) text/vector evidence 결합`이다. 임베딩 모델/차원/정규화/version을 데이터 lineage로 관리하고 재임베딩 중 구·신 버전을 섞지 않는다. Neo4j 공식 문서는 노드/관계 vector index와 버전별 filtering 변화를 명시하므로 “벡터 지원” 한 칸 대신 대상, filter, consistency, rebuild를 비교해야 한다.

### GraphRAG

Microsoft GraphRAG의 한 구현은 텍스트에서 entity/relationship을 추출하고 community와 community report를 만든 뒤 local/global/DRIFT 검색을 제공한다. 이는 GraphRAG 전체의 유일한 정의가 아니다. 최근 survey는 query processor, retriever, organizer, generator, graph data source로 더 넓게 분류한다. 평가축은 answer correctness뿐 아니라 retrieval recall/precision, claim-evidence 연결, entity resolution, temporal correctness, abstention, latency, indexing/query token 비용, graph freshness다. 같은 corpus/question에서 BM25·dense RAG·hybrid RAG 기준선과 비교해야 하며, 추출 graph를 원문 근거 없이 “사실”로 승격하면 안 된다.

## 7. E2E 수명주기와 참조 아키텍처

```text
소스(DB/API/문서/이벤트)
  -> 계약·CDC·원문 보존
  -> 정규화/파싱/PII 분류
  -> ID 발급 + entity resolution(점수/근거/검토)
  -> ontology/schema + shape/constraint 검증
  -> graph upsert/tombstone + provenance + valid/transaction time
  -> [운영 graph] --snapshot/CDC--> [분석/ML graph]
         |                              |-> algorithms/features/GNN
         |-> query API                  |-> vector index
         `-> bounded traversal          `-> GraphRAG retrieval
  -> 정책 필터/근거 조립/API
  -> 품질·성능·비용·보안·drift 관측
  -> 백업/복구/삭제/정정/재구축
```

### 수명주기 계약

1. **질문 계약:** 사용자/업무 질문, 그래프가 필요한 이유, latency/freshness/정확도 SLO와 금지된 사용을 적는다.
2. **개념/ID:** canonical ID와 source ID를 분리하고 node/edge 타입, 방향, cardinality, 필수 속성, 단위를 정의한다.
3. **해소:** deterministic rule → 후보 생성 → 확률/ML 점수 → threshold와 human review로 진행한다. merge뿐 아니라 unmerge와 audit를 지원한다.
4. **시간:** `valid_from/to`(현실에서 참인 시각)와 `recorded_from/to`(시스템이 안 시각)를 구별한다. current-only overwrite는 역사 질문을 파괴한다.
5. **출처:** source document/record, extraction method/model, confidence, ingest run, license/consent를 주장 단위 또는 적절한 묶음 단위로 연결한다. W3C PROV-O는 Entity/Activity/Agent 중심의 교환 어휘를 제공한다.
6. **검증:** schema/shape, referential integrity, orphan, duplicate, impossible time interval, degree distribution, component 변화, source coverage를 검사한다.
7. **발행:** transactional batch 또는 idempotent event로 publish하고 부분 실패의 quarantine/DLQ와 replay를 둔다.
8. **소비:** parameterized query, 깊이/결과 한도, materialized projection, snapshot binding을 제공한다.
9. **운영:** query plan/latency, cache, locks, replication lag, hot key, cross-partition traffic, ingest lag, validation error, ER precision을 관측한다.
10. **종료:** source deletion과 법적 삭제가 원문·그래프·파생 feature·embedding·cache·backup에 어떻게 전파되는지 시험한다.

## 8. 성능, 테스트, 관측성

용량 계획의 최소 변수는 |V|, |E|, 타입/속성별 크기, degree의 p50/p95/p99/max, 그래프 밀도, 성장률, 쓰기 burst, TTL/history 보존, 인덱스 증폭이다. 평균 degree만으로 supernode 비용을 숨기지 않는다.

테스트 피라미드는 다음과 같다.

- 모델/계약: ID 안정성, cardinality, 시간 경계, shape/constraint의 positive/negative fixture.
- 쿼리: 작은 oracle graph에 대한 정확 결과, null/missing, cycle, duplicate path, disconnected, supernode cases.
- pipeline: duplicate/out-of-order/replay/delete/schema evolution과 partial failure의 idempotency.
- 성능: 실제 degree/skew와 read/write mix, cold/warm, concurrency, p50/p95/p99, timeout, plan regression.
- 회복: 노드/zone/network failure, replica lag, backup restore와 point-in-time recovery의 실제 RTO/RPO.
- 분석/ML: snapshot 재현성, leakage, seed variance, calibration, subgroup fairness, drift와 기준선.
- 보안: 권한 우회 경로, inference attack, export/backup/log 유출, 생성 쿼리의 resource exhaustion.

관측의 단위는 서버뿐 아니라 질문이다. `query-template/version → plan → scanned/expanded nodes/edges → result cardinality → latency/cost/error`를 연결하고, pipeline에는 source offset → transform/ER version → graph commit/snapshot을 연결한다. 무제한 variable-length path와 Cartesian product를 정적 lint하고 런타임 budget으로 차단한다.

## 9. 보안·개인정보·거버넌스

그래프는 공개 속성만 결합해도 민감한 관계를 추론할 수 있다. 행/노드 권한만으로는 경로가 중간 노드·엣지·집계를 통해 정보를 누출할 수 있으므로 query/result 단계 모두에서 label/type/tenant/relationship 정책을 적용한다. 최소권한, 네트워크 격리, 전송/저장 암호화, secret rotation, audit, export 통제는 기본이다.

특히 다음을 위협모델에 넣는다: 존재 유추(결과 수/latency), membership inference, shortest-path를 통한 숨은 관계 노출, high-degree 재식별, federation/SERVICE의 외부 유출, 악의적 속성 텍스트를 통한 GraphRAG prompt injection, LLM 생성 쿼리의 쓰기/대량 탐색. 민감도·법적 근거·retention은 노드뿐 아니라 엣지와 파생 결과에 태깅한다. 삭제 가능성은 append-only provenance와 상충하므로 audit 보존의 법적 근거, pseudonymization, 암호키 폐기, backup 만료 정책을 Human이 결정해야 한다.

## 10. 생태계: 기능 범주와 선택 기준

아래는 완전한 제품 목록이 아니며 기능을 공식 문서로 확인한 대표군이다.

| 범주/예 | 확인된 성격 | 검토 포인트 |
|---|---|---|
| Neo4j | property graph, Cypher, GDS, vector index; self-managed/managed 제품군 | Cypher/GQL 버전, edition별 clustering/security/GDS, 라이선스 |
| Amazon Neptune | 관리형; RDF/SPARQL 및 property graph Gremlin/openCypher, Database와 Analytics | 두 모델 간 질의 경계, AWS 종속, feature/region/비용 |
| JanusGraph | Apache 2 계열 분산 property graph; Gremlin; Cassandra/HBase/Scylla 등 backend와 별도 search index | 다중 컴포넌트 운영, transaction/consistency가 backend에 의존 |
| Apache TinkerPop | DB가 아니라 graph computing/traversal 프레임워크; Gremlin, OLTP/OLAP abstraction | provider별 지원 step과 optimization |
| ArangoDB | graph+document+key-value+search/vector의 multi-model, AQL, cluster | BSL/상용 조건, cross-shard traversal, multi-model 이점 실증 |
| Memgraph | Cypher property graph, Kafka/Redpanda/Pulsar stream 연결, 동적 알고리즘 표방 | durability/HA/edition/connector의 실제 보장 |
| Kùzu | MIT, embedded/serverless property graph, Cypher, columnar/CSR, vector/full-text | 2025년 이후 프로젝트/extension 배포 상태와 지원성 |
| RDF triplestore/semantic platform군 | SPARQL, named graph, 일부 entailment/SHACL/federation | 표준 적합성, reasoning profile, validation/transaction/HA는 제품별 검증 |
| 분석 라이브러리군 | NetworkX/igraph(단일기계), Spark/GraphX, cuGraph, GraphBLAS 계열 | 데이터 이동, 동적 업데이트, GPU 메모리, 재현성 |
| GNN 프레임워크군 | PyTorch Geometric, DGL 등 message-passing/샘플링 | graph DB가 아님; feature store/serving 별도 |

선택 RFP는 모델·언어만 묻지 말고 ACID/isolation, HA topology, online backup/PITR, rolling upgrade, encryption/RBAC/audit, bulk+CDC, schema/constraint, temporal, explain/profile, timeout, driver, metrics, Kubernetes/managed 책임경계, egress·storage·compute·LLM 총비용, 라이선스와 exit export를 포함한다. 후보마다 같은 acceptance dataset/workload를 실행한다.

## 11. 사용 사례별 적합성과 부적합성

| 사용 사례 | 그래프가 강한 이유 | 부적합/경계 | 핵심 평가 |
|---|---|---|---|
| 사기/AML | 계정-기기-거래의 다단계 ring·공유 자원 | 최종 결정 자동화, 실시간 규칙만 필요한 단순 사례 | time-aware recall, false positive, 설명 경로, latency |
| IAM/보안 | 사용자-역할-리소스 attack path | policy engine의 authoritative source를 무심코 대체 | 권한 시점, deny 의미, path explosion |
| 추천 | 다종 관계·공동 이웃·경로 설명 | 단순 인기/콘텐츠 추천이 충분 | 온라인 lift, 편향, freshness, cold start |
| 공급망/lineage | 부품·공정·배포 영향 전파 | source provenance가 빈약한 시각화 전용 그래프 | coverage, temporal reachability, blast-radius 정확도 |
| 지식 통합 | 이질 ID/어휘 연결, provenance | ER 품질·ownership 없이 모든 데이터를 연결 | precision/recall, competency questions, SHACL |
| 네트워크/설비 | topology, 장애 영향, 경로 | telemetry 시계열 자체의 주 저장소 | topology freshness, temporal path, supernode |
| 생명과학 | 이질 관계·ontology·문헌 근거 | 상관 경로를 인과 증거로 해석 | evidence grade, ontology version, reproducibility |
| GraphRAG | 관계적/전역 질문과 근거 조직 | 작은 문서집·단순 사실 검색; 비용 제한이 엄격 | groundedness, retrieval, abstention, total cost |

## 12. 안티패턴

- “그래프 DB를 샀으니 질문을 찾는다”: 기술이 아니라 competency question에서 시작한다.
- 모든 것을 노드/엣지로 복제: authoritative source와 freshness/삭제 경계가 사라진다.
- 문자열 이름을 ID로 사용: 철자·다국어·이름 변경이 잘못된 merge를 만든다.
- ER merge를 비가역 처리: 오결합 하나가 많은 경로를 오염시킨다.
- 현재 상태 overwrite: 역사·감사·학습 재현이 불가능해진다.
- 무제한 탐색/OPTIONAL 조합/Cartesian product: tail latency와 비용 폭발을 유발한다.
- supernode를 무시한 평균 기반 설계: 실제 최악경로가 숨는다.
- 운영 OLTP에서 전역 PageRank 실행: 자원 격리와 일관된 snapshot이 깨진다.
- vendor demo/비감사 benchmark로 우열 단정: workload와 공개 조건이 다르다.
- ontology를 중앙위원회가 완성할 때까지 ingestion 중단: 질문 기반의 얇은 vertical slice와 versioning이 낫다.
- GraphRAG 추출 엣지를 원문 근거 없이 사실로 취급: 환각의 구조화일 뿐이다.
- GNN 점수를 인과/설명으로 간주: 예측과 의사결정의 책임 경계를 흐린다.

## 13. 팀과 역량

최소 역할은 domain/data owner(정의·품질·승인), graph/data engineer(모델·pipeline·ID), database/SRE(성능·HA·복구), analyst/algorithm engineer, semantic/ontology engineer(RDF 시), ML engineer(GNN/RAG 시), security/privacy/governance다. 소규모 팀에서는 한 사람이 겸임할 수 있지만 승인권과 독립 검증은 구분한다. 공통 역량은 그래프 모델링, 분산 시스템, 쿼리 계획, 통계/실험, 데이터 계약과 lineage, 위협모델, 비용 모델이다.

## 14. 도입 체크리스트와 단계별 로드맵

### 사전 체크리스트

- [ ] 관계형/검색 baseline보다 그래프가 유리할 구체적 질문 3~10개가 있는가?
- [ ] authoritative source, owner, refresh, 삭제·정정 규칙이 있는가?
- [ ] canonical ID, ER threshold와 unmerge 절차가 있는가?
- [ ] edge 방향·역할·cardinality·시간·provenance가 정의됐는가?
- [ ] 예상 |V|/|E|, degree skew, growth, read/write mix를 측정했는가?
- [ ] latency/freshness/quality/cost/availability SLO와 실패 허용값이 있는가?
- [ ] 개인정보·tenant·경로 기반 추론 위협과 retention을 검토했는가?
- [ ] 후보 엔진의 라이선스·운영 모델·export/exit를 확인했는가?
- [ ] 골든 그래프와 정확성/성능/복구 acceptance suite가 있는가?
- [ ] 그래프가 이기지 못할 경우 중단 기준이 있는가?

### 로드맵

**0단계—문제 프레이밍(1~2주):** competency question, baseline, 금지 사용, SLO, 데이터 권한을 고정한다. 산출물은 질문-데이터-측정치 표다.

**1단계—얇은 vertical slice(2~6주):** 2~4개 node type, 핵심 edge, 작은 골든셋으로 두 모델/엔진 이내를 실험한다. ER·시간·provenance를 처음부터 포함한다. 게이트는 baseline 대비 정확성/개발성/성능/비용의 명시적 이득이다.

**2단계—생산 가능성(4~10주):** CDC/replay, constraint, query budget, RBAC, metrics, backup/restore, 장애주입, schema evolution을 구현·검증한다. LDBC 모양을 참고하되 실제 workload로 판정한다.

**3단계—제한 운영:** 한 tenant/업무 흐름에서 shadow/canary로 운영하고 p99, 오류, ER 검토량, freshness, 비용, 사용자 결과를 관찰한다. 자동 의사결정은 별도 위험 승인을 받는다.

**4단계—확장:** 통과한 모델·pipeline template만 재사용하고 ontology/ID council, query registry, snapshot/model registry, chargeback을 둔다. OLTP/OLAP/ML을 필요에 따라 분리한다.

**5단계—지속 평가/퇴출:** 분기별로 baseline, 라이선스, restore, deletion, drift, 사용되지 않는 graph 자산을 재평가하고 export와 decommission을 시험한다.

## 15. 리스크, 상충 근거, 미해결 쟁점

1. **표준화 대 구현 격차:** GQL은 표준이지만 각 제품의 채택 범위는 다르다. openCypher 호환을 GQL 적합성으로 간주할 수 없다.
2. **RDF 1.2 성숙도:** triple term/reification은 provenance 표현을 개선하지만 Candidate Recommendation이며 SPARQL/SHACL 1.2도 기준일 현재 최종 표준이 아니다. production은 구현 상호운용 시험이 필요하다.
3. **일관성 대 분산성:** cross-partition transaction/탐색은 latency·availability와 맞바꾼다. 하나의 보편적 정답이 없다.
4. **표현력 대 계산성:** OWL profile, 복잡한 path, 하이퍼그래프는 의미를 풍부하게 하지만 최적화와 설명을 어렵게 한다.
5. **신선도 대 재현성:** 실시간 graph는 최신이나 분석/ML 재현을 깨뜨릴 수 있다. event log와 immutable snapshot을 함께 둔다.
6. **정확성 대 coverage:** 공격적 ER은 연결을 늘리지만 false merge의 전파 비용이 크다. threshold는 업무 손실 함수에 따라 Human이 정한다.
7. **GraphRAG 품질 대 비용:** community report/LLM extraction은 전역 질문에 도움을 줄 수 있으나 indexing 비용과 오류 표면을 키운다. corpus별 대조실험 없이는 결론 불가다.
8. **privacy 대 연결 가치:** 연결이 많을수록 inference/re-identification 위험도 커진다. 허용 위험과 법적 근거는 기술팀이 단독 결정할 수 없다.
9. **벤치마크 외삽:** LDBC/OGB는 재현 가능한 공통점을 제공하지만 실제 데이터의 skew·정책·장애·비용을 대신하지 않는다.
10. **동적·시간 그래프:** 시간에 따라 reachability 자체가 달라지고 정적 알고리즘을 snapshot마다 재실행하는 것은 비용/의미 모두 불충분할 수 있다. 범용 temporal query/streaming 표준과 증분 알고리즘은 여전히 파편화되어 있다.

## 16. 결론과 후속 조사

그래프 엔지니어링의 핵심은 “연결을 저장하는 DB”가 아니라 질문과 의미를 식별자·시간·출처에 고정하고, 서로 다른 실행 평면을 데이터 계약과 운영 통제로 이어 붙이는 일이다. 모델과 제품은 그 뒤의 선택이다. 성공 판단은 더 멋진 시각화가 아니라 baseline 대비 정확한 답, tail latency, freshness, 복구 가능성, 총비용, 보안/삭제 가능성으로 내려야 한다.

가장 작은 유용한 후속 Inquiry는 대상 업무 한 가지를 선택해 (1) 10개 competency question, (2) 1천~10만 규모의 대표 골든 그래프, (3) 관계형/검색 baseline, (4) 2개 이하 후보 엔진, (5) 정확성·p99·CDC replay·restore·삭제 acceptance test와 3년 TCO를 설계하는 것이다. 제품 채택과 privacy/위험 threshold는 Human 결정으로 남는다.
