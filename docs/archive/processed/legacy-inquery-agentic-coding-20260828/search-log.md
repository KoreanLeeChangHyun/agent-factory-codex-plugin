# 검색 기록

> 조사일 2026-08-28 (Asia/Seoul). 공개 웹의 완전 열거가 아니라 범주별 1차 자료 우선의 체계적 탐색 기록이다.

## 검색어 묶음

실제 검색은 아래 개념을 조합해 영어 중심으로 수행했고, 결과 페이지가 아니라 원문 URL을 `sources.md`에 남겼다.

1. **정의/구조:** `agentic coding definition`, `building effective agents coding`, `coding agent architecture`, `ReAct reasoning acting`, `Reflexion coding`, `CodeAct`, `SWE-agent ACI`, `context engineering coding agents`.
2. **역사/표준:** `GitHub Copilot 2021 official`, `OpenAI Codex 2021`, `Model Context Protocol official November 2024`, `AGENTS.md standard`, `Agent Skills standard`.
3. **상용 제품:** `OpenAI Codex official`, `Claude Code docs`, `GitHub Copilot coding agent`, `Cursor background agents security`, `Windsurf Cascade docs`, `Devin docs`, `Replit Agent docs`, `Amazon Q Kiro`, `Gemini CLI Antigravity transition`.
4. **오픈소스:** `OpenHands GitHub license`, `SWE-agent GitHub`, `aider license`, `Cline license`, `goose Apache`, `Continue agent license`, `Gemini CLI Apache`.
5. **벤치마크:** `SWE-bench original Verified Multilingual Multimodal Live Pro`, `SWE-Lancer`, `Terminal-Bench`, `RE-Bench`, `software task time horizon`, `benchmark contamination infrastructure noise cost reproducibility`.
6. **보안/거버넌스:** `OWASP agentic security`, `prompt injection coding agents`, `excessive agency`, `NIST SSDF generative AI`, `coding agent supply chain secrets data exfiltration sandbox permissions`.
7. **생산성/품질:** `GitHub Copilot randomized trial 55.8`, `METR experienced developers 19% slower`, `DORA AI delivery stability throughput`, `AI generated code security empirical`, `Claude Code usage expertise`.
8. **실무/교육:** `coding agent best practices repo instructions tests review CI rollback observability`, `agentic coding learning path`.

도메인 제한 검색은 `anthropic.com`, `openai.com`, `docs.github.com`, `github.com` 공식 조직, `aws.amazon.com`, `docs.cursor.com`, `docs.replit.com`, `docs.windsurf.com`, `swebench.com`, `metr.org`, `nist.gov`, `owasp.org`, `arxiv.org`, `openreview.net`을 우선했다.

## 조사 범주와 포화 판단

| 범주 | 교차 확인 방식 | 포화 판단 |
|---|---|---|
| 정의·경계 | Anthropic architecture 글 + ReAct/ACI 논문 + 제품 docs | 새 결과가 “모델+tools+feedback loop” 변형을 반복하여 포화 |
| 역사 | GitHub/OpenAI/Anthropic 공식 발표 + benchmark 논문 날짜 | 주요 2021–2026 이정표가 반복되어 포화 |
| 구조 | general agent pattern, SWE-agent/CodeAct, AWS textcode, 제품 security docs | model/plan/context/ACI/test/HITL/sandbox 요소가 반복되어 포화 |
| 제품 | 상용 9계열, OSS 6계열의 공식 문서/저장소와 라이선스 | 시장 전체가 아니라 대표 배포 형태(IDE/CLI/cloud/SDK)가 채워진 수준에서 중단; 완전 포화 아님 |
| 벤치마크 | 원 논문/공식 leaderboard + 오염/infra 비판 + fresh/private 후속 | SWE-bench 계열과 terminal/economic/R&D 축이 채워져 핵심 범주 포화 |
| 보안 | OWASP, NIST, 공급자 containment 문서 | 위험과 통제 항목이 반복되어 포화; 실제 incident 전수조사는 아님 |
| 생산성 | 상반 RCT 2개, DORA 관찰, 공급자 usage study | 효과 이질성이 확인됐지만 장기 독립 자료 부족으로 비포화/연구 공백 처리 |

검색 결과 52개 원문을 최종 목록에 유지했다. 동일 문서의 PDF/HTML, 미러, 보도자료 재게시, 검색 결과 URL은 중복 제거했다.

## 링크 확인 방식

- 검색 결과의 발췌만 믿지 않고 공식 페이지/논문/저장소 원문을 열어 제목, 발행 주체, 날짜, 주장 지지 여부를 확인했다.
- 빠르게 변하는 기능은 기준일을 붙였고, 지속 갱신 문서는 날짜 없음/지속 갱신으로 표시했다.
- 라이선스는 공식 저장소 README/License 표기를 사용했다. 상용 서비스와 OSS client/harness의 라이선스를 합치지 않았다.
- benchmark 점수는 역사적 맥락을 설명하는 데만 제한적으로 사용하고, 최신 순위표를 고정된 사실로 복사하지 않았다.

## 접근 실패·불안정

1. **Windsurf Cascade 영어 canonical 문서:** 검색 인덱스가 스페인어/포르투갈어/독일어 locale을 우선 반환했다. 동일 공식 문서 구조와 canonical URL을 확인해 기능만 요약했으며 정확한 모델/가격은 제외했다.
2. **Replit Agent 세부 페이지:** 과거 `/replitai/agent` 계열 URL과 현행 문서 라우팅이 바뀌고 동적 문서 index를 사용했다. 현행 `Build with Agent`와 mode 문서는 접근 가능했으나 가격 수치를 수집하지 않았다.
3. **Cursor 문서:** `docs.cursor.com`, `cursor.com/docs`, `prod.cursor.com/docs` 사이 URL 이동이 있었다. 공식 현행 페이지의 제품/보안 주장을 사용하고 URL 변동을 한계로 기록했다.
4. **SWE-agent 라이선스:** 검색 결과만으로 현행 저장소의 정확한 license 문구를 안정적으로 확보하지 못해 비교표에서 “원문 확인 필요”로 보수적으로 표시했다.
5. **유료/로그인 자료:** Gartner/Forrester류 시장 보고서, 기업 내부 dashboard, 유료벽 논문, 제품 admin console 기능은 로그인/비공개이므로 제외했다. 공개 요약만으로 세부 수치에 접근하지 않았다.
6. **동적 leaderboard:** 일부 순위표는 JavaScript·계속 갱신 형태다. 기준일의 “1위”를 보고서 결론으로 쓰지 않고 평가 설계·변형 자체만 원문에서 확인했다.
7. **삭제/robots:** 이번 최종 인용 집합에서는 원문을 전혀 열지 못한 핵심 출처를 인용하지 않았다. 검색 결과에 나타난 미러/재게시/robots 제한 가능 페이지는 공식 대체 원문이 있으면 제외했다.

## 의도적으로 제외한 범위

- 모든 모델별 최신 SWE-bench 점수와 매일 변하는 제품 가격/쿼터의 전수표.
- SEO “top 50 coding agents”, affiliate 비교, 출처 없는 벤더 순위, 소셜 미디어 경험담의 정량 합산.
- 비공개 기업 생산성 수치, 고객 testimonial을 독립 실증 근거로 취급하는 것.
- 단순 code completion 모델/IDE 확장의 전수 목록. agent loop가 없으면 역사적 비교 외 제외.
- 일반-purpose agent framework(LangChain, LangGraph, AutoGen, CrewAI 등)의 전수 비교. 코딩 시스템을 만들 수 있지만 이번 질문의 주요 coding products와 직접 benchmark에 집중했다.
- 중국권/일본권을 포함한 모든 지역 제품, 교육과정, 특허, 법원 사건의 전수 조사. 언어·접근성 한계로 후속 범위다.
- EU AI Act, 미국 주별 법률, 저작권 소송의 법률 자문 수준 분석. 변동성과 관할 차이가 커서 risk 항목만 표시했다.

## 모순·마케팅 처리

- Copilot RCT의 55.8% 향상과 METR RCT의 19% 저하는 하나의 평균으로 합치지 않았다. 과제, 사용자, repo familiarity, 도구 세대, outcome 차이를 함께 기록했다.
- DORA 2024의 delivery 지표 악화와 2025 요약의 throughput 개선 방향 전환은 기술·조직 환경의 시간 민감성으로 기록했다.
- vendor의 “자율 software engineer”, 고객 시간 절감, benchmark SOTA는 기능/사례 증거일 뿐 일반 효능 사실로 쓰지 않았다.
- OpenAI의 2026 SWE-bench 신호 저하 분석은 중요한 최신 1차 분석이나 benchmark 경쟁 이해관계를 명시했다.
- Open source라는 표현은 harness/client license에만 적용하고 모델·cloud·enterprise 기능에 자동 확장하지 않았다.

## 남을 수 있는 누락

장기간 유지되는 공개 웹 전체를 완전 열거할 수 없다. 검색엔진 미색인 문서, 삭제된 릴리스 노트, 비영어 자료, 비공개 eval, 작은 신규 프로젝트, 2026-08-28 당일 변경, 이후 수정된 계속 갱신 문서가 빠질 수 있다. 제품군은 대표성 포화이지 전수 포화가 아니며, 실증 생산성·장기 품질은 공개 연구 자체가 아직 포화되지 않았다.
