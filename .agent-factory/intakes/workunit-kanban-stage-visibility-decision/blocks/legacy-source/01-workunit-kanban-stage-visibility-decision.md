---
id: workunit-kanban-stage-visibility-decision
date: 2026-07-14
status: answered
basis_request: "워크유닛 헤더에서 칸반을 선택할 수 있어야 하며 선택된 칸반만 출력"
related_artifacts:
  - "docs/work-units/vscode-extension-ui-structure-draft/"
---

# WorkUnit 칸반 단계 표시 결정

## 확인된 Human Fact

- WorkUnit TabHeader에서 칸반 표시 대상을 선택할 수 있어야 한다.
- Body에는 선택한 대상만 표시되어야 한다.
- 각 칸반 단계는 세로 스크롤을 가진다.
- 단계별 스크롤바는 너비 0으로 설정하여 보이지 않게 한다.

## 결정 질문

WorkUnit TabHeader에서 선택하는 대상은 여러 칸반 보드, 칸반 단계 또는 두 종류 모두 중 무엇인가?

## 선택지

- A: 여러 칸반 보드 중 하나를 선택하고 Body에는 선택된 보드의 5단계 전체를 표시한다.
- B: 표시할 칸반 단계를 선택하고 Body에는 선택된 단계만 표시한다.
- C: 칸반 보드 선택과 단계 선택을 모두 제공한다.

## 추천

A. 최초 요청의 "칸반 선택"이라는 표현을 보드 선택으로 해석하면서 기존 5단계 전체를 보존하는 선택지였다.

## 현재 결정

2026-07-14 Human이 B를 구체화하여 선택했다.

- WorkUnit TabHeader에서는 표시할 칸반 단계를 선택한다.
- Body에는 선택한 단계만 표시한다.
- `Done`처럼 선택하지 않은 단계는 항상 표시하지 않아도 된다.
- 선택 컨트롤 형식과 기본 표시 단계는 아직 정하지 않았다.
