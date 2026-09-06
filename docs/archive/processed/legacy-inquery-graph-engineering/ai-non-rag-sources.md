# AI 관점의 그래프 엔지니어링(비-RAG) — 출처 기록

- 조사 기준일: 2026-08-28 (Asia/Seoul)
- 범위: 그래프 학습·추론·생성·최적화·운영. RAG/GraphRAG/문서 검색 증강 생성/벡터 검색 답변 생성은 제외.
- 출처 원칙: 학회 원문·논문·공식 문서 우선. 2025–2026 프리프린트와 공급사 성능 주장은 별도 표시하고 독립 재현 전에는 사실로 일반화하지 않는다.

## 기초와 고차 구조

1. Bronstein et al., *Geometric Deep Learning*, 공식 책 사이트 — 대칭성·불변성·등변성으로 grid, set, graph, manifold 학습을 통합하는 기본 틀. https://geometricdeeplearning.com/
2. Bronstein et al., *Geometric Deep Learning: Grids, Groups, Graphs, Geodesics, and Gauges*, preface. https://geometricdeeplearning.com/book/preface.html
3. *DHG-Bench: A Comprehensive Benchmark for Deep Hypergraph Learning*, arXiv:2508.12244, 2025, 프리프린트 — 20개 데이터셋·16개 방법의 효과성/효율/강건성/공정성 평가. https://arxiv.org/abs/2508.12244
4. *Higher-Order Learning with Graph Neural Networks via Hypergraph Encodings*, NeurIPS 2025 — 고차 상호작용을 그래프 인코딩과 GNN으로 처리. https://papers.nips.cc/paper_files/paper/2025/hash/fe2223207c5801afa8c4325bd831e159-Abstract-Conference.html
5. *Hypergraph Learning on Heterophilic Data*, AAAI 2025 — 이질적 연결에서 하이퍼그래프 학습 평가. https://mlanthology.org/aaai/2025/li2025aaai-hypergraph/
6. *A Closer Look at Graph Transformers*, NeurIPS 2025 — 그래프 Transformer 설계·평가 분석. https://proceedings.neurips.cc/paper_files/paper/2025/file/c7e4746c7341a2c329e43ab55714db55-Paper-Conference.pdf

## 그래프 파운데이션 모델과 언어–그래프 결합

7. *GOFA: A Generative One-For-All Model for Joint Graph Language Modeling*, ICLR 2025 — 자기지도 사전학습, 과업 유연성, 그래프 인식이라는 GFM 요구를 제안. https://proceedings.iclr.cc/paper_files/paper/2025/hash/652c104b5b0652a03684efeaf805463b-Abstract-Conference.html
8. *Graph In-Context Learning with Task-Trees*, ICML 2025 — 5개 도메인, 30개 이상 그래프에서 전이·인컨텍스트·제로샷 평가. https://proceedings.mlr.press/v267/wang25eq.html
9. *GraphBFF: A Scalable Billion-Scale Graph Foundation Model*, arXiv:2602.04768, 2026, 프리프린트 — 14억 파라미터·대규모 샘플과 스케일링 주장. https://arxiv.org/abs/2602.04768
10. *G2PT: A General Graph Pretrained Transformer*, arXiv:2501.01073, 2025, 프리프린트. https://arxiv.org/abs/2501.01073
11. *LLM4Hypergraph*, ICLR 2025 — LLM의 하이퍼그래프 구조 이해 평가. https://proceedings.iclr.cc/paper_files/paper/2025/hash/690fc970014e4ecebc8068bbc03b35e6-Abstract-Conference.html
12. *CypherBench: Towards Precise Text-to-Cypher Generation*, ACL 2025 — 큰 스키마에서 자연어를 그래프 쿼리로 변환하는 벤치마크; 검색 증강이 아니라 구조화 쿼리 생성 관점으로만 사용. https://aclanthology.org/2025.acl-long.438/
13. *LLM4VKG: LLM-assisted Virtual Knowledge Graph Construction*, IJCAI 2025 — 스키마 매핑·가상 KG 구성. https://www.ijcai.org/proceedings/2025/525
14. *SciGraph-LLM: Evidence-Grounded Scientific Knowledge Graph Construction*, WSDM Companion 2026 — 과학 문헌에서 KG 구성; 답변 생성이 아닌 그래프 구축 관점. https://doi.org/10.1145/3779211.3793169

## 지식 그래프 추론

15. *Rule-Guided Graph Neural Networks for Explainable Knowledge Graph Reasoning*, AAAI 2025 — 규칙 신뢰도를 반영한 설명 가능한 KG 추론. https://ojs.aaai.org/index.php/AAAI/article/view/33394
16. *Neural-Symbolic Reasoning over Knowledge Graphs: A Survey*, IEEE TNNLS, 2025 — 논리 제약, 규칙 학습, 임베딩의 결합 분류. https://pubmed.ncbi.nlm.nih.gov/39024082/

## 그래프 생성 AI

17. *GraphXForm: Graph Transformer for Constrained Molecular Generation*, Digital Discovery, 2025 — 원자·결합의 반복 생성과 화학적 제약. https://doi.org/10.1039/D4DD00339J
18. *MatterGen: A Generative Model for Inorganic Materials Design*, Nature, 2025 — 원자 종류·좌표·격자에 대한 확산과 주기 대칭. https://doi.org/10.1038/s41586-025-08628-5
19. *Learning Joint Protein Graph and Text Representations*, Patterns, 2025 — 단백질 그래프–텍스트 표현 정렬. https://doi.org/10.1016/j.patter.2025.101227
20. *Protein Structure Generation with Global-Geometry-Aware Diffusion*, Nature Machine Intelligence, 2025. https://www.nature.com/articles/s42256-025-01059-x
21. *RAPiDock: Protein–Peptide Docking by Diffusion*, Nature Machine Intelligence, 2025. https://www.nature.com/articles/s42256-025-01077-9
22. *Generative Graph Pattern Machine*, NeurIPS 2025 — 그래프 패턴 생성 모델. https://proceedings.neurips.cc/paper_files/paper/2025/file/2b22bacd7ad8677f4837b28a11fe496f-Paper-Conference.pdf

## 인과, 월드 모델, 강화학습·조합최적화

23. *Graph World Models*, ICML 2025 — 그래프 상태와 행동 노드를 갖는 월드 모델, 6개 과업 평가. https://proceedings.mlr.press/v267/feng25p.html
24. *Characterization and Learning of Causal Graphs from Hard Interventions*, NeurIPS 2025 — 잠재변수 환경의 개입 동치와 식별. https://proceedings.nips.cc/paper_files/paper/2025/hash/6ff3e124a89678abb0dd5ffc322f0700-Abstract-Conference.html
25. *Neural Causal Graphs*, ICLR 2025 — 신경망 기반 인과 그래프 표현·학습. https://proceedings.iclr.cc/paper_files/paper/2025/hash/f25d75fc760aec0a6174f9f5d9da59b8-Abstract-Conference.html
26. *CausalGraphBench*, ACL Student Research Workshop 2025 — LLM 기반 인과 그래프 구축 평가. https://aclanthology.org/2025.acl-srw.16.pdf
27. *Graph Reinforcement Learning for Combinatorial Optimization: A Survey*, arXiv:2404.06492, 2024, 프리프린트. https://arxiv.org/abs/2404.06492
28. *Neural Combinatorial Optimization with Reinforcement Learning in Industrial Applications: A Survey*, Artificial Intelligence Review, 2025. https://doi.org/10.1007/s10462-024-11045-1
29. *A Graph Placement Methodology for Fast Chip Design*, Nature, 2021 — 그래프 RL의 대표적 산업 응용; 최신 운영 판단에는 별도 재현·휴리스틱 비교 필요. https://www.nature.com/articles/s41586-021-03544-w
30. *Deep Reinforcement Learning for Vehicle Routing Problems: A Review*, Transportation Research Part E, 2025. https://doi.org/10.1016/j.tre.2025.104278

## 동적 그래프와 벤치마크

31. Open Graph Benchmark 공식 사이트 — node/link/graph property prediction, 표준 split·evaluator. https://ogb.stanford.edu/
32. Hu et al., *Open Graph Benchmark*, arXiv:2005.00687. https://arxiv.org/abs/2005.00687
33. OGB Leaderboard Overview — 외부 데이터 사용 등 제출 조건 차이를 명시. https://ogb.stanford.edu/docs/leader_overview/
34. *TGB 2.0: A Benchmark for Learning on Temporal Knowledge Graphs and Heterogeneous Graphs*, NeurIPS Datasets and Benchmarks 2024. https://proceedings.neurips.cc/paper_files/paper/2024/file/fda026cf2423a01fcbcf1e1e43ee9a50-Paper-Datasets_and_Benchmarks_Track.pdf
35. *TGB-Seq: Challenging Temporal GNNs with Complex Sequential Dynamics*, ICLR 2025 — 반복 간선이 기존 시간 벤치마크를 쉽게 만드는 문제를 분석. https://proceedings.iclr.cc/paper_files/paper/2025/file/db5ca61dbc08cf5143c05ad2d1b0b2ca-Paper-Conference.pdf
36. *Temporal-Aware Evaluation for Dynamic Graph Learning*, AAAI 2025 — 변동성 군집 등 시간별 성능 편차 평가. https://ojs.aaai.org/index.php/AAAI/article/view/34273

## 프레임워크·대규모 시스템·그래프 저장소 연동

37. PyTorch Geometric Distributed Training 공식 문서 2.5.1 — 분산 샘플링·feature store·graph store 구성. https://pytorch-geometric.readthedocs.io/en/2.5.1/tutorial/distributed_pyg.html
38. DGL 2.5 GraphBolt 공식 문서 — item/negative/subgraph sampler와 feature fetch 파이프라인. https://www.dgl.ai/dgl_docs/stochastic_training/index.html
39. DGL Distributed Node Classification 공식 튜토리얼 — 파티션·분산 그래프/특징·PyTorch gradient. https://www.dgl.ai/dgl_docs/tutorials/dist/1_node_classification.html
40. NVIDIA cuGraph 26.10 공식 문서 — GPU 그래프 분석, cuGraph-PyG, WholeGraph. https://docs.nvidia.com/cugraph/26.10/
41. NVIDIA WholeGraph 공식 문서 — 분산 GPU/호스트/스토리지 메모리와 GNN 연동. https://docs.nvidia.com/cugraph/26.08/wholegraph/basics/wholegraph_intro/
42. AWS GraphStorm 공식 저장소 — 분산 그래프 ML 프레임워크, 릴리스 이력. https://github.com/awslabs/graphstorm
43. AWS, *Faster Distributed GNN Training with GraphStorm v0.4*, 2025-02-11 — GraphBolt 연동 및 속도 수치; 공급사 주장으로 취급. https://aws.amazon.com/blogs/machine-learning/faster-distributed-graph-neural-network-training-with-graphstorm-v0-4/
44. Google DeepMind Jraph 공식 저장소 — 2025-05-21 archived 상태. https://github.com/google-deepmind/jraph
45. Amazon Neptune ML 공식 문서 — 그래프 export, SageMaker/DGL 기반 학습·추론 흐름. https://docs.aws.amazon.com/neptune/latest/userguide/machine-learning.html
46. Neo4j Graph Data Science, Machine Learning 공식 문서 — pipeline 중심 node/link/graph ML. https://neo4j.com/docs/graph-data-science/current/machine-learning/

## 설명가능성·공정성·보안

47. *Explainability in Graph Neural Networks: A Taxonomic Survey*, ACM Computing Surveys, 2025. https://doi.org/10.1145/3711122
48. *Membership Inference Attacks against Graph Neural Networks*, IEEE TDSC, 2025. https://doi.org/10.1109/TDSC.2025.3586251
49. *Benchmarking Fairness in GNNs through Local Homophily*, SIAM SDM 2025. https://epubs.siam.org/doi/10.1137/1.9781611978520.65
50. *FairGSE*, arXiv:2511.12132, 2025, 프리프린트 — 평균 공정성 지표가 높은 subgroup FPR을 숨길 수 있다는 경고. https://arxiv.org/abs/2511.12132
51. *Privacy-Preserving Graph Machine Learning from Data to Computation: A Survey*, arXiv:2308.16375, 프리프린트. https://arxiv.org/abs/2308.16375

## 판독 한계

- 출판일은 온라인 공개일과 학회 개최연도가 다를 수 있다.
- 프리프린트(3, 9, 10, 27, 50, 51)는 동료심사 확정 결과가 아니며 버전이 바뀔 수 있다.
- 공급사 문서(40–46)는 기능 확인에는 적합하지만 성능 비교의 독립 근거가 아니다.
- 공개 벤치마크 순위는 데이터 누출, 외부 데이터, split, hardware, sampling budget가 다르면 직접 비교할 수 없다.
