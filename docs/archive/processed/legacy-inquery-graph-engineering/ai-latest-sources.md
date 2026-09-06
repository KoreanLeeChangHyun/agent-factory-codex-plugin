# 그래프 엔지니어링 최신 AI 조사 출처

> 확인일 2026-08-28. 자료 유형과 공급자/저자 주장을 구분한다.

## GraphRAG 원리·구현·평가

- **GraphRAG Methods / Query Overview** — Microsoft, 지속 갱신(2026 확인). https://microsoft.github.io/graphrag/index/methods/ ; https://microsoft.github.io/graphrag/query/overview/ — 공식 문서; Standard/Fast indexing, local/global/DRIFT/basic의 실제 범주와 용도.
- **microsoft/graphrag Releases & Changelog** — Microsoft, v3.1.0 2026-05, 이후 3.1.1 changelog. https://github.com/microsoft/graphrag/releases ; https://github.com/microsoft/graphrag/blob/main/CHANGELOG.md — 공식 repository; 3.x 상태, provider·streaming/vector 관련 engineering 변화.
- **GraphRAG-Bench: Challenging Domain-Specific Reasoning...** — Peng et al., 2025-06. https://arxiv.org/abs/2506.02404 ; https://github.com/jeremycp3/GraphRAG-Bench — 원 논문+공식 repo; construction/retrieval/generation을 포괄하려는 benchmark와 그 한계.
- **RAG vs. GraphRAG: A Systematic Evaluation and Key Insights** — 2025-02. https://arxiv.org/abs/2502.11371 — 원 논문(preprint); GraphRAG 우월성이 task·조건 의존임을 평가할 근거.
- **Retrieval-Augmented Generation with Graphs (GraphRAG)** — Han et al., 2025. https://arxiv.org/abs/2501.00309 — survey; query processor/retriever/organizer/generator/data source라는 넓은 정의. 대표 구현 주장에는 단독 사용하지 않음.
- **LightRAG: Simple and Fast Retrieval-Augmented Generation** — Guo et al., Findings of EMNLP 2025. https://aclanthology.org/2025.findings-emnlp.568/ ; https://github.com/HKUDS/LightRAG — 동료평가 논문+공식 MIT repo; graph indexing/retrieval 계열과 2026 release 상태.
- **HippoRAG 2 / From RAG to Memory** — Gutiérrez et al., 2025. https://arxiv.org/abs/2502.14802 ; https://github.com/OSU-NLP-Group/HippoRAG — 원 논문+공식 repo; associative graph retrieval와 non-parametric continual memory.
- **Query-Driven Multimodal GraphRAG** — Bu et al., Findings of ACL 2025. https://aclanthology.org/2025.findings-acl.1100/ — 동료평가 원 논문; query-local multimodal KG와 multi-path retrieval.
- **When Do Multimodal and Graph-Augmented RAG Help?** — 2026-07. https://arxiv.org/abs/2607.16604 — preprint; modality별 retrieval 병목과 controlled baseline 필요성.

## LLM ↔ KG·query generation

- **CypherBench: Towards Precise Retrieval over Full-scale Modern Knowledge Graphs** — Feng, Papicchio, Rahman, ACL 2025-07. https://aclanthology.org/2025.acl-long.438/ ; https://github.com/megagonlabs/cypherbench — 동료평가 논문+공식 repo; 11 graph/780만 entity/1만+ question, large-schema text-to-Cypher 평가.
- **Mind the Query: A Benchmark Dataset towards Text2Cypher** — IBM Research/EMNLP Industry 2025. https://research.ibm.com/publications/mind-the-query-a-benchmark-dataset-towards-text2cypher-task — 동료평가 논문; schema별 text-to-Cypher hallucination과 benchmark 확대.
- **LLM4VKG: Leveraging LLMs for Virtual KG Construction** — IJCAI 2025. https://www.ijcai.org/proceedings/2025/525 — 동료평가 원 논문; ontology/schema analysis/mapping 생성 보조의 특정 benchmark 결과.
- **Ontology-grounded Automatic KG Construction by LLM under Wikidata schema** — 2024-12. https://arxiv.org/abs/2412.20942 — preprint; authored ontology로 extraction을 제약하는 계보.
- **SciGraph-LLM: Automatic KG Construction from Scientific Papers** — Malashin et al., WSDM Companion 2026-05. https://doi.org/10.1145/3779211.3793169 — 학회 원 논문; claim/evidence/provenance를 보존하는 constrained pipeline.
- **Performance evaluation of LLMs for automated KG generation** — 2026. https://www.sciencedirect.com/science/article/pii/S2666827026000885 — 연구 논문; controlled Log-to-KG에서 prompting/model별 syntax·semantic extraction 평가. 다른 도메인에 점수 외삽하지 않음.
- **Graph-Assisted Large Language Models** — Luo et al., Findings of ACL 2026-07. https://aclanthology.org/2026.findings-acl.945/ — 동료평가 survey; knowledge augmentation, reasoning/planning, collaboration 분류.

## Graph Foundation Model·graph transformer

- **Graph Foundation Models: A Comprehensive Survey** — Wang et al., 2025-05. https://arxiv.org/abs/2505.15116 — survey/preprint; universal/task/domain scope와 structural alignment·heterogeneity·evaluation 문제.
- **Towards Graph Foundation Models: A Survey and Beyond** — Liu et al., 2023. https://arxiv.org/abs/2310.11829 — 계보 survey; GFM 정의 자체가 정착 중이라는 근거.
- **Graph Transformers: A Survey** — Shehzad et al., 2024. https://arxiv.org/abs/2407.09777 — survey; global attention, positional encoding, scalability/robustness 과제.
- **Billion-Scale Graph Foundation Models** — 2026-02. https://arxiv.org/abs/2602.04768 — preprint; GraphBFF billion-scale/scaling-law 주장. 미동료평가 최신 연구 신호로만 사용.
- **Large Language Models Meet Text-Attributed Graphs** — Su et al., 2025-10. https://arxiv.org/abs/2510.21131 — survey; LLM-for-TAG/TAG-for-LLM와 orchestration 분류.

## GNN·temporal/distributed graph ML

- **Temporal Graph Benchmark** — Huang et al., NeurIPS 2023; 현재 TGB 2.0 docs. https://tgb.complexdatalab.com/ ; https://arxiv.org/abs/2307.01026 — 원 논문+공식 benchmark; dynamic link/node, temporal KG/heterogeneous 평가.
- **TGB-Seq Benchmark** — Yi et al., ICLR 2025. https://proceedings.iclr.cc/paper_files/paper/2025/file/db5ca61dbc08cf5143c05ad2d1b0b2ca-Paper-Conference.pdf — 동료평가 원 논문; repeated-edge가 기존 평가를 쉽게 만드는 문제와 sequential dynamics.
- **Temporal-Aware Evaluation and Learning for TGNNs** — Su, Wu, AAAI 2025-04. https://ojs.aaai.org/index.php/AAAI/article/view/34273 — 동료평가 원 논문; temporal error volatility clustering.
- **SWIFT: Enabling Large-Scale Temporal Graph Learning on a Single Machine** — Xu et al., PACMMOD 2025-09. https://doi.org/10.1145/3749184 — 동료평가 systems 논문; secondary-memory pipeline의 특정 workload 성능.
- **Leveraging Temporal Graph Networks Using Module Decoupling** — Feldman, Baskin, LoG 2025. https://proceedings.mlr.press/v269/feldman25a.html — 동료평가 원 논문; lightweight temporal model과 throughput trade-off.
- **PyG Distributed Training** — PyTorch Geometric, v2.5+ docs. https://pytorch-geometric.readthedocs.io/en/2.5.1/tutorial/distributed_pyg.html — 공식 문서; partition/RPC sampling+feature retrieval/DDP 구조.
- **GraphStorm repository / v0.4 announcement** — AWS Labs, v0.5.1 2025-12; announcement 2025-02. https://github.com/awslabs/graphstorm ; https://aws.amazon.com/blogs/machine-learning/faster-distributed-graph-neural-network-training-with-graphstorm-v0-4/ — 공식 OSS+공급자 블로그; GraphBolt 통합과 distributed graph ML. 성능 수치는 공급자 주장.

## 생성형·과학·코드·multimodal graph

- **GraphXForm: graph transformer for computer-aided molecular design** — 2025-01. https://doi.org/10.1039/d4dd00339j — 동료평가 원 논문; atom/bond graph의 validity-preserving generation.
- **MatterGen: A generative model for inorganic materials design** — Zeni et al., Nature 2025. https://www.nature.com/articles/s41586-025-08628-5 — 동료평가 원 논문; diffusion material generation과 property fine-tuning.
- **MolE: a foundation model for molecular graphs** — Nature Communications, 2025. https://doi.org/10.1038/s41467-024-53751-y — 동료평가 원 논문; 약 8.42억 molecule pretraining 주장과 domain-specific foundation 근거.
- **Materials Graph Library (MatGL)** — Ong et al., npj Computational Materials 2025. https://www.nature.com/articles/s41524-025-01742-y — 동료평가+OSS 설명; invariant/equivariant GNN와 pretrained potential.
- **Code Graph Model** — NeurIPS 2025. https://proceedings.neurips.cc/paper_files/paper/2025/hash/178ae4ba29022eb7bf509c2e27bc8ab8-Abstract-Conference.html — 동료평가 원 논문; repository code graph를 LLM attention에 통합.
- **Foundation Molecular Grammar** — Sun et al., ICML 2025. https://proceedings.mlr.press/v267/sun25aa.html — 동료평가 원 논문; multimodal foundation model과 interpretable molecular graph grammar.

## Agent memory

- **Zep: A Temporal Knowledge Graph Architecture for Agent Memory** — Rasmussen et al., 2025-01. https://arxiv.org/abs/2501.13956 — 제품 저자 preprint; bitemporal KG/hybrid retrieval 및 DMR/LongMemEval 주장. 독립 결과로 취급하지 않음.
- **Graphiti repository** — Zep/Graphiti maintainers, 계속 갱신. https://github.com/getzep/graphiti — 공식 OSS 문서; incremental bitemporal KG, episode/entity/community, hybrid retrieval 기능.
- **AriGraph: Learning KG World Models with Episodic Memory for LLM Agents** — Anokhin et al., 2024. https://arxiv.org/abs/2407.04363 — 원 논문; semantic+episodic graph memory 계보.
- **A Machine with Short-Term, Episodic, and Semantic Memory Systems** — Kim et al., AAAI 2023. https://doi.org/10.1609/aaai.v37i1.25075 — 동료평가 원 논문; memory type을 KG로 분리하는 계보.
- **ARTEM: Spatial-Temporal Episodic Memory** — AAAI 2026. https://ojs.aaai.org/index.php/AAAI/article/view/39773 — 동료평가 원 논문; temporal-episodic agent memory의 최신 연구 사례.

## 공식 DB·cloud AI 기능

- **Neo4j GraphRAG for Python** — Neo4j, 2026 docs. https://neo4j.com/docs/neo4j-graphrag-python/current/ — 공급자 공식 문서; first-party package, KG builder/retriever, version·filtering 요구. 성능 비교 근거 아님.
- **Neo4j GenAI docs** — Neo4j, 2026. https://neo4j.com/docs/genai/ — 공급자 공식 문서; vector/embedding/GraphRAG/MCP 기능 범주.
- **Amazon Neptune ML** — AWS. https://docs.aws.amazon.com/neptune/latest/userguide/machine-learning.html — 공급자 공식 문서; SageMaker/DGL 기반 GNN, KGE, task와 inductive/transductive 구분.
- **Neptune Analytics guide** — AWS, 2025/2026. https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html — 공급자 공식 문서; vector similarity+graph analytics 범주.
- **Neptune Analytics–GraphStorm integration** — AWS, 2025-06. https://aws.amazon.com/about-aws/whats-new/2025/06/amazon-neptune-analytics-integrates-graphstorm/ — 공급자 공지; learned embedding/classification/link prediction의 Analytics 반입 기능.
- **Spanner Graph overview / vector search** — Google Cloud, 2026. https://docs.cloud.google.com/spanner/docs/graph/overview ; https://docs.cloud.google.com/spanner/docs/graph/perform-vector-similarity-search — 공급자 공식 문서; relational+GQL+full-text/vector, node/edge KNN와 node ANN, edition/제약.
- **GraphRAG infrastructure with Agent Platform and Spanner Graph** — Google Cloud Architecture Center, 2025. https://docs.cloud.google.com/architecture/gen-ai-graphrag-spanner — 공급자 reference architecture; Spanner Graph+AI platform 결합이지 독립 성능 증거가 아님.
- **Google Knowledge Graph Search API** — Google Developers. https://developers.google.com/knowledge-graph — 공급자 공식 문서; read-only, production-critical에 부적합 경고와 Enterprise KG migration 안내.

## 보안·거버넌스

- **OWASP Top 10 for LLM Applications 2025** — OWASP, 2025. https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf — 공식 보안 지침; RAG가 prompt injection을 완화하지 못함, indirect injection/data poisoning.
- **RAG Security Cheat Sheet** — OWASP, 지속 갱신. https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html — 공식 실무 지침; ingestion, poisoning, retrieval, access-control attack surface.
- **PoisonedRAG** — Zou et al., USENIX Security 2025. https://www.usenix.org/conference/usenixsecurity25/presentation/zou-poisonedrag — 동료평가 원 논문; RAG corpus knowledge-corruption 공격.
- **GraphRAG under Fire** — Liang et al., 2025-01. https://arxiv.org/abs/2501.14050 — preprint; relation injection/enhancement와 GraphRAG-specific poisoning.
- **A Few Words Can Distort Graphs** — Wen et al., 2025-08. https://arxiv.org/abs/2508.04276 — preprint; 소량 source 변경이 construction graph와 downstream QA를 오염시키는 실험.
- **LogicPoison** — 2026-04. https://arxiv.org/abs/2604.02954 — preprint; surface semantics보다 graph logical/topological integrity를 노리는 공격 주장.
- **A Survey on Privacy in GNNs** — Zhang et al., IEEE TKDE 2024. https://arxiv.org/abs/2308.16375 — 동료평가 survey; membership/inversion/reconstruction과 방어 범주.

## 출처 충돌·해석 제한

- Microsoft GraphRAG, LightRAG, HippoRAG, Graphiti는 “GraphRAG/memory”라는 유사 명칭을 쓰지만 index, query, 목표와 평가가 다르다.
- GraphRAG-Bench의 이름과 세부 task를 표방하는 후속/동명 자료가 있어 논문 ID·repo·corpus version을 함께 고정해야 한다.
- Zep, AWS, Neo4j, Google의 성능/정확성 문구는 공급자 또는 저자 주장이다. 본문에서는 기능 근거 또는 가설로만 사용했다.
- arXiv 2025~2026 보안/GFM 논문은 최신 신호이나 동료평가 상태가 제한적이다. 공격면·실험 가설로 인용하고 보편 수치로 일반화하지 않았다.
- molecular/material 결과는 강한 domain semantics·validator에 의존하므로 일반 enterprise KG로 직접 전이하지 않았다.
