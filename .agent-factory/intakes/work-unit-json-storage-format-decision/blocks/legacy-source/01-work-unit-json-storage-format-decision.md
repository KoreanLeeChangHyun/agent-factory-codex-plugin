---
id: work-unit-json-storage-format-decision
date: 2026-07-14
status: answered
basis_request: "워크 유닛 저장 포멧을 JSON으로 변경하는 Work Unit 생성"
related_artifacts:
  - "docs/research/work-unit-json-storage-format.md"
  - "planned: docs/work-units/work-unit-json-storage-format/"
---

# Work Unit JSON 저장 계약 결정

## 확인된 Human Fact

- Work Unit 저장 형식을 JSON으로 변경한다.
- HTML 렌더링의 의미 데이터 원본으로 JSON을 사용한다.
- Work Unit 생성 전에 자료 조사를 수행한다.

## 결정 질문

현재 필수 `output/result.md`를 어떤 JSON 계약으로 대체할 것인가?

## 선택지

- A: 새 major contract에서 `data/report.json`을 canonical result로 추가하고 필수 `output/result.md`를 제거한다. HTML과 Markdown은 선택적 파생물로만 둔다.
- B: 새 major contract에서 `output/result.json`으로 직접 교체한다.
- C: canonical JSON result를 추가하되 `result.md`를 선택적 파생 export로 유지한다.

## 조사 기반 추천

A. JSON source of truth의 소유 위치를 `data/`로 유지하고 renderer와 validator가 동일한 구조화 계약을 사용하므로 DRY, 검증 가능성, 장기 유지보수에 가장 적합하다.

## 현재 결정

2026-07-14 Human이 A를 선택했다.

- 새 major contract에서 `data/report.json`을 canonical result로 추가한다.
- 필수 `output/result.md`를 제거한다.
- HTML과 Markdown은 선택적 파생물로만 둔다.
- 기존 package는 자동 덮어쓰기 없이 별도 migration 경계로 보존한다.
