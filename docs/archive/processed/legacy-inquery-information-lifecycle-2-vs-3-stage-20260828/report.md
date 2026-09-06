# 정보 수명주기: 2단계와 3단계 비교

- 조사일: 2026-08-28
- 조사 범위: 공개 웹의 표준·정부·연구기관 자료와 공식 제품 문서, 그리고 요청에 지정된 현재 저장소 계약
- 문서 성격: 임시 Inquiry 결과(비정제 정보). 이 보고서는 Agent Factory의 정제된 Specification이나 Project Skill이 아니며, 최종 아키텍처 결정도 아니다.

## 간결한 결론

Agent Factory에는 기본적으로 **`원본 -> 가공 -> 정제`의 3단계 의미 모델**이 더 적합하다. 핵심 이유는 파일 수가 세 종류라서가 아니라, 세 단계가 서로 다른 주장을 하기 때문이다.

- **원본**은 “출처가 실제로 무엇을 말했는가”에 관한 증거 권위를 가진다.
- **가공**은 “Agent나 사람이 그 증거를 어떻게 분석·요약·비교했는가”를 나타내지만, 아직 프로젝트의 승인된 진실은 아니다.
- **정제**는 출처, 충돌, 불확실성, Human 결정을 조정하여 프로젝트가 신뢰하도록 승인된 지식이다.

W3C PROV는 단순한 `derived-from` 연결과 활동·사용·생성을 명시한 상세 파생 기록을 모두 허용한다. 즉, 간단한 경우에는 두 엔터티만 보이게 축약할 수 있지만 변환의 존재나 책임까지 없애야 한다는 뜻은 아니다. 반대로 NARA의 기록 수명주기, OAIS, DCC의 디지털 큐레이션 모델, 연구 데이터 수명주기, Medallion 패턴은 유지·사용·변환·선별·보존 같은 중간 활동을 구분하는 것이 감사, 재처리, 장기 이해에 유리함을 보여 준다.

따라서 **가공은 별도의 논리적 상태이자 별도의 권위 경계여야 하며, 필요할 때 격리된 운영 작업공간으로도 구현되어야 한다.** 다만 모든 중간 파일을 영구 보존해야 하는 것은 아니다. 2단계는 결정적·저위험 변환이고, 원본과 승인된 결과를 연결할 수 있으며, 중간 산출물을 재생성할 수 있고, 충돌·해석·AI 추론이 프로젝트 진실로 오인될 가능성이 낮을 때의 **명시적 축약 경로**로 두는 것이 안전하다.

## 용어 정규화

이 조사에서 서로 다른 분야의 용어를 다음과 같이 맞추었다. 완전히 같은 개념이라는 뜻이 아니라 비교를 위한 기능적 대응이다.

| Agent Factory 용어 | 기능적 정의 | 외부 모델의 가까운 표현 | 권위 해석 |
| --- | --- | --- | --- |
| 원본(original) | 출처 충실도, 출처 식별자, 수집 맥락을 보존한 증거 | raw/bronze, create or receive, SIP, primary source | “무엇이 입력되었는가”에 대한 증거 권위. 곧바로 프로젝트 진실을 뜻하지 않음 |
| 가공(processed) | 분석, 요약, 비교, 정규화, 가설, 인터뷰 해석, 변환 결과 | working/intermediate, silver, maintenance and use, analysis, transformation/ingest activity | 파생 과정의 산출물. 유용하고 근거가 있어도 승인된 프로젝트 진실은 아님 |
| 정제(refined) | 충돌을 조정하고 Human 결정을 반영한 신뢰 가능한 프로젝트 지식 | curated/gold, archival/published/authoritative representation | Specification이 관리하는 승인·조정된 지식 |
| 승격(promotion) | 한 상태의 산출물을 다음 권위 상태로 받아들이는 명시적 행위 | publish, appraisal/selection, ingest/validation, approval gate | 변환과 다름. 내용이 바뀌지 않아도 권위가 바뀔 수 있음 |
| 보존(retention) | 특정 기간 동안 객체·메타데이터·로그를 유지하는 정책 | maintenance, storage, archival retention | 상태 모델과 별개. 가공 상태가 있다고 모든 중간 파일을 보존할 필요는 없음 |

중요한 구분은 **품질, 권위, 저장 위치가 같은 축이 아니라는 점**이다. 잘 검증된 가공 결과도 Human 승인 전에는 비정제일 수 있고, 원본은 오류를 포함해도 출처 증거로서 충실할 수 있다. 또한 가공 상태는 메타데이터로만 남고 파일은 삭제될 수 있으며, 반대로 재현성 때문에 일부 가공 산출물을 오래 보존할 수도 있다.

## 공개 모델과 사례

### 1. 두 단계 또는 직접 승격에 가까운 모델

#### W3C PROV의 축약 파생 표현 — 표준 근거

[W3C PROV-O](https://www.w3.org/TR/prov-o/)는 한 엔터티가 다른 엔터티에서 파생되었다는 `prov:wasDerivedFrom`만으로 가장 단순한 파생을 표현할 수 있고, 필요한 경우 그 파생을 수행한 Activity, Usage, Generation, Agent를 상세히 붙일 수 있게 한다. [PROV 개요](https://www.w3.org/TR/prov-overview/)는 객체 식별, 처리 단계, 재현성, 버전, 파생을 핵심 요구로 든다.

이것은 `원본 -> 정제`라는 **축약된 외부 표현**이 성립할 수 있음을 뒷받침한다. 다만 표준이 중간 처리의 존재를 부정하는 것은 아니다. 처리 활동이 알려지지 않았거나 관심 대상이 아닐 때 단순 관계로 접을 수 있게 한 것이다. 따라서 Agent Factory의 2단계 안전 경로에도 최소한 `정제 산출물 -> 원본`, 승격 주체, 버전/시각, 적용된 절차 정도는 남기는 편이 PROV의 취지에 맞다.

#### GOV.UK의 draft-to-live — 정부 공식 운영 사례

[GOV.UK Publishing API](https://docs.publishing.service.gov.uk/repos/publishing-api/publishing-application-examples.html)는 draft를 갱신한 뒤 별도 publish 요청으로 live로 전환하는 흐름을 규정한다. [API 모델](https://docs.publishing.service.gov.uk/repos/publishing-api/model.html)은 draft, published, unpublished, superseded 등의 상태를 둔다. 외부 소비 관점에서는 `초안 -> 게시`라는 두 권위 상태가 선명하고, publish가 명시적 승격 게이트다.

이 모델은 하나의 편집 단위가 짧은 검토를 거쳐 게시되고, 소스·초안 버전·게시 요청이 시스템에 기록되는 콘텐츠 배포에 잘 맞는다. 그러나 초안 안에서 일어난 조사와 해석을 별도 권위 상태로 관리하는 지식 수명주기 모델은 아니다. 연구가 많은 프로젝트에 그대로 일반화하기에는 부족하다.

#### GitHub Pages의 source-to-published — 벤더 운영 패턴

[GitHub Pages 공식 문서](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)는 특정 branch/folder를 publishing source로 삼아 push 시 게시하거나, Actions에서 checkout, 선택적 build, artifact upload, deploy를 수행하게 한다. 제어가 필요 없는 경우에는 source branch에서 직접 게시하는 단순 경로를 권한다.

이 사례는 소스와 게시 결과만 장기적인 관심 대상이고 빌드가 결정적·재실행 가능할 때 중간 산출물을 별도 지식 상태로 보존하지 않아도 되는 경우를 보여 준다. 동시에 실제 배포에는 build artifact와 workflow run이라는 운영 중간물이 있을 수 있다. 즉 **두 개의 장기 권위 상태와 세 단계 이상의 운영 과정은 양립한다.**

### 2. 세 단계 이상을 명시하는 모델

#### NARA 기록 수명주기 — 정부 기록관리 근거

[미국 국립문서기록관리청(NARA)](https://www.archives.gov/records-mgmt/faqs/general.html)은 기록 수명주기를 `creation or receipt -> maintenance and use -> disposition`의 세 단계로 설명한다. 유지·사용 단계에는 파일 계획, 색인, 통제어휘, 분류체계, 데이터 사전, 접근·보안 절차가 포함되며, disposition은 영구 이관 또는 승인된 폐기를 포함한다. 이 모델의 세 번째 단계는 Agent Factory의 “정제”와 동일하지는 않지만, 생성과 최종 처분 사이의 관리·사용 상태를 없애면 안 된다는 권위 있는 유사 근거다.

#### OAIS — 보존 표준/권고 관점

[CCSDS의 최신 OAIS Reference Model(650.0-M-3, 2024)](https://ccsds.org/publications/allpubs/entry/3054/)은 생산자에게서 받은 Submission Information Package(SIP), 보존을 위해 관리되는 Archival Information Package(AIP), 소비자에게 제공되는 Dissemination Information Package(DIP)를 구분한다. Ingest는 SIP를 검증·변환하여 AIP를 만드는 기능이다. OAIS는 Agent Factory의 3단계와 일대일로 같지는 않지만, 제출본, 보존 권위본, 배포본 및 그 사이의 ingest 변환을 구분하는 대표적인 표준 근거다.

특히 원본과 보존본이 형식상 달라질 수 있으므로, 무결성·맥락·provenance를 함께 보존해야 한다는 점이 중요하다. [Library of Congress의 보존 형식 설명](https://www.loc.gov/preservation/digital/formats/sustain/sustain.shtml)도 OAIS의 representation, reference, context, fixity, provenance 메타데이터와 변환 이력의 조기 기록을 강조한다.

#### DCC 디지털 큐레이션 수명주기 — 인정된 연구기관 모델

[Digital Curation Centre의 모델](https://www.dcc.ac.uk/about/digital-curation)은 conceptualise, create/receive, appraise/select, ingest, preservation action, store, access/use/reuse, transform, dispose, reappraise 등을 분리한다. Transform은 원본에서 새로운 디지털 객체를 만들고, appraise/select와 preservation action은 무엇을 권위 있게 장기 보존할지 결정한다. [DCC 설명](https://www.dcc.ac.uk/guidance/curation-lifecycle-model)은 이 모델이 역할·책임과 연구 데이터 관리 workflow를 정의하도록 돕는다고 명시한다.

이는 복잡한 조사에서 “받은 것”, “분석·변환한 것”, “선별·보존하기로 한 것”이 서로 다른 책임과 정책을 가져야 함을 뒷받침한다. 또한 모든 객체를 보존하는 것이 아니라 appraise/select와 dispose를 명시하므로, 3단계 모델이 무제한 보존을 뜻하지 않는다는 근거이기도 하다.

#### 연구 데이터 수명주기 — 재현성 근거

[UK Data Service](https://ukdataservice.ac.uk/learning-hub/data-producer-support/foundations-of-research-data-management/)는 연구 데이터가 조직·문서화·큐레이션되지 않으면 다른 사람이 해석하거나 재사용하기 어렵고 재현성과 투명성이 낮아진다고 설명한다. 기존 자료의 수명주기 예시는 creating, processing, analysing, preserving, giving access, re-using을 구분한다. 원자료, 처리, 분석, 보존/공개의 분리는 방법과 입력을 다시 사용해 결과를 재현하는 데 유리하다.

#### Medallion — 벤더 패턴, 표준 아님

[Databricks Medallion 공식 문서](https://docs.databricks.com/aws/en/lakehouse/medallion)는 Bronze(raw ingestion), Silver(cleaning/validation), Gold(modeling/aggregation/business use)의 세 계층으로 품질을 점진적으로 높이는 패턴을 설명한다. Bronze를 보존하면 하위 계층을 재구축할 수 있다는 [공식 아키텍처 지침](https://docs.databricks.com/aws/en/lakehouse-architecture/deployment-guide/delta-lake)도 있다.

이것은 Agent Factory의 3단계를 이해하기 좋은 운영 유사 모델이지만 **벤더 권장 데이터 아키텍처이며 정보 권위에 관한 표준은 아니다.** Silver를 “refined”라고 부르는 제품 용어도 Agent Factory의 최종 refined와 충돌하므로 용어가 아닌 역할만 대응해야 한다.

## 근거 기반 비교

| 비교 기준 | 2단계 `원본 -> 정제` | 3단계 `원본 -> 가공 -> 정제` | 근거와 판단 |
| --- | --- | --- | --- |
| provenance·감사 | 직접 연결이 단순하다. 변환이 사소하면 충분하다. 복수 분석·요약이 최종본에 섞이면 어떤 해석이 어디서 생겼는지 잃기 쉽다. | 원본, 파생 Activity/Agent, 승인 결과를 분리해 파생 사슬을 설명하기 쉽다. | W3C PROV는 단순 derivation과 qualified activity를 모두 지원한다. LoC/OAIS는 provenance와 변환 메타데이터를 강조한다. |
| Human 발언과 AI 해석 보존 | 하나의 문서로 합치면 직접 발언·결정과 AI 요약·추론이 섞일 위험이 크다. | 원문/직접 진술을 원본으로, Agent 해석을 가공으로, 확인·승인된 결론을 정제로 분리할 수 있다. | NIST는 GAI confabulation, automation bias, over-reliance, 정보 무결성 위험을 식별한다. 로컬 Interview 계약도 직접 진술과 Agent 해석을 분리한다. |
| 재현성·재처리 | 결정적 빌드이고 소스·절차·버전이 남으면 강점이 있다. 비결정적 AI 분석이나 여러 출처 결합에서는 결과 재현이 어렵다. | 입력 snapshot, 프롬프트/방법/도구 버전, 가공 결과를 선택적으로 남겨 재검토·재처리가 쉽다. | PROV의 Activity/Usage/Generation, 연구 데이터 수명주기, Bronze에서 downstream 재구축 패턴이 지지한다. |
| 모순·불확실성 | 최종 문서에 바로 조정해야 하므로 해결되지 않은 충돌을 누락하거나 성급히 단일화하기 쉽다. | 가공 공간에서 경쟁 가설·충돌·한계를 유지하고, 정제 단계에서 해결 또는 미해결로 명시할 수 있다. | DCC의 appraise/reappraise 및 로컬 Inquery/Specification 계약과 부합한다. |
| 저장·운영 복잡도 | 경로, ACL, 상태 전이가 적고 작은 프로젝트에 유리하다. | 분류·승격·청소 정책, lineage 메타데이터, 권한 분리가 필요해 비용이 증가한다. | GOV.UK/GitHub의 단순 게시 흐름과 UK Data Service의 수명주기 비용 설명이 양쪽 trade-off를 보여 준다. |
| 개인정보·보존·삭제 | 복제본이 적어 삭제 범위가 단순할 수 있다. 단, 원본에서 정제로 개인정보가 바로 복사되면 최소화·익명화 기회를 잃는다. | 격리·비식별화 지점을 만들 수 있지만 복제와 잔존 데이터가 늘어 삭제 전파가 어려워질 수 있다. 단계별 TTL과 lineage가 필수다. | GDPR Article 5는 목적 제한, 데이터 최소화, 정확성, 저장 제한을 요구하고 Article 17은 조건부 삭제권을 둔다. DCC는 select/dispose를 명시한다. |
| 승격·승인 의미 | publish/approve 한 번으로 명료하다. 작성과 승인을 같은 행위·주체가 하면 의미가 약해진다. | 분석 완료와 프로젝트 지식 승인을 별도 사건·책임으로 표현할 수 있다. | GOV.UK publish endpoint는 draft-to-live 전이를 분리한다. 로컬 Specification은 Human 결정과 조정을 요구한다. |
| 작은·단순 프로젝트 | 기계적 형식 변환, 한 출처, 짧은 문서, 낮은 위험이면 효율적이다. | overhead가 이득을 넘을 수 있다. 가공 상태만 논리적으로 표시하고 파일을 영구화하지 않는 경량 운용이 가능하다. | GitHub Pages의 branch-to-publish와 PROV의 단순 derivation이 축약 가능성을 지지한다. |
| 조사 중심 프로젝트 | 근거가 많고 충돌·불확실성이 있으면 부적합해지기 쉽다. | 분석·가설·인터뷰 해석을 정제 진실과 분리하므로 적합하다. | DCC, UK Data Service, NARA, OAIS 모두 생성/수신과 사용·변환·선별·보존을 분리한다. |
| AI 가공물을 진실로 오인할 위험 | “원본이 아니면 정제”라는 이분법이 AI 요약을 자동으로 권위화할 수 있다. | processed 라벨이 비승인 상태를 명시한다. 다만 이름만 두고 승인 gate가 없으면 위험은 남는다. | [NIST AI 600-1](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)은 확신에 찬 오류, over-reliance, 사실·의견·불확실성 미구분 위험을 명시한다. |

## Agent Factory에 적용한 매핑

| Capability / artifact | 주 입력 | 기본 출력 상태 | 권위·보존 해석 |
| --- | --- | --- | --- |
| Gather | Google Drive, Gmail, Slack, Notion, Discord, OneDrive 등의 외부 자료 | 원본 | source fidelity, identity, provenance를 보존한다. 수집한 주장을 조정하거나 정제 진실로 승격하지 않는다. 실제 수집물은 `.agent-factory/` 밖의 resolved destination에 둔다. |
| Explorer(수용된 핵심 개념) | 웹, 코드, 문서, 원본/가공 자료 | 원본 또는 가공 | 탐색·연구·분석을 수행하되 정제 진실을 독립 승인하지 않는다. 현재 구현 완료를 뜻하지 않으며, `inquery`와의 관계는 미결이다. |
| Interview | Human 발언과 질문 | 가공 | 직접 Human 진술·결정과 Agent의 paraphrase·해석을 구분한다. 대화 안에 기본 유지하고, 명시적 요청 없이 별도 저장·승격하지 않는다. |
| Inquery workspace | 불확실한 질문과 관련 증거 | 가공 중심의 임시 Markdown, 필요시 임시 원본 사본·실험물 | `.agent-factory/inquery/<id>/`는 비정제 AI 작업공간이다. 임시라고 자동 삭제하지도, 존재한다고 승인 진실로 보지도 않는다. |
| Specification | 원본, 가공, 명시적 Human 결정 | 정제 | 충돌과 불확실성을 조정해 하나의 의미 본체를 관리한다. Human-facing 한국어 browser 문서와 AI-facing English Project Skill은 충실한 두 투영이다. |
| paired Human/AI representations | 동일한 정제 의미 본체 | 정제 | 두 개의 독립 권위본이 아니라 같은 정제 지식의 두 표현이다. 의미가 어긋나면 안 된다. |

현재 로컬 계약은 이미 이 매핑을 명시한다. 특히 `.codex/skills/agent-factory-core/references/core-model.md`는 `original -> processed -> refined`를 수용된 의미 모델로 기록하고, `skills/gather/SKILL.md`, `skills/inquery/SKILL.md`, `skills/interview/SKILL.md`, `skills/specification/SKILL.md`는 각 capability의 승격 한계를 분리한다. 이 조사 결과는 그 결정을 새로 내리는 것이 아니라, 공개 근거가 그 경계를 지지하는지 비교한 것이다.

## “가공”은 상태인가, 작업공간인가

권고 답은 **둘 다일 수 있으나 두 의미를 분리해야 한다**이다.

1. **논리적·권위 상태로서는 필수**다. AI 분석, 인터뷰 synthesis, 정규화 결과가 원본도 아니고 승인된 정제 진실도 아니라는 사실을 표현해야 한다. 파일을 남기지 않아도 run metadata나 provenance에는 “처리됨, 미승인” 상태와 사용한 원본·절차·책임 주체가 남을 수 있다.
2. **운영 작업공간으로서는 조건부**다. 여러 출처, 장기 조사, 모순, 실험, 후속 turn, 독립 검토가 있으면 격리된 Inquery workspace가 유용하다. 단순한 결정적 변환은 메모리나 일회성 build artifact로 처리하고 삭제할 수 있다.
3. **장기 보존 계층으로서는 기본값이 아니다.** 재현성, 감사, 법적 보존, 비용, 민감도에 따라 산출물별로 결정해야 한다. DCC가 appraise/select/dispose를 분리하고 GDPR이 최소화·저장 제한을 요구하는 점은 “세 단계 = 세 벌 영구 보관” 해석을 반박한다.

권위 상태와 물리 저장을 분리하면 다음 네 경우가 모두 가능하다.

- 논리적 processed + 단기 파일 보존: 일반 Inquiry 메모와 임시 분석.
- 논리적 processed + 장기 선택 보존: 재현이 어렵거나 감사에 필요한 실험 결과.
- 논리적 processed + 파일 미보존: 결정적 build의 중간 artifact. lineage와 절차만 기록.
- processed artifact 없이 직접 승격: Human이 출처를 직접 검토·수용하고 변환이 없는 경우. 그래도 승인 사건과 원본 연결은 기록.

## 기본 모델과 안전한 2단계 축약 기준

### 권고 기본값

기본 의미 모델은 `원본 -> 가공 -> 정제`로 유지한다. 세 상태는 각각 evidence fidelity, unaccepted derivation, accepted project knowledge라는 다른 권위 계약을 가진다. 경로도 Gather destination, `.agent-factory/inquery/`, Specification/Project Skill로 분리하고, 승격은 자동 파일 이동이 아니라 출처 검토·충돌 조정·Human 결정 반영을 포함한 명시적 사건으로 취급한다.

### 2단계 축약이 안전한 조건

다음 조건을 **모두** 만족할 때 `원본 -> 정제`의 축약 경로가 합리적이다.

1. 입력 원본과 identity/version/snapshot이 고정되고 나중에 검사 가능하다.
2. 변환이 없거나, deterministic·반복 가능하고 의미 판단을 거의 포함하지 않는다(예: 포맷 변환, 정적 build, 검증된 필드 매핑).
3. 복수 출처의 모순, 불확실한 가설, 누락된 맥락, Human 발언에 대한 Agent 해석이 없다.
4. 생성형 AI의 자유로운 요약·추론이 없거나, 있다면 그 결과를 processed로 명시하고 Human 검토 전 정제로 보지 않는다.
5. 원본에서 정제 결과로의 provenance, 사용한 절차/도구 버전, 수행 주체를 기록한다.
6. publish/accept 사건과 승인 주체가 명시되고, 작성/변환 완료를 승인과 혼동하지 않는다.
7. 중간물을 폐기해도 결과를 원본에서 재생성할 수 있거나, 재생성 불가능성의 위험을 Human이 별도로 결정한다.
8. 개인정보·기밀의 복사, 비식별화, TTL, 삭제 전파가 정의되어 있고 중간 복제 제거가 법적·조직 정책과 맞는다.
9. 결과가 작고 영향이 낮으며, 오류 시 원본으로 되돌아가 재승격할 수 있다.

한 조건이라도 충족하지 못하면 3단계 경로로 올리는 것이 안전하다. 특히 AI가 해석한 Human 발언, 여러 자료의 synthesis, 경쟁 가설, 조사 결과는 내용이 매끄럽더라도 processed다.

## 보존·provenance·삭제 함의

### 최소 provenance 묶음

상태 수와 관계없이 정제 항목마다 다음을 추적할 수 있어야 한다.

- source identity, 위치/URI, 수집 또는 확인 시각, 가능한 경우 content hash/version;
- 파생된 원본 목록과 각 원본의 직접 인용/요약 구분;
- 처리 Activity의 종류, 도구·모델·프롬프트/방법의 필요한 버전, 수행 Agent/Human;
- processed 상태와 refined 상태의 생성 시각 및 별도 식별자;
- Human의 명시적 결정 또는 승인 사건과 범위;
- 해결된 충돌, 남은 모순·불확실성, 제외한 근거와 이유;
- retention class, 접근권한, 개인정보/기밀 표시, 삭제 예정과 삭제 전파 상태.

W3C PROV의 Entity/Activity/Agent와 derivation은 이 묶음의 일반 골격을 제공한다. OAIS/LoC의 context, fixity, provenance는 장기 이해와 무결성에 필요한 보존 메타데이터를 보강한다.

### 보존 정책

- **원본:** 무조건 영구 보존이 아니라 source fidelity와 재수집 가능성, 라이선스, 법적 의무, 민감도에 따라 기간을 둔다. 외부 원본을 복사할 수 없다면 identifier, 접근일, hash 또는 충분한 인용 provenance를 남긴다.
- **가공:** 기본은 topic/run 단위 TTL 또는 Inquiry 종료 후 재평가다. 재현 불가능한 실험, 고비용 분석, 중요한 모순 기록, 승인 근거가 된 snapshot만 선별 보존한다.
- **정제:** 현재 신뢰본과 변경 이력을 보존하되, 원본 개인정보를 불필요하게 복제하지 않는다. 정제 문서에 필요한 최소 정보와 근거 포인터만 포함하는 방식을 우선한다.
- **삭제:** 원본 하나가 삭제 대상이 되면 파생 lineage를 따라 processed/refined 사본과 인덱스·cache·backup 범위를 식별해야 한다. 정제 결론을 반드시 지워야 하는지는 법적 근거와 익명화 가능성에 따라 별도 판단한다.

[GDPR 원문](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679)은 Article 5에서 목적 제한, 데이터 최소화, 정확성, 저장 제한을 정하고 Article 17에서 조건과 예외가 있는 삭제권을 둔다. 따라서 3단계의 감사 이점만을 이유로 개인정보가 포함된 모든 중간 산출물을 무기한 보존해서는 안 된다. 반대로 삭제 가능성을 확보하려면 lineage와 소유권이 필요하므로, 단순히 파일을 한곳에 합치는 2단계가 항상 더 나은 개인정보 설계도 아니다.

## 모순, 한계, 해석 주의

1. **외부 모델은 같은 문제를 풀지 않는다.** NARA는 기록의 보관·처분, OAIS와 DCC는 장기 디지털 보존, Medallion은 분석 데이터 품질, GOV.UK/GitHub는 게시·배포를 다룬다. Agent Factory의 지식 권위 모델에 대한 적용은 기능적 유추이며 표준의 직접 요구사항이 아니다.
2. **“refined” 용어가 충돌한다.** Databricks 계열 문서는 Silver에도 refined/curated라는 말을 쓰지만 Agent Factory에서 refined는 최종 승인 지식이다. 이름을 기계적으로 대응하면 안 된다.
3. **2단계 모델의 표준 근거는 제한적이다.** W3C PROV가 단순 binary derivation을 허용하고 공식 publishing 시스템이 draft/live 또는 source/published 흐름을 제공하지만, 이를 “모든 정보는 두 권위 단계면 충분하다”는 보편 표준으로 선언한 권위 자료는 찾지 못했다.
4. **세 단계가 정확히 최적이라는 직접 실증은 없다.** 공개 자료는 대체로 세 단계보다 더 세분된다. 이 보고서의 3단계 권고는 Agent Factory가 필요한 세 권위 경계를 최소한으로 정규화한 설계 판단이다.
5. **보존과 권위는 직교한다.** NARA의 disposition이나 OAIS의 AIP를 Agent Factory refined와 동일시할 수 없다. 보존된 원본이 정제 진실은 아니고, 승인된 정제 지식이 원본보다 장기 보존 가치가 항상 높은 것도 아니다.
6. **AI 위험 근거는 일반적이다.** NIST는 confabulation과 over-reliance를 확인하지만 “processed라는 세 번째 상태를 두라”고 규정하지 않는다. processed 경계가 그 위험을 줄인다는 부분은 근거에 기반한 아키텍처 추론이다.
7. 이번 조사는 공개 문서 검토만 수행했다. 두 모델을 실제 Agent Factory 프로젝트에 적용한 비용·오류율·승격 지연 실험은 수행하지 않았다.

## Human에게 남는 결정

최종 아키텍처 결정은 Human 소유다. 구체적으로 다음을 결정해야 한다.

- 3단계 의미 모델을 기본값으로 유지하면서 2단계 축약을 공식 지원할지;
- processed 상태의 최소 provenance 필드와 승격 gate를 무엇으로 할지;
- Inquiry/Interview/Explorer 산출물별 기본 TTL, 선별 보존 기준, 개인정보 삭제 전파 규칙;
- 축약 기준의 위험 등급과 누가 예외를 승인할지;
- unresolved인 future Explorer와 현재 `inquery`의 관계, Interview의 wider integration.

이 보고서는 그 선택을 대신하지 않는다.

## 가장 작은 후속 Inquiry

필요한 후속 조사는 하나다. **실제 프로젝트 2~3개(단순 문서 갱신, 다중 출처 조사, 민감한 Human 인터뷰)를 표본으로 삼아**, 동일 작업을 (a) processed artifact 미보존 축약 경로와 (b) 선택 보존 3단계 경로로 재연하고 다음만 측정한다.

- 출처까지 역추적 가능한 정제 주장 비율;
- 변경된 원본으로 재처리하는 시간;
- Human 발언과 AI 해석의 혼동 건수;
- 저장량·민감정보 복제 수·삭제 대상 탐색 시간;
- 승격에 필요한 Human 검토 시간.

이 비교가 있어야 의미 모델은 유지하되 processed 물리 보존의 기본 TTL과 축약 임계값을 경험적으로 정할 수 있다.

## 출처 목록

모든 웹 출처의 최종 접근일은 **2026-08-28**이다.

### 표준·정부·공공기관

- W3C, [PROV-Overview](https://www.w3.org/TR/prov-overview/) 및 [PROV-O](https://www.w3.org/TR/prov-o/).
- CCSDS, [Reference Model for an Open Archival Information System (OAIS), CCSDS 650.0-M-3](https://ccsds.org/publications/allpubs/entry/3054/), 2024-12.
- U.S. National Archives and Records Administration, [Frequently Asked Questions about Records Management in General](https://www.archives.gov/records-mgmt/faqs/general.html).
- European Union, [Regulation (EU) 2016/679 (GDPR)](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679), Articles 5 and 17.
- National Institute of Standards and Technology, [Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile, NIST AI 600-1](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence), 2024.
- Library of Congress, [Sustainability Factors](https://www.loc.gov/preservation/digital/formats/sustain/sustain.shtml).

### 연구기관 자료

- Digital Curation Centre, [Curation Lifecycle Model](https://www.dcc.ac.uk/guidance/curation-lifecycle-model) 및 [What is digital curation?](https://www.dcc.ac.uk/about/digital-curation).
- UK Data Service, [Foundations of research data management](https://ukdataservice.ac.uk/learning-hub/data-producer-support/foundations-of-research-data-management/).

### 공식 플랫폼 문서(사례·벤더 패턴)

- GOV.UK Developer Documentation, [Publishing application examples](https://docs.publishing.service.gov.uk/repos/publishing-api/publishing-application-examples.html) 및 [Publishing API model](https://docs.publishing.service.gov.uk/repos/publishing-api/model.html).
- GitHub Docs, [Configuring a publishing source for your GitHub Pages site](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
- Databricks Docs, [What is the medallion lakehouse architecture?](https://docs.databricks.com/aws/en/lakehouse/medallion) 및 [Design Delta Lake architecture](https://docs.databricks.com/aws/en/lakehouse-architecture/deployment-guide/delta-lake).

### 로컬 비교 근거

- `AGENTS.md`
- `skills/gather/SKILL.md`
- `skills/gather/references/gather-management.md`
- `skills/inquery/SKILL.md`
- `skills/inquery/references/workspace.md`
- `skills/interview/SKILL.md`
- `skills/interview/references/conduct.md`
- `skills/specification/SKILL.md`
- `skills/specification/references/specification-document.md`
- `skills/specification/references/project-skill.md`
- `.codex/skills/agent-factory-core/SKILL.md`
- `.codex/skills/agent-factory-core/references/core-model.md`
