# 후속 조사 요청: 그래프 엔지니어링의 최신 AI 동향

기존 `graph-engineering` Inquiry의 후속 작업이다. 같은 워크스페이스와 관리 세션을 사용하되 기존 `report.md`와 `sources.md`를 덮어쓰지 않는다.

## 사용자 요청

"그래프 엔지니어링 최신 AI 정보를 기반으로 조사해주세요"

## 기준과 목표

- 조사 기준일은 2026-08-28이다.
- 그래프 엔지니어링과 AI가 만나는 최신 실무·연구 동향을 한국어로 조사한다.
- 특히 2025~2026 자료를 우선하되, 기술 계보를 설명하는 데 필요한 2023~2024 원자료는 포함할 수 있다.
- 단순 트렌드 목록이 아니라 기술의 성숙도, 검증 수준, 시스템 설계 영향, 비용과 리스크, 채택 판단 기준을 분석한다.

## 조사 범위

1. GraphRAG의 최신 유형과 발전: KG 기반, community/hierarchical, path/subgraph, hybrid vector+graph, temporal/dynamic GraphRAG, multimodal GraphRAG, agentic GraphRAG.
2. LLM + Knowledge Graph의 양방향 결합: KG-enhanced LLM과 LLM-enhanced KG, ontology/schema 생성, entity/relation extraction, entity resolution, query generation, reasoning, provenance/grounding.
3. Graph Foundation Models와 범용 그래프 표현학습: pretraining, transfer, in-context learning, graph transformers, text-attributed graph, heterogeneous/dynamic graph. 'foundation model'이라는 명칭의 과장 가능성도 평가.
4. 최신 GNN/Graph ML 엔지니어링: scalability, sampling, distributed/GPU, temporal GNN, graph anomaly/fraud/recommendation, MLOps와 feature/snapshot 관리.
5. 생성형 그래프 모델과 과학/분자/코드/소프트웨어 그래프 응용. 범용 그래프 엔지니어링에 실제로 전이 가능한 부분과 도메인 한계를 구분.
6. AI agent의 graph memory, long-term memory, episodic/semantic/temporal knowledge graph, multi-agent graph coordination. 논문 근거와 제품 주장을 분리.
7. 최신 오픈소스/공식 구현과 클라우드·DB 제품의 AI 기능: Microsoft GraphRAG, Neo4j, Amazon Neptune, Google/Vertex AI 관련 graph capability, Apache/OSS, LightRAG/HippoRAG/Graphiti 등 확인 가능한 대표 사례. 기능 존재와 성능 우월성을 구분.
8. 평가·벤치마크: retrieval/answer/groundedness, graph construction quality, entity resolution, temporal correctness, latency/token/indexing/TCO, GraphRAG 전용 benchmark의 한계, baseline 설계.
9. 안전·거버넌스: hallucinated edges, prompt injection through graph/text properties, generated-query abuse, authorization-aware traversal, privacy inference, provenance, deletion, model/embedding drift.
10. 12~24개월 전망과 아직 검증되지 않은 주장. 사실, 합리적 추론, 전망을 명시적으로 구분.

## 웹 및 출처 규칙

- 실제 웹 검색을 수행하고 현재 상태를 확인한다.
- 논문 원문(arXiv는 원 논문일 때 허용), 학회, 연구기관, 표준기관, 공식 프로젝트 저장소/문서, 공급자 공식 문서를 우선한다.
- 가능하면 2025~2026의 최신 원자료를 직접 확인하며, 날짜와 버전/상태를 기록한다.
- 기술적 주장마다 가까운 위치에 클릭 가능한 URL을 둔다.
- 공급자 벤치마크와 블로그는 공급자 주장으로 표시하고 독립 결과처럼 쓰지 않는다.
- survey만으로 핵심 주장을 단정하지 말고 대표 원 논문/공식 구현을 함께 찾는다.
- 확인할 수 없는 유행어, 시장점유율, 절대 성능 순위는 제외한다.
- 동일 이름의 서로 다른 GraphRAG 정의와 벤치마크 조건 불일치를 기록한다.

## 결과물

1. `.agent-factory/inquery/graph-engineering/ai-latest-report.md`
   - 10문장 이내 핵심 요약
   - 조사 방법·기준일·한계
   - 최신 AI 분야 지도와 기술 분류
   - 2025~2026 주요 변화 타임라인
   - 각 기술군의 원리, 성숙도, 대표 근거, 실무 아키텍처 영향
   - 대표 논문/프로젝트/제품 비교표
   - 평가 프레임워크와 권장 baseline
   - production 참조 아키텍처
   - 도입 체크리스트 및 30/60/90일 실험 계획
   - 과장된 주장/실패 모드/보안·거버넌스
   - 12~24개월 전망(사실/추론/전망 구분)
   - 결론과 최소 후속 Inquiry
2. `.agent-factory/inquery/graph-engineering/ai-latest-sources.md`
   - 범주별 제목, 저자/기관, 날짜, URL, 자료 유형, 어떤 주장에 사용했는지
3. 관리 런의 `result.md`에는 조사 경계, 가장 중요한 최신 변화, 결과 파일, 한계와 후속 조사를 간결히 기록한다.

이 자료는 임시 Inquiry이며 Specification이나 Project Skill로 승격하지 않는다. 제품 선택, 테스트 실행, 외부 쓰기, 구현 변경은 하지 않는다.
