---
id: work-unit-execution-context-sufficiency
date: 2026-07-14
type: web-research
basis_request: "Human request 2026-07-14: 조사한 내용을 기록하고 이를 위한 Work Unit을 생성한다."
related_artifacts:
  - docs/work-units/work-unit-execution-context-sufficiency-research/data/work-unit.json
sources:
  - https://developers.openai.com/cookbook/articles/codex_exec_plans
  - https://json-schema.org/overview/what-is-jsonschema
  - https://json-schema.org/understanding-json-schema/reference/string
  - https://www.nasa.gov/reference/appendix-c-how-to-write-a-good-requirement/
  - https://www.nasa.gov/reference/4-2-technical-requirements-definition/
  - https://scrumguides.org/scrum-guide.html
---

# 무히스토리 Execution을 위한 Work Unit 문맥 충분성 조사

## 조사 질문 (Question)

현재 Agent Factory Work Unit v3 구조는 이전 대화가 없는 신규 Execution 세션이 하나의 Work Unit id만 받아 작업할 때 필요한 문맥을 표현할 수 있는가? 또한 현재 `schema-valid` 및 `ready` 상태는 그 문맥이 실제로 충분하다는 것을 기계적으로 보장하는가?

이 조사는 다음 두 판단을 분리한다.

1. **표현 가능성**: 현재 필드 집합에 목표, 범위, 실행 계획, 검증, 검토 경계와 미해결 항목을 기록할 수 있는가.
2. **강제력**: 현재 schema와 manager가 그 내용의 의미적 충분성을 검사하여 문맥이 부족한 패키지가 `ready`가 되는 것을 막는가.

## 조사·점검 범위 (Search and Inspection Scope)

### 웹 조사 범위와 검색어

- 무히스토리 실행 계획의 자기완결성: `OpenAI Codex ExecPlan self-contained no prior context`
- JSON Schema가 보장하는 검증 범위와 문자열 제약: `JSON Schema declarative constraints string minLength`
- 요구사항의 명확성, 완전성, 추적성, 검증 가능성: `NASA good requirement completeness traceability verifiability`
- 실행 준비와 완료 기준의 투명성: `Scrum Guide ready Product Backlog item Definition of Done`

모든 URL은 2026-07-14에 HTTP `200`으로 접근 가능함을 확인했다. 결론에는 공식 T1 또는 공식 발행자의 T2 자료만 사용했다.

### 저장소 점검 범위와 명령

```text
rg -n '"version"|"status"|sourceDesignRefs|unresolvedItems|ready|basis|blocking|x-packageStateConsistency' docs/work-units/*/data/work-unit.json .codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json
rg -n 'ready|validate|unresolved|preflight|sourceDesignRefs|traceability' .codex/skills/work-unit-planner-af/assets/scripts/work_unit.py .codex/skills/work-unit-planner-af/tests/test_work_unit_manager.py .codex/skills/agent-factory-lifecycle-af/references/lifecycle.md
rg -n '/goal|Goal objective|lacks enough basis|fresh session|preflight|readiness' .codex/skills docs -g '*.py' -g '*.js' -g '*.mjs' -g '*.json' -g '*.md'
python3 .codex/skills/work-unit-planner-af/assets/scripts/work_unit.py validate docs/work-units/work-unit-json-storage-format-v3
python3 .codex/skills/work-unit-planner-af/assets/scripts/work_unit.py validate docs/work-units/vscode-extension-ui-structure-draft
python3 .codex/skills/work-unit-planner-af/assets/scripts/work_unit.py validate docs/work-units/work-unit-json-storage-format
sha256sum .codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json /home/deus/.codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json
diff -u /home/deus/.codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json .codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json
```

의미적으로 빈약한 패키지가 통과하는지 확인하기 위해 manager의 필수 인수에 모두 `x`를 넣은 임시 `context-poor` 패키지를 `create`한 뒤 `validate`했다. 임시 패키지는 검증 후 삭제했다. 전체 재현 명령과 출력은 관련 Work Unit의 `evidence/logs/context-poor-counterexample.log`에 기록한다.

## 웹 출처 (Web Source Table)

| 출처 | 등급 | 신선도 | 핵심 근거 | 이 조사에서의 사용 경계 |
| --- | --- | --- | --- | --- |
| [OpenAI, Using PLANS.md for multi-hour problem solving](https://developers.openai.com/cookbook/articles/codex_exec_plans) | T2 primary expert | F5 — 2025-10-07 발행 | ExecPlan 독자는 현재 worktree와 단일 계획 파일만 가진 저장소 초보자로 가정되며, 계획은 이전 기억이나 외부 문맥 없이 자기완결적이어야 한다. | Agent Factory 계약 자체가 아니라 무히스토리 실행 문서 충분성의 비교 기준으로만 사용한다. |
| [JSON Schema, What is JSON Schema?](https://json-schema.org/overview/what-is-jsonschema) | T1 authoritative primary | F5 — 2026 공식 문서, 현재 최신 dialect `2020-12` 명시 | JSON Schema는 JSON 구조와 제약을 선언하며 validator는 인스턴스가 선언된 schema에 부합하는지 검사한다. | schema-valid가 선언되지 않은 의미 조건까지 자동 보장하지 않는다는 판단에 사용한다. |
| [JSON Schema, string](https://json-schema.org/understanding-json-schema/reference/string) | T1 authoritative primary | F5 — 2026 공식 문서 | 빈 문자열도 단순 `type: string`에는 유효하며 길이 제한은 `minLength` 같은 명시적 keyword가 필요하다. | `minLength: 1`도 `x`의 업무 의미를 판정하지 못한다는 반례 해석에 사용한다. |
| [NASA, Appendix C: How to Write a Good Requirement](https://www.nasa.gov/reference/appendix-c-how-to-write-a-good-requirement/) | T1 authoritative primary | F1 — 공식 현행 reference 페이지이나 본문 발행·수정일 미표시 | 요구사항은 명확·비모호하고 가능한 한 완전해야 하며, 가정은 명시되고, 상위 요구에 양방향 추적되며, 검증 기준을 세울 수 있어야 한다. 제품 요구사항에 personnel/task assignment를 섞지 말라는 지침도 있다. | 일반 요구 품질 기준으로만 사용하며 Agent Factory 필드나 조직 역할을 새로 요구하는 근거로 사용하지 않는다. |
| [NASA, 4.2 Technical Requirements Definition](https://www.nasa.gov/reference/4-2-technical-requirements-definition/) | T1 authoritative primary | F1 — 공식 현행 reference 페이지이나 본문 발행·수정일 미표시 | 요구사항은 stakeholder expectation에 추적되고, 유효한 가정에 근거하며, 실행 결과를 검증할 충분한 정보를 가져야 한다. 요구만 보고 소통 없이 구현하면 다른 해석의 원치 않는 결과를 만들 위험이 있다고 명시한다. | 의미적 readiness가 구조 검증과 별도라는 비교 근거로만 사용한다. |
| [The Scrum Guide](https://scrumguides.org/scrum-guide.html) | T1 authoritative primary | F3 — 2020 공식 Guide, 현재 공식 사이트에서 제공 | refinement는 backlog item에 설명·순서·크기 같은 상세를 더해 투명성을 높이며, Definition of Done은 필요한 품질 측정을 충족한 상태의 공식 설명이다. | Agent Factory에 Scrum 역할을 도입하지 않고 Ready/Done에 투명한 기준이 필요하다는 보조 근거로만 사용한다. |

최고 출처 등급은 `T1 authoritative primary`이다. NASA 두 페이지의 발행·수정일이 표시되지 않아 freshness는 `F1`로 보수적으로 기록했지만, 두 자료는 비시점성 요구공학 원칙에만 사용했으며 2026-07-14 현재 공식 URL 접근성을 확인했다.

## 저장소 근거 (Repository Evidence Table)

| 근거 | 재현 위치 또는 명령 | 확인 내용 |
| --- | --- | --- |
| v3 표현 필드 | `.codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json:85` 및 `:109` | `goal`, `scope`, `outOfScope`, `assumptions`, `constraints`, `plan`, `acceptanceCriteria`, `definitionOfDone`, `testCriteria`, AI/Human checklist, review method, expected output, dependencies, unresolved items가 필수 구조에 포함된다. |
| 별도 first-class basis 부재 | `.codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json:85` 및 `:114` | `sourceDesignRefs`는 있으나 Design Document가 아닌 실행 근거의 유형·위치·제약·검증 상태를 구조화한 `basis` 객체는 없다. |
| 자유 문자열 traceability | `.codex/skills/work-unit-planner-af/assets/schema/traceability.schema.json:7` | `requirementRefs`만 최소 한 항목을 요구하고 모든 ref 배열의 항목은 일반 문자열이다. 참조 유형, 해석 가능성, 대상 존재 여부는 schema가 강제하지 않는다. |
| `unresolvedItems` 비구조화 | `.codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json:191` | 미해결 항목은 문자열 배열이며 blocking 여부, 해소 조건, 상태를 나타내는 구조가 없다. 빈 배열도 유효하다. |
| `ready` 생성 | `.codex/skills/work-unit-planner-af/assets/scripts/work_unit.py:322` 및 `:337` | `new_package`는 입력 내용의 의미를 평가하는 분기 없이 새 패키지 status를 항상 `ready`로 설정한다. |
| validator 경계 | `.codex/skills/work-unit-planner-af/assets/scripts/work_unit.py:225` 및 `:254`-`:281` | validator는 JSON Schema, canonical path/reference, evidence, package state 조합을 확인하지만 goal·scope·계획·수용 기준이 실제 실행에 충분한지 의미적으로 판정하는 readiness 단계는 없다. |
| 현재 테스트 경계 | `.codex/skills/work-unit-planner-af/tests/test_work_unit_manager.py:398`, `:767`, `:845`, `:903` | 테스트는 필수 필드/비어 있지 않은 배열, terminal sentinel, 상태 일관성 등을 검증한다. 업무 의미의 충분성을 판정하는 테스트는 확인되지 않았다. |
| 문맥 빈약 반례 | `evidence/logs/context-poor-counterexample.log` | goal, scope, plan, acceptance, DoD, test, checklist, review method, expected output, requirement ref를 모두 `x`로 둔 임시 패키지가 `status: ready`로 생성되고 v3 validate를 통과했다. |
| 실제 v3 표본 | manager `validate` 명령 | `work-unit-json-storage-format-v3`와 `vscode-extension-ui-structure-draft`는 모두 `schemaVersion: 3.0.0`, `valid: true`였다. 이는 구조적 유효성을 증명하지만 각 패키지의 신규 세션 실행 충분성을 별도로 증명하지는 않는다. |
| legacy 경계 | manager `validate docs/work-units/work-unit-json-storage-format` | `2.0.0`은 `legacy package schema version 2.0.0 is unsupported`로 거부됐다. 이 결과는 v3 검증과 구분된다. |
| `/goal` 실행 규칙 | `.codex/skills/agent-factory-lifecycle-af/references/lifecycle.md:156`-`:182` | 새 세션은 패키지 전체를 읽고 충분한 basis가 없으면 중단하도록 문서화되어 있다. scoped `rg`에서는 이 판단을 실행 전에 자동화하는 별도 preflight 구현을 찾지 못했다. 따라서 현재 최종 방어선은 실행 Agent의 문서 기반 판단이다. |
| `$CODEX_HOME` drift | project와 `/home/deus/.codex/skills/work-unit-planner-af/`의 `find`, `sha256sum`, `diff` | project schema SHA-256은 `90e43e...ac9e3`, HOME schema는 `f7ced3...17cb0`으로 다르다. HOME에는 `assets/scripts/work_unit.py`, `report.schema.json`, evidence schema와 tests가 없고 Work Unit schema도 이전 계약이다. |
| Design Document 확인 | `find docs/design-documents -type f` 및 주제 검색 | `vscode-extension-ui-structure` Design Document만 존재하며 본 연구 주제에 직접 대응하는 Design Document는 없다. 연구 결과가 기존 Design Document의 제품 설계를 변경하지 않으므로 갱신하지 않는다. |

## 조사 결과 (Findings)

### 1. 현재 v3는 충분한 실행 문맥을 **표현할 수 있다**

`work-unit.schema.json`은 목표, 범위와 제외 범위, 가정·제약, 계획, 수용 기준, Definition of Done, 테스트 기준, AI/Human checklist, Human review method, expected output, dependencies와 unresolved items를 담는다. lifecycle 문서도 신규 세션이 이 패키지를 실행 source of truth로 사용하도록 명시한다. 따라서 작성자가 구체적이고 추적 가능한 내용을 채우면, 무히스토리 세션에 필요한 문맥을 한 패키지로 전달할 표현 공간은 존재한다.

### 2. 현재 v3는 그 문맥의 **의미적 충분성을 보장하지 않는다**

현재 schema는 대부분 비어 있지 않은 문자열 또는 배열을 요구한다. JSON Schema 공식 설명과 실제 `context-poor` 반례가 함께 보여 주듯, 구조적 유효성은 선언된 형식 제약의 충족을 뜻할 뿐 `x`가 실행 가능한 목표나 검증 가능한 기준인지 판단하지 않는다. manager는 새 패키지를 무조건 `ready`로 생성하며 validator에는 별도 semantic readiness 판정이 없다.

따라서 다음 명제는 구분해야 한다.

- `schema-valid`: 현재 JSON 구조·값 형식·package state 계약에 부합한다.
- `ready`: 현재 manager가 생성 시 부여하며 상태 조합상 실행 전 상태다.
- `fresh-session executable`: 신규 Agent가 숨은 문맥 없이 범위와 성공 조건을 이해하고 실행·검증·보고할 수 있다.

현재 계약에서 앞의 두 상태만으로 세 번째 상태가 논리적으로 보장되지는 않는다.

### 3. basis와 unresolved item의 의미가 구조화되지 않았다

Design Document 참조는 first-class 필드지만, 다른 허용 근거인 Human request, Goal, 연구, repository/runtime/review evidence는 `traceability.json`의 자유 문자열에 들어간다. 문자열이 어떤 basis 유형인지, 실제 대상을 가리키는지, 실행 범위를 어떻게 제한하는지 schema가 판정하지 않는다.

또한 `unresolvedItems`는 자유 문자열 배열이므로 차단 항목과 비차단 항목을 기계적으로 구분할 수 없다. 본 Work Unit처럼 문자열 앞에 `비차단:`을 쓰는 것은 사람이 읽는 관례이지 schema 계약이 아니다.

### 4. `/goal` preflight는 규칙으로는 있으나 자동 검증으로는 확인되지 않았다

lifecycle은 신규 세션이 전체 패키지를 읽고 basis가 부족하면 중단하도록 요구한다. 그러나 조사 범위의 Python/JavaScript/JSON/Markdown 검색에서는 goal 해석 직후 semantic readiness를 자동 검사하는 실행 가능한 preflight를 찾지 못했다. 즉 문서 규칙은 존재하지만, schema-valid `ready` 패키지를 실행 Agent가 다시 읽고 판단해야 한다.

### 5. project v3와 `$CODEX_HOME` 설치본이 동일 계약이 아니다

Agent Factory lifecycle은 `$CODEX_HOME/skills/`를 active location으로 설명하지만, 이 프로젝트 Work Unit이 지정한 project v3 manager와 HOME 설치본은 현재 동기화되어 있지 않다. HOME에는 manager 자체와 v3 report/evidence schema가 없고 `work-unit.schema.json`도 이전 형태다. 따라서 project v3의 검증 결과를 HOME 설치본 전체에 일반화할 수 없다.

### 6. 기존의 `담당자` 필드 권고는 철회한다

현재 Agent Factory Work Unit 계약, `unresolvedItems`, lifecycle 어디에도 별도 `담당자` 필드를 필수로 요구하는 근거가 없다. NASA 자료의 일반 TBR 관리 예시는 Agent Factory 데이터 모델 요구가 아니며, 같은 NASA validation checklist는 제품 요구사항에 personnel/task assignment를 섞지 말라고 구분한다.

확인된 현재 경계는 다음뿐이다.

- AI는 Work Unit을 실행하고 검증 증거, AI Review, Human review 자료를 준비한다.
- Human은 승인 또는 rework를 결정하며, 병합과 PR 승격도 별도로 결정한다.

따라서 이전 `담당자` 표현은 근거 없는 확장이었으며 이 조사에서는 철회한다.

## 권고 (Recommendations)

아래 항목은 **승인된 요구사항이나 구현 결과가 아니라 조사 기반 후속 제안**이다. 정확한 데이터 모델과 적용 범위는 별도 Intake와 Human 결정이 필요하다.

1. Design Document 외의 실행 basis도 유형, 참조, 범위 제약과 검증 상태를 구분할 수 있는 first-class 구조로 만들지 검토한다.
2. unresolved item의 blocking 여부와 해소 조건을 machine-readable하게 만들지 검토한다. 특정 역할이나 담당자 필드를 자동으로 추가하지 않는다.
3. `ready` 전환 전에 목표·범위·수용 기준·검증 방법·근거 참조의 의미적 충분성을 확인하는 readiness gate를 둘지 검토한다.
4. `/goal <id>` 해석 직후 schema validation과 별도로 fresh-session sufficiency를 확인하는 preflight를 둘지 검토한다.
5. project v3와 `$CODEX_HOME` 설치본의 전파·동기화 정책은 별도 Work Unit과 Human review로 결정한다.

## 제한사항 (Limitations)

- 이 조사는 지정된 project v3 schema, manager, tests, 세 개의 현재 v3 패키지, 한 legacy 패키지, lifecycle 규칙과 HOME 설치본을 점검했다. 모든 미래 Work Unit의 내용 품질을 평가하지 않았다.
- `rg` 결과의 부재는 조사한 저장소 범위에 executable preflight가 없다는 증거이며, 외부 runtime이나 조사 범위 밖 시스템 전체의 부재를 증명하지 않는다.
- `context-poor` 반례는 의미 검증 부재를 입증하기 위한 최소 사례다. 유효한 실제 v3 표본의 내용이 부족하다고 판정하는 근거로 사용하지 않는다.
- NASA 두 공식 페이지에는 발행·수정일이 표시되지 않아 freshness를 `F1`로 기록했다. 해당 자료는 최신 API나 제품 상태가 아닌 비시점성 요구공학 품질 기준에만 사용했다.
- HOME drift의 해결 방향, 배포 방법과 우선순위는 조사 범위 밖이다.

## 미해결 항목 (Unresolved Items)

- 비차단: project v3 Agent Factory skill과 `/home/deus/.codex/skills` 설치본의 전파·동기화 여부는 별도 Human 결정과 Work Unit이 필요하다.
- 비차단: Work Unit schema, readiness gate, `/goal` preflight 개선 구현 여부와 정확한 데이터 모델은 본 연구 후 별도 Intake와 Human 결정이 필요하다.

## 결론 (Conclusion)

결론은 **부분적 충분성**이다.

현재 Work Unit v3는 무히스토리 Execution에 필요한 주요 내용을 표현할 수 있다. 그러나 `schema-valid` 및 `ready`는 구조와 상태 조합의 유효성만 나타내며, 신규 세션이 실행하기에 충분한 의미적 문맥을 보장하지 않는다. `x`만 채운 `ready` 패키지가 validate를 통과한 반례가 이 차이를 직접 입증한다.

따라서 현재 안전성은 작성자가 구체적 basis와 실행 기준을 기록하고, `/goal` 실행 Agent가 lifecycle 규칙에 따라 전체 패키지를 읽어 부족하면 중단하는 사람·Agent 수준의 검토에 의존한다. schema, readiness gate, preflight 또는 HOME 동기화 변경은 이 조사에서 구현하지 않았으며 후속 Human 결정 대상으로 남긴다.
