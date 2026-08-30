# 후속 조사 요청: RAG를 제외한 그래프 엔지니어링의 AI

기존 `graph-engineering` Inquiry와 같은 관리 세션을 사용한다. 기존 문서들은 덮어쓰지 않는다.

## 사용자 요청

"그래프 엔지니어링이 RAG 말고 AI 관점으로 조사하세요"

## 명시적 경계

- **RAG, GraphRAG, 문서 검색 증강 생성, 벡터 검색 기반 답변 생성은 본 조사에서 제외한다.**
- LLM은 그래프를 학습·추론·생성·계획·변환하는 모델 또는 그래프 AI 개발 도구로 쓰이는 경우만 포함한다.
- 기준일은 2026-08-28이며 2025~2026 최신 원자료를 우선한다. 계보 설명에 필요한 이전 핵심 논문은 제한적으로 포함한다.

## 조사 질문

그래프 구조를 AI의 입력·학습 편향·추론 상태·생성 대상·행동 공간으로 사용할 때 어떤 기술이 존재하고, 무엇이 실제로 검증됐으며, 이를 생산 시스템으로 만드는 그래프 엔지니어링은 무엇인가?

## 조사 범위

1. **Geometric Deep Learning과 GNN:** message passing, spectral/spatial, equivariant GNN, graph attention/transformer, positional/structural encoding, higher-order graph learning.
2. **그래프 학습 과제:** node/edge/graph classification, link prediction/KG completion, anomaly/fraud, recommender/ranking, community, graph regression, combinatorial prediction.
3. **Temporal·dynamic·streaming·heterogeneous graph AI:** event-time 학습, temporal leakage, continual learning, heterogeneous relation/type 처리, concept drift.
4. **Graph Foundation Model과 self-supervised/pretrained graph model:** universal/task/domain-specific 구분, transfer·few/zero-shot·in-context 주장, scaling law와 한계.
5. **Knowledge Graph AI(비-RAG):** embedding, completion, rule/ontology reasoning, neural-symbolic reasoning, LLM을 이용한 KG construction/validation/query generation. 검색 증강 답변은 제외.
6. **Graph generative AI:** graph diffusion/autoregressive generation, molecule/material/protein, circuit/network/code/scene graph 생성과 제약 만족·유효성 검증.
7. **그래프와 인과 AI:** causal graph discovery, SCM과 graph learning의 관계, intervention/counterfactual, 상관 그래프를 인과 그래프로 오해하는 위험.
8. **그래프 강화학습과 조합 최적화:** routing, scheduling, chip design, network control, molecule design, relational RL, world model/agent planning에서 graph state/action 사용. GraphRAG는 제외.
9. **대규모 AI 시스템 엔지니어링:** sampling, partition, distributed/GPU, sparse kernels, graph/feature store, offline/online parity, training/inference serving, snapshot/versioning, incremental update.
10. **평가·MLOps·안전:** OGB/TGB 등 benchmark, split/leakage/negative sampling, calibration/fairness/explainability/robustness/privacy, adversarial graph attack, monitoring/drift/deletion/reproducibility.
11. **도구·생태계:** PyTorch Geometric, DGL, GraphStorm, cuGraph/GNN, Jraph 등 공식적으로 확인 가능한 프레임워크와 graph DB/feature pipeline 연계. 제품 기능은 공식 문서로만 확인하고 절대 순위를 만들지 않는다.
12. **실무 도메인:** 사기·보안, 추천, 공급망, 바이오·신약·재료, 교통·통신, 제조, 소프트웨어/코드 그래프. 어디에 적합/부적합한지 구분한다.
13. **2025~2026 연구 변화와 12~24개월 전망:** 사실·추론·전망을 분리한다.

## 출처 및 분석 규칙

- 웹 검색을 실제로 수행한다.
- 원 논문, 동료평가 학회/저널, 공식 benchmark, 공식 프로젝트 문서/저장소를 우선한다.
- 최신 preprint는 preprint로 표시하고 동료평가 결과처럼 표현하지 않는다.
- 공급자 성능 수치는 공급자 주장으로 표시한다.
- 기술적 주장 옆에 클릭 가능한 URL을 둔다.
- 모델 정확도 수치를 서로 다른 dataset/split/hardware 사이에서 직접 비교하지 않는다.
- 'foundation', 'causal', 'reasoning', 'explainable', 'real-time' 같은 용어는 증거 기준을 제시한다.
- 대표 성공 사례뿐 아니라 negative result, failure mode, scaling/운영 비용을 포함한다.

## 결과물

1. `.agent-factory/inquery/graph-engineering/ai-non-rag-report.md`
   - 핵심 요약(10문장 이내)
   - 범위·제외 범위·방법·한계
   - AI 분야 지도와 기술 계층
   - 2025~2026 타임라인
   - 기술군별 원리·성숙도·장단점·생산 엔지니어링 요구
   - 모델/과제/프레임워크/benchmark 비교표
   - 도메인별 적용성과 부적합성
   - end-to-end 학습·서빙 참조 아키텍처
   - 평가·MLOps·보안·거버넌스
   - 과장 주장 판별표와 실패 모드
   - 조직 역할과 도입 체크리스트
   - 30/60/90일 검증 계획
   - 12~24개월 전망(사실/추론/전망 구분)
   - 결론과 최소 후속 Inquiry
2. `.agent-factory/inquery/graph-engineering/ai-non-rag-sources.md`
   - 범주별 제목, 저자/기관, 날짜, URL, 자료 유형, 사용 주장
3. 관리 런 결과에는 조사 경계, 핵심 결론, 결과 파일, 한계, 후속 조사만 간결히 적는다.

임시 Inquiry 자료로 유지하며 Specification/Project Skill로 승격하지 않는다. 구현·시험·제품 선택·외부 쓰기는 하지 않는다.
