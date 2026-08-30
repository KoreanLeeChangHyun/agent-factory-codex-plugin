# 그래프 엔지니어링 조사 출처

> 2026-08-28 확인. 아래 날짜는 문서의 발행/표준 날짜가 확인될 때만 표기했다. 접근일은 모두 조사 기준일이다.

## 표준·데이터 모델·질의 언어

- **ISO/IEC 39075:2024 — Database languages — GQL** — ISO/IEC JTC 1/SC 32, 2024-04. https://www.iso.org/standard/76120.html — GQL이 property graph 구조·조회·변경을 규정하는 최초판 국제표준이라는 주장.
- **ISO/IEC 9075-16:2023/Cor 1:2026 — SQL/PGQ Corrigendum 1** — ISO/IEC, 2026-08. https://www.iso.org/standard/93698.html — SQL/PGQ의 2026년 정오표 상태와 SQL Part 16 식별.
- **openCypher Resources** — openCypher project, 날짜 미표기. https://opencypher.org/resources/ — 공개 grammar/spec과 GQL로 이어진 프로젝트 관계 확인.
- **Apache TinkerPop** — Apache Software Foundation, 2026 릴리스 정보. https://tinkerpop.apache.org/ — Gremlin이 property graph의 functional data-flow traversal 언어이고 TinkerPop이 OLTP/OLAP abstraction을 제공한다는 주장.
- **SPARQL 1.1 Query Language** — W3C, Recommendation 2013-03-21. https://www.w3.org/TR/sparql11-query/ — RDF graph pattern, property path, query semantics.
- **SPARQL 1.1 Recommendations announcement** — W3C, 2013-03-21. https://www.w3.org/news/2013/eleven-sparql-11-specifications-are-w3c-recommendations/ — aggregate, subquery, negation, update, protocol 등 1.1 범위.
- **RDF 1.2 Concepts and Abstract Data Model** — W3C, Candidate Recommendation Snapshot 2026-04-07. https://www.w3.org/TR/rdf12-concepts/ — RDF graph/dataset, triple term, reifier 및 표준 단계.
- **OWL 2 Document Overview (Second Edition)** — W3C, Recommendation 2012-12-11. https://www.w3.org/TR/owl2-overview/ — ontology, semantics, EL/QL/RL profile의 목적과 계산성 교환.
- **SHACL 1.0** — W3C, Recommendation 2017-07-20. https://www.w3.org/TR/shacl/ — 안정 SHACL 기반과 RDF shape validation.
- **SHACL 1.2 Core** — W3C, Working Draft 2026-05/06. https://www.w3.org/TR/shacl12-core/ — 1.2가 진행 중인 초안이며 shape/validation/rules 확장 상태라는 주장.
- **SPARQL 1.2 Query Language** — W3C, Working Draft 2026. https://www.w3.org/TR/sparql12-query/ — 1.2의 기준일 비최종 상태 확인.
- **PROV-O: The PROV Ontology** — W3C, Recommendation 2013-04-30. https://www.w3.org/TR/prov-o/ — Entity/Activity/Agent 기반 provenance 교환 어휘.
- **GraphBLAS C++ API Specification v1.0** — GraphBLAS Forum. https://graphblas.org/graphblas-api-cpp/ — semiring 기반 sparse matrix/vector primitive로 graph algorithm을 표현한다는 주장.

## 처리 아키텍처·알고리즘·벤치마크

- **Pregel: a system for large-scale graph processing** — Malewicz et al., ACM SIGMOD 2010. https://research.google/pubs/pregel-a-system-for-large-scale-graph-processing/ — vertex-centric bulk-synchronous 대규모 그래프 처리의 고전 모델.
- **LDBC/GDC Benchmarks** — Graph Data Council, 계속 갱신. https://ldbcouncil.org/benchmarks/ — SNB Interactive/BI, Graphalytics, FinBench, RDF/SPARQL benchmark의 범주.
- **LDBC Social Network Benchmark** — Graph Data Council. https://ldbcouncil.org/benchmarks/snb/ — Interactive의 이웃 중심 트랜잭션과 BI의 집계·조인 중심 분석 workload 구분.
- **Graphalytics specification** — Graph Data Council. https://ldbcouncil.org/ldbc_graphalytics_docs/graphalytics_spec.pdf — BFS, WCC, PageRank 등 분석 benchmark의 job/run 및 자원 보고 원칙.
- **Apache Flink 2.3 Documentation** — Apache Software Foundation, 2026-08. https://nightlies.apache.org/flink/flink-docs-stable/ — bounded/unbounded stream, stateful processing, event time, checkpoint에 대한 근거.
- **Open Graph Benchmark** — Stanford OGB team, 계속 갱신. https://ogb.stanford.edu/index.html — 실제 규모 데이터, node/link/graph prediction, 표준 split·evaluator.

## Graph ML·시간 그래프·GraphRAG 연구

- **Graph Neural Networks: A Review of Methods and Applications** — Zhou et al., 2018/2020. https://arxiv.org/abs/1812.08434 — message passing과 GCN/GAT 등 GNN 범주·응용.
- **A Survey on Oversmoothing in Graph Neural Networks** — Rusch, Bronstein, Mishra, 2023. https://arxiv.org/abs/2303.10993 — 깊이가 증가할 때 node representation이 유사해지는 oversmoothing과 완화의 한계.
- **An Introduction to Temporal Graphs: An Algorithmic Perspective** — Michail, 2015. https://arxiv.org/abs/1503.00278 — 시간 차원이 reachability와 알고리즘 문제를 근본적으로 바꾼다는 근거.
- **Bitemporal Property Graphs to Organize Evolving Systems** — Rost et al., 2021. https://arxiv.org/abs/2111.13499 — valid/transaction time을 함께 다루는 bitemporal property graph와 continuous event 연구.
- **Retrieval-Augmented Generation with Graphs (GraphRAG): A Survey** — Han et al., 2024/2025. https://arxiv.org/abs/2501.00309 — query processor/retriever/organizer/generator/data source의 넓은 GraphRAG 분류와 도전과제.
- **GraphRAG: Improving global search via dynamic community selection** — Microsoft Research, 2024. https://www.microsoft.com/en-us/research/blog/graphrag-improving-global-search-via-dynamic-community-selection/ — 문서 segment, entity/relation, hierarchical community report, global query의 구현 설명.
- **Introducing DRIFT Search** — Microsoft Research, 2024. https://www.microsoft.com/en-us/research/blog/introducing-drift-search-combining-global-and-local-search-methods-to-improve-quality-and-efficiency/ — local/global을 결합하는 DRIFT 및 비용-품질 trade-off.

## 대표 구현·제품 공식 자료

- **Neo4j Cypher Manual: Vector indexes** — Neo4j, 계속 갱신. https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/ — 노드/관계 vector index와 버전별 filtering 기능이 다르다는 주장.
- **Neo4j Documentation** — Neo4j. https://neo4j.com/docs/ — Cypher, Graph Data Science, import, operations 범주 확인.
- **Amazon Neptune Documentation** — AWS. https://docs.aws.amazon.com/neptune/ — 관리형 Database/Analytics, SPARQL·Gremlin·openCypher와 graph algorithms 지원 범주.
- **Querying a Neptune Graph** — AWS. https://docs.aws.amazon.com/neptune/latest/userguide/access-graph-queries.html — RDF에는 SPARQL, property graph에는 Gremlin/openCypher라는 질의 경계.
- **JanusGraph official site/documentation** — JanusGraph project. https://janusgraph.org/ ; https://docs.janusgraph.org/configs/configuration-reference/ — Gremlin, Cassandra/HBase/Scylla 등 storage backend, 별도 search backend, Spark OLAP 범주.
- **ArangoDB 3.12 feature list** — ArangoDB. https://docs.arango.ai/arangodb/stable/features/list/ — graph/document/key-value multi-model, AQL과 공통 core 기능.
- **ArangoDB cluster deployments** — ArangoDB. https://docs.arango.ai/arangodb/stable/deploy/cluster/ — sharding과 cluster 배치 범주.
- **ArangoDB features/licensing notice** — ArangoDB. https://docs.arango.ai/arangodb/stable/features/ — graph/document/vector/search와 source의 BSL 1.1 표기; 실제 채택 시 조항 재확인 필요.
- **Memgraph stream ingestion docs** — Memgraph. https://memgraph.com/docs/data-streams — Kafka/Redpanda/Pulsar 기반 streaming ingestion 기능 확인. (공식 사이트의 URL/문서는 변경될 수 있음.)
- **Kùzu repository and documentation pointer** — Kùzu project, 2025 상태. https://github.com/kuzudb/kuzu — MIT, embedded property graph, Cypher, columnar/CSR, vector/full-text 및 extension 배포 변경.

## 모델링·통합 보조 연구

- **A comprehensive survey of entity alignment for knowledge graphs** — Zeng et al., 2021. https://doi.org/10.1016/j.aiopen.2021.02.002 — entity alignment/matching/resolution이 knowledge fusion의 핵심이라는 근거.
- **Hypergraph: A Unified and Uniform Definition...** — Ouvrard et al., 2024. https://arxiv.org/abs/2405.12235 — hyperedge가 고차 관계를 표현하며 모델 정의가 단일하지 않다는 근거.

## 출처상의 제한과 상충 기록

- ISO 본문 전체는 유료일 수 있어 공개 abstract와 catalogue metadata로 상태·범위만 확인했다.
- W3C 1.2 문서들은 각각 Working Draft/Candidate Recommendation 상태가 달라 “W3C 표준”으로 뭉뚱그리지 않았다.
- 제품 기능 페이지는 공급자 주장이다. 기능 존재의 근거로만 사용했으며 성능 우월성·시장 지위의 근거로 사용하지 않았다.
- Kùzu는 공식 repository가 2025년 이후 extension server 제공 변화 등을 공지하므로 장기 지원성은 별도 검토 대상이다.
- LDBC workload는 공정한 공통 비교에 유용하지만 실제 업무 workload의 대체가 아니며, 공식 결과 표기는 감사 조건을 확인해야 한다.
