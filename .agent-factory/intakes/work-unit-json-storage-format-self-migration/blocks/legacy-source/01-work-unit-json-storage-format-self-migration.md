---
id: work-unit-json-storage-format-self-migration
date: 2026-07-14
status: answered
selected_strategy: B
related_artifacts:
  - "docs/interviews/work-unit-json-storage-format-decision.md"
  - "docs/work-units/work-unit-json-storage-format/"
  - "docs/work-units/work-unit-json-storage-format-v3/"
---

# 실행 Work Unit 자체의 2.0.0 → 3.0.0 전환 결정

## 이전 결정과 이번 질문의 구분

기존 Human 결정 A는 canonical 결과 저장 위치를 `data/report.json`으로
정하고 필수 `output/result.md`를 제거하는 저장 계약 결정이다. 현재 active
Work Unit package 자체를 어떤 방식으로 3.0.0에 맞출지는 해당 기록에서
결정되지 않았다.

## 확인된 사실

- 현재 package id와 경로는
  `docs/work-units/work-unit-json-storage-format/`이다.
- 현재 `data/work-unit.json`은 `version: 2.0.0`, `status: working`이다.
- 현재 package에는 `data/report.json`이 없고 legacy
  `output/result.md`가 존재한다.
- 현재 Work Unit DoD는 Design Document 결과와 실행 결과를
  `data/report.json`에 기록하도록 요구한다.
- 새 manager와 lifecycle은 2.0.0을 unsupported legacy로 처리하고 별도
  3.0.0 migration destination을 요구한다.
- 기존 Human 결정은 기존 package를 자동 덮어쓰지 않고 별도 migration
  경계로 보존하도록 한다.
- 별도 destination id/path, archive path, 현재 Goal과 새 package의 연결
  방식은 기록되어 있지 않다.

## 결정 질문

현재 active 2.0.0 실행 package를 어떤 방식으로 최종 3.0.0 report package에
연결할 것인가?

| 선택지 | 결정 | 장점 | 단점 |
| --- | --- | --- | --- |
| A | 현재 active package를 같은 id/path에서 수동 3.0.0으로 승격하는 예외를 새로 승인한다. | 현재 DoD와 Goal identity를 그대로 완료하며 새 id/path를 만들지 않는다. | 기존 package 보존 결정의 명시적 예외이고 정식 `migrate` 경로가 아니다. 2.0.0 bytes가 보존되지 않으며 `output/result.md` 삭제 전 별도 최종 확인이 필요하다. |
| B | 현재 package를 보존하고 Human이 정한 새 id/path로 manager `migrate`를 실행한다. | 기록된 source 보존 결정과 새 manager의 별도 migration 경계를 직접 지킨다. | 새 id/path와 Goal 연결을 Human이 정해야 하고 기존 실행 기록을 새 package에 반영하는 후속 작업이 필요하다. |
| C | 현재 package를 Human이 정한 archive path로 보존한 뒤 원래 id/path를 새 3.0.0 package로 교체한다. | legacy snapshot과 기존 Goal path를 함께 유지할 수 있다. | manager에 없는 move/replace 작업, archive 규칙과 중복 id 정리가 필요하며 교체 전 별도 파괴적 작업 확인이 필요하다. |

## 추천

B를 추천한다. 기존 Human 결정이 2.0.0 package의 자동 덮어쓰기를 금지하고
별도 migration 경계에서 source를 보존하도록 했으며, 현재 manager도 같은
source/destination을 거부하기 때문이다. 새 id/path를 정하는 비용은 있지만
기록된 결정과 구현된 migration 안전 경계를 예외 없이 유지한다.

이전 AI 추천 A는 결정 당시 이 Work Unit이 planned 상태였다는 사실을 근거로
active execution record 예외를 추론한 것이며, Human이 승인한 예외가 아니므로
추천 근거로 사용하지 않는다.

## 기록된 결정

2026-07-14 Human이 B를 선택했다.

- 현재 `docs/work-units/work-unit-json-storage-format/` 2.0.0 package는
  source로 보존한다.
- manager `migrate`로 별도 3.0.0 destination package를 생성한다.
- Human이 새 package id를 `work-unit-json-storage-format-v3`, destination
  path를 `docs/work-units/work-unit-json-storage-format-v3/`로 확정했다.
- 확정된 destination에 manager `migrate`를 실행하고 즉시 full validate를
  통과시킨다.

## 승인 경계

- A 선택 후 `output/result.md`를 삭제하기 전 정확한 대상 파일에 대한
  별도 최종 확인이 필요하다.
- B와 새 id 및 destination path가 확정됐으며 source 보존 검증을 포함한
  migration 실행이 승인됐다.
- C는 archive path와 교체 대상·절차에 대한 별도 최종 확인이 필요하다.
- 어떤 선택도 `/home/deus/.codex/skills` 전파, merge 또는 PR promotion을
  승인하지 않는다.
