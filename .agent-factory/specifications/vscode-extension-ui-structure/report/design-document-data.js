"use strict";

// Generated from Design Document JSON. Do not edit by hand.
globalThis.__VSCODE_EXTENSION_UI_STRUCTURE_REPORT_DATA__ = Object.freeze({
  "generatedFrom": {
    "manifest": "data/manifest.json",
    "sections": [
      "data/sections/project-core.json",
      "data/sections/requirements.json",
      "data/sections/ui-structure.json",
      "data/sections/governance-and-verification.json"
    ],
    "collections": [
      "data/decisions/design-decisions.json",
      "data/diagrams/diagram-metadata.json",
      "data/snapshots/pre-execution-baseline.json",
      "data/events/change-history.json"
    ],
    "diagrams": [
      "diagram/ui-tab-structure.json",
      "diagram/work-unit-status.json"
    ],
    "workUnit": "docs/work-units/vscode-extension-ui-structure-draft/data/work-unit.json"
  },
  "manifest": {
    "id": "vscode-extension-ui-structure",
    "title": "VS Code 확장 UI 구조",
    "status": "draft",
    "sourceOfTruth": "Design Document JSON",
    "lifecyclePhase": "Execution",
    "adoptionTiming": "new-project",
    "sourceWorkUnit": {
      "id": "vscode-extension-ui-structure-draft",
      "path": "docs/work-units/vscode-extension-ui-structure-draft/data/work-unit.json"
    },
    "schema": "data/schema/design-document.schema.json",
    "projectCore": "data/sections/project-core.json",
    "sections": [
      {
        "id": "project-core",
        "title": "Project Core",
        "path": "data/sections/project-core.json",
        "order": 1
      },
      {
        "id": "requirements",
        "title": "요구사항과 완료 경계",
        "path": "data/sections/requirements.json",
        "order": 2
      },
      {
        "id": "ui-structure",
        "title": "UI 구조와 상태 계약",
        "path": "data/sections/ui-structure.json",
        "order": 3
      },
      {
        "id": "governance-and-verification",
        "title": "결정, 검증, 추적성",
        "path": "data/sections/governance-and-verification.json",
        "order": 4
      }
    ],
    "collections": {
      "decisions": "data/decisions/design-decisions.json",
      "diagrams": "data/diagrams/diagram-metadata.json",
      "snapshots": "data/snapshots/pre-execution-baseline.json",
      "events": "data/events/change-history.json"
    },
    "report": {
      "index": "report/index.html",
      "styles": "report/styles.css",
      "script": "report/script.js",
      "generatedData": "report/design-document-data.js",
      "generator": "report/generate-report-data.mjs",
      "role": "Human 검토용 파생 렌더링"
    },
    "references": [
      "reference/sources.json",
      "docs/interviews/workunit-kanban-stage-visibility-decision.md",
      ".codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json",
      "docs/work-units/vscode-extension-ui-structure-draft/data/work-unit.json"
    ]
  },
  "sections": {
    "project-core": {
      "id": "project-core",
      "title": "Project Core",
      "purpose": "확정된 Human Fact만을 근거로 VS Code 확장의 초기 UI 구조를 정의한다.",
      "corePrinciples": [
        "Design Document JSON을 source of truth로 사용한다.",
        "확정된 Human Fact와 repository evidence만 설계 근거로 사용한다.",
        "미정 항목은 구현 결정으로 채우지 않고 명시적으로 유지한다.",
        "Work Unit 상태 변경은 canonical x-statusTransitions와 Human approval boundary를 따른다."
      ],
      "scope": [
        "Dashboard, Intake, Design, WorkUnit 네 탭의 초기 UI 구조.",
        "활성 탭의 TabHeader와 Body가 한 쌍으로 함께 전환되는 관계.",
        "WorkUnit TabHeader의 칸반 단계 표시 선택과 Body의 선택 단계 단독 표시.",
        "Backlog, Ready, Working, Review, Done 5단계 칸반과 title만 표시하는 고정 높이 Work Unit 카드.",
        "canonical 상태 전이와 Human 승인 경계를 따르는 카드 DnD.",
        "단계별 세로 스크롤, 너비 0의 보이지 않는 스크롤바, 정상 흐름 밖 Blocked 예외 상태."
      ],
      "humanApprovalBoundaries": [
        "Review에서 Done으로의 이동은 카드 drop만으로 Human 승인을 대신하지 않는다.",
        "Design Report의 승인 또는 재작업, 병합, PR 승격은 Human이 결정한다."
      ],
      "unresolvedItems": [
        "Dashboard, Intake, Design 각 탭의 TabHeader와 Body 상세 내용.",
        "WorkUnit TabHeader의 단계 선택 컨트롤 형식, 선택 cardinality, 기본 표시 단계와 선택 상태 저장 범위.",
        "고정 Work Unit 카드 높이의 정확한 값, 긴 제목의 overflow 처리, 제목 외 추후 추가할 카드 정보와 카드 액션.",
        "동일 단계 안의 카드 정렬, drag handle, 터치·키보드 대체 동작, 허용되지 않은 drop 피드백, 상태 저장·실패 처리와 Review에서 Done으로 이동할 때의 Human 승인 UI.",
        "Blocked 예외 상태의 표시 위치와 시각적 표현 및 카드가 Blocked로 진입·복귀하는 조작 방식.",
        "단계별 스크롤 영역의 높이·overflow 시작 기준과 키보드·접근성 세부 동작.",
        "VS Code에서 UI가 배치될 호스트 영역.",
        "확장 구현 언어, 프레임워크, VS Code API, 상태 저장과 외부 연동.",
        "시각 디자인, 접근성 세부 기준, 반응형 동작과 아이콘."
      ]
    },
    "requirements": {
      "id": "requirements",
      "title": "요구사항과 완료 경계",
      "userRequest": {
        "source": "docs/work-units/vscode-extension-ui-structure-draft/data/work-unit.json",
        "goal": "확정된 Human Fact만을 근거로 VS Code 확장의 초기 UI 구조를 Design Document JSON과 Human 검토용 Design Report 초안으로 작성한다."
      },
      "lifecycle": {
        "phase": "Execution",
        "workUnit": "vscode-extension-ui-structure-draft",
        "nextPhase": "Human Review"
      },
      "baselineRef": "data/snapshots/pre-execution-baseline.json",
      "outcome": "네 탭, 탭별 TabHeader·Body 전환, WorkUnit 칸반 단계 표시 선택, 카드와 DnD 상태 변경, 스크롤, Blocked 예외 상태를 검토할 수 있는 UI 구조 초안.",
      "completionBoundary": "실행 가능한 VS Code 확장을 구현하지 않고 JSON source와 브라우저에서 열 수 있는 Human 검토용 Design Report 초안을 준비한다.",
      "stakeholders": [
        {
          "role": "Human",
          "concerns": [
            "UI 구조가 확정된 요구와 일치하는지 검토한다.",
            "미정 항목이 임의로 확정되지 않았는지 검토한다."
          ],
          "decisionOwnership": [
            "Design Report 승인 또는 재작업",
            "Work Unit의 Done 승인",
            "병합과 PR 승격"
          ]
        },
        {
          "role": "AI executor",
          "concerns": [
            "Work Unit 범위 안에서 source와 report를 작성한다.",
            "검증과 AI Review 증거를 기록한다."
          ],
          "decisionOwnership": []
        }
      ],
      "functionalRequirements": [
        {
          "id": "FR-001",
          "requirement": "Dashboard, Intake, Design, WorkUnit 네 탭을 제공한다."
        },
        {
          "id": "FR-002",
          "requirement": "활성 탭이 바뀌면 해당 탭의 TabHeader와 Body가 한 쌍으로 함께 바뀐다."
        },
        {
          "id": "FR-003",
          "requirement": "WorkUnit TabHeader에서 표시할 칸반 단계를 선택하고 Body에는 선택한 단계만 표시한다."
        },
        {
          "id": "FR-004",
          "requirement": "선택하지 않은 단계는 숨길 수 있으며 Done도 숨길 수 있다."
        },
        {
          "id": "FR-005",
          "requirement": "WorkUnit Body의 정상 칸반은 Backlog, Ready, Working, Review, Done 순서다."
        },
        {
          "id": "FR-006",
          "requirement": "각 Work Unit은 카드로 표현하고 카드에 처음 보이는 정보는 title뿐이다."
        },
        {
          "id": "FR-007",
          "requirement": "모든 Work Unit 카드는 고정 높이를 사용한다."
        },
        {
          "id": "FR-008",
          "requirement": "허용된 목적 단계로의 drop 뒤 카드 위치와 Work Unit status가 목적 단계에 맞게 함께 변경된다."
        },
        {
          "id": "FR-009",
          "requirement": "허용되지 않은 drop은 status를 변경하지 않고 Review에서 Done으로의 drop은 Human 승인을 대신하지 않는다."
        },
        {
          "id": "FR-010",
          "requirement": "각 정상 단계는 세로 스크롤을 가지며 스크롤바 너비는 0이어서 보이지 않지만 스크롤 동작은 유지된다."
        },
        {
          "id": "FR-011",
          "requirement": "Blocked는 정상 5단계가 아닌 명시적 blocker의 예외 상태다."
        }
      ],
      "nonFunctionalRequirements": [
        {
          "id": "NFR-001",
          "requirement": "Human-facing 설명과 검토 자료는 한국어로 작성한다."
        },
        {
          "id": "NFR-002",
          "requirement": "미정 요구사항과 미승인 기술·시각 디자인을 설계 결정으로 확정하지 않는다."
        },
        {
          "id": "NFR-003",
          "requirement": "Design Document JSON과 파생 Design Report 사이의 추적성을 유지한다."
        }
      ],
      "qualityAttributes": [
        "사실성",
        "추적성",
        "검토 가능성",
        "Human 승인 경계 보존"
      ],
      "assumptions": [],
      "constraints": [
        "canonical 상태 전이는 .codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json을 따른다.",
        "Design Report는 JSON source의 Human 검토용 파생물이며 제품 시각 디자인의 승인본이 아니다."
      ],
      "outOfScope": [
        "실행 가능한 VS Code 확장과 배포 패키지.",
        "호스트 영역, 구현 언어, 프레임워크, VS Code API 선택.",
        "탭별 상세 업무 기능, 카드 추가 정보와 액션, DnD 세부 동작 발명.",
        "아이콘, 색상, 타이포그래피, 간격, 애니메이션의 제품 디자인 확정."
      ],
      "nonGoals": [
        "이 초안에서 Dashboard, Intake, Design 탭의 상세 업무 기능을 정하지 않는다.",
        "이 초안에서 단계 선택 control, DnD 세부 조작과 Blocked 시각 표현을 정하지 않는다.",
        "이 초안을 실행 가능한 VS Code 확장 또는 승인된 제품 시각 디자인으로 만들지 않는다."
      ],
      "acceptanceCriteriaRef": "docs/work-units/vscode-extension-ui-structure-draft/data/work-unit.json#/acceptanceCriteria",
      "definitionOfDoneRef": "docs/work-units/vscode-extension-ui-structure-draft/data/work-unit.json#/definitionOfDone",
      "deferredItemsRef": "data/sections/project-core.json#/unresolvedItems"
    },
    "ui-structure": {
      "id": "ui-structure",
      "title": "UI 구조와 상태 계약",
      "architectureOverview": {
        "level": "conceptual-ui-structure",
        "description": "VS Code 호스트 영역과 구현 기술을 정하지 않은 상태에서 탭, TabHeader, Body, WorkUnit 칸반의 관계만 정의한다.",
        "runtimeArchitecture": null,
        "hostArea": null,
        "implementationTechnology": null
      },
      "tabs": [
        {
          "id": "dashboard",
          "label": "Dashboard",
          "tabHeader": {
            "content": null,
            "status": "unresolved"
          },
          "body": {
            "content": null,
            "status": "unresolved"
          }
        },
        {
          "id": "intake",
          "label": "Intake",
          "tabHeader": {
            "content": null,
            "status": "unresolved"
          },
          "body": {
            "content": null,
            "status": "unresolved"
          }
        },
        {
          "id": "design",
          "label": "Design",
          "tabHeader": {
            "content": null,
            "status": "unresolved"
          },
          "body": {
            "content": null,
            "status": "unresolved"
          }
        },
        {
          "id": "workunit",
          "label": "WorkUnit",
          "tabHeader": {
            "responsibility": "표시할 칸반 단계를 선택한다.",
            "controlType": null,
            "selectionCardinality": null,
            "defaultVisibleStages": null,
            "selectionPersistence": null
          },
          "body": {
            "responsibility": "선택한 정상 칸반 단계만 표시하고 선택하지 않은 단계는 숨긴다.",
            "normalStageOrder": [
              "backlog",
              "ready",
              "working",
              "review",
              "done"
            ]
          }
        }
      ],
      "activeTabContract": {
        "input": "activeTabId",
        "effect": "activeTabId에 해당하는 TabHeader와 Body를 동시에 활성화하고 다른 탭의 두 영역은 함께 비활성화한다.",
        "persistence": null
      },
      "stageVisibilityContract": {
        "input": "selectedNormalStageIds",
        "effect": "WorkUnit Body에는 선택한 정상 단계만 표시하고 선택하지 않은 정상 단계는 숨긴다.",
        "doneCanBeHidden": true,
        "controlType": null,
        "selectionCardinality": null,
        "defaultValue": null,
        "persistence": null
      },
      "reviewHarness": {
        "status": "non_normative",
        "sampleWorkUnitRef": "vscode-extension-ui-structure-draft",
        "initialStatus": "ready",
        "reason": "허용·불허 DnD와 Human approval boundary를 브라우저에서 검토하기 위한 report 전용 시나리오이며 canonical package의 현재 status를 표시하지 않는다."
      },
      "normalStages": [
        {
          "id": "backlog",
          "label": "Backlog",
          "order": 1,
          "meaning": "기록되었지만 실행 준비 전인 Work Unit"
        },
        {
          "id": "ready",
          "label": "Ready",
          "order": 2,
          "meaning": "실행 근거와 범위가 준비된 Work Unit"
        },
        {
          "id": "working",
          "label": "Working",
          "order": 3,
          "meaning": "AI가 실행 중인 Work Unit"
        },
        {
          "id": "review",
          "label": "Review",
          "order": 4,
          "meaning": "AI 실행이 끝나 Human Review를 기다리는 Work Unit"
        },
        {
          "id": "done",
          "label": "Done",
          "order": 5,
          "meaning": "Human Review와 후속 결정을 마친 보존 대상 Work Unit"
        }
      ],
      "exceptionStates": [
        {
          "id": "blocked",
          "label": "Blocked",
          "classification": "exception",
          "meaning": "명시된 차단 사유로 실행을 진행할 수 없는 Work Unit",
          "normalKanbanStage": false,
          "visualPlacement": null,
          "entryAndReturnInteraction": null
        }
      ],
      "workUnitCardContract": {
        "visibleFields": [
          "title"
        ],
        "height": {
          "mode": "fixed",
          "exactValue": null
        },
        "longTitleHandling": null,
        "futureFields": null,
        "actions": null
      },
      "dragAndDropContract": {
        "transitionSource": ".codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json#/x-statusTransitions",
        "statusTransitions": {
          "backlog": [
            "ready",
            "blocked"
          ],
          "ready": [
            "backlog",
            "working",
            "blocked"
          ],
          "working": [
            "ready",
            "review",
            "blocked"
          ],
          "review": [
            "working",
            "done",
            "blocked"
          ],
          "done": [],
          "blocked": [
            "backlog",
            "ready",
            "working",
            "review"
          ]
        },
        "allowedDropResult": [
          "카드를 목적 단계로 이동한다.",
          "canonical Work Unit status를 목적 단계와 일치하도록 변경한다."
        ],
        "disallowedDropResult": "카드 위치와 Work Unit status를 변경하지 않는다.",
        "reviewToDoneRequiresHumanApproval": true,
        "reviewToDoneGuard": "Review에서 Done으로의 drop만으로 Human 승인을 생성하거나 대신하지 않는다.",
        "sameStageOrdering": null,
        "dragHandle": null,
        "touchAlternative": null,
        "keyboardAlternative": null,
        "failurePersistence": null
      },
      "scrollContract": {
        "scope": "각 정상 칸반 단계",
        "direction": "vertical",
        "behavior": "enabled",
        "scrollbarWidth": 0,
        "scrollbarVisible": false,
        "viewportHeight": null,
        "overflowStartThreshold": null,
        "keyboardAndAccessibilityDetails": null
      },
      "conceptualInterfaces": [
        {
          "name": "tab activation",
          "input": "tab id",
          "output": "해당 탭의 활성 TabHeader와 Body 쌍"
        },
        {
          "name": "stage visibility selection",
          "input": "선택한 정상 단계 id",
          "output": "선택한 단계만 포함하는 WorkUnit Body"
        },
        {
          "name": "work unit drop",
          "input": "현재 status와 목적 단계",
          "output": "허용된 경우에만 함께 변경된 카드 위치와 status"
        }
      ],
      "apiModel": {
        "status": "unresolved",
        "reason": "VS Code API와 확장 구현은 이 Work Unit 범위 밖이며 선택 근거가 없다."
      },
      "eventModel": {
        "status": "unresolved",
        "reason": "runtime event 이름, payload와 전달 방식은 이 Work Unit에서 정하지 않았다."
      },
      "dataAndState": {
        "canonicalWorkUnitFieldsUsed": [
          "title",
          "status"
        ],
        "visibleCardField": "title",
        "statusOwnership": "canonical Work Unit",
        "stageSelectionStorage": null,
        "persistence": null,
        "cache": null,
        "migration": null,
        "retention": null
      },
      "fileFormats": [
        "Design Document JSON",
        "Human-facing HTML/CSS/JavaScript report"
      ],
      "errorBehavior": {
        "disallowedTransition": "카드 위치와 status를 변경하지 않는다.",
        "saveFailure": null,
        "runtimeErrorPresentation": null
      }
    },
    "governance-and-verification": {
      "id": "governance-and-verification",
      "title": "결정, 검증, 추적성",
      "decisionsRef": "data/decisions/design-decisions.json",
      "diagramMetadataRef": "data/diagrams/diagram-metadata.json",
      "securityPrivacyAndRisk": {
        "securityRequirements": {
          "status": "unresolved",
          "items": [],
          "reason": "실행 가능한 확장, data source와 authorization model이 이 Work Unit 범위 밖이다."
        },
        "privacyRequirements": {
          "status": "unresolved",
          "items": [],
          "reason": "수집·저장·전송할 사용자 data가 이 Work Unit에서 정의되지 않았다."
        },
        "knownRisks": [
          "미정 컨트롤, 기술 또는 시각 표현을 승인된 제품 결정처럼 오해할 수 있다.",
          "DnD가 Review에서 Done으로의 Human 승인을 자동 처리한다고 오해할 수 있다."
        ],
        "mitigations": [
          "Design Report를 비규범적 검토용 파생물로 표시한다.",
          "Review에서 Done으로의 drop만으로 상태를 변경하지 않는 검토 시나리오를 제공한다."
        ],
        "implementationSecurityModel": null,
        "dataProtectionModel": null
      },
      "observabilityAndOperations": {
        "runtimeObservability": null,
        "deployment": null,
        "operations": null,
        "reason": "실행 가능한 확장과 런타임은 이 Work Unit 범위 밖이다.",
        "reportOnlyFeedback": "검토용 report는 탭 전환, 단계 표시 선택, DnD 결과를 화면 상태 메시지로 보여 준다."
      },
      "verificationStrategy": {
        "testCriteriaRef": "docs/work-units/vscode-extension-ui-structure-draft/data/work-unit.json#/testCriteria",
        "qualityGateRef": "docs/work-units/vscode-extension-ui-structure-draft/data/quality-gate.json",
        "requiredEvidence": [
          "Design Document JSON strict parse 결과",
          "source와 report 구조 대조 결과",
          "탭·단계 표시·DnD 상호작용 검증 결과",
          "HTML/CSS/JavaScript 정적 검사 결과",
          "AI checklist 결과와 Human review 방법"
        ]
      },
      "traceability": [
        {
          "requirementIds": [
            "FR-001",
            "FR-002"
          ],
          "designRefs": [
            "data/sections/ui-structure.json#/tabs",
            "diagram/ui-tab-structure.json"
          ],
          "decisionRefs": [
            "DEC-001"
          ],
          "workUnitRefs": [
            "vscode-extension-ui-structure-draft"
          ],
          "testRefs": [
            "verify-structure:07",
            "verify-browser:03",
            "verify-browser:04"
          ],
          "reviewRefs": [
            "docs/work-units/vscode-extension-ui-structure-draft/data/review.json"
          ]
        },
        {
          "requirementIds": [
            "FR-003",
            "FR-004"
          ],
          "designRefs": [
            "data/sections/ui-structure.json#/stageVisibilityContract",
            "report/index.html#stage-visibility-review"
          ],
          "decisionRefs": [
            "DEC-002"
          ],
          "workUnitRefs": [
            "vscode-extension-ui-structure-draft"
          ],
          "testRefs": [
            "verify-structure:08",
            "verify-browser:05",
            "verify-browser:06"
          ],
          "reviewRefs": [
            "docs/work-units/vscode-extension-ui-structure-draft/data/review.json"
          ]
        },
        {
          "requirementIds": [
            "FR-005",
            "FR-006",
            "FR-007",
            "FR-010",
            "FR-011"
          ],
          "designRefs": [
            "data/sections/ui-structure.json#/normalStages",
            "data/sections/ui-structure.json#/workUnitCardContract",
            "data/sections/ui-structure.json#/scrollContract",
            "data/sections/ui-structure.json#/exceptionStates"
          ],
          "decisionRefs": [
            "DEC-003",
            "DEC-004"
          ],
          "workUnitRefs": [
            "vscode-extension-ui-structure-draft"
          ],
          "testRefs": [
            "verify-structure:09-11,13",
            "verify-browser:07-08,13-14"
          ],
          "reviewRefs": [
            "docs/work-units/vscode-extension-ui-structure-draft/data/review.json"
          ]
        },
        {
          "requirementIds": [
            "FR-008",
            "FR-009"
          ],
          "designRefs": [
            "data/sections/ui-structure.json#/dragAndDropContract",
            "diagram/work-unit-status.json"
          ],
          "decisionRefs": [
            "DEC-004"
          ],
          "workUnitRefs": [
            "vscode-extension-ui-structure-draft"
          ],
          "testRefs": [
            "verify-structure:12",
            "verify-browser:09-12"
          ],
          "reviewRefs": [
            "docs/work-units/vscode-extension-ui-structure-draft/data/review.json"
          ]
        }
      ],
      "aiChecklistRef": "docs/work-units/vscode-extension-ui-structure-draft/data/work-unit.json#/aiChecklist",
      "humanChecklistRef": "docs/work-units/vscode-extension-ui-structure-draft/data/work-unit.json#/humanChecklist",
      "workUnitDecompositionBasis": {
        "status": "not_created",
        "statement": "Human 승인 뒤 구현 범위가 확정되면 이 Design Document를 후속 실행 Work Unit의 basis로 사용할 수 있다."
      },
      "customerDeliverableImpact": "확정된 customer-facing deliverable은 없으며 이 초안은 내부 Human 검토용 Design Report다.",
      "references": [
        "docs/work-units/vscode-extension-ui-structure-draft/data/work-unit.json",
        "docs/work-units/vscode-extension-ui-structure-draft/data/traceability.json",
        "docs/interviews/workunit-kanban-stage-visibility-decision.md",
        ".codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json"
      ],
      "glossary": [
        {
          "term": "TabHeader",
          "meaning": "활성 탭에 대응해 Body와 함께 전환되는 탭별 상단 영역. 상세 내용은 WorkUnit의 단계 표시 선택 외에는 미정이다."
        },
        {
          "term": "Body",
          "meaning": "활성 탭의 본문 영역. WorkUnit에서는 선택한 정상 칸반 단계만 표시한다."
        },
        {
          "term": "Blocked",
          "meaning": "정상 5단계가 아니라 명시적 차단 사유로 진행할 수 없는 예외 상태."
        }
      ],
      "unspecifiedRef": "data/sections/project-core.json#/unresolvedItems"
    }
  },
  "collections": {
    "decisions": {
      "id": "design-decisions",
      "items": [
        {
          "id": "DEC-001",
          "decision": "탭 이름은 Dashboard, Intake, Design, WorkUnit이다.",
          "basis": "docs/work-units/vscode-extension-ui-structure-draft/data/traceability.json#/decisionRefs",
          "rationale": {
            "status": "recorded",
            "text": "Human이 네 탭 이름을 확정했다."
          },
          "alternatives": {
            "status": "not_recorded",
            "items": []
          },
          "tradeoffs": {
            "status": "not_recorded",
            "items": []
          },
          "consequences": [
            "네 탭 각각에 TabHeader와 Body 대응 관계가 필요하다."
          ]
        },
        {
          "id": "DEC-002",
          "decision": "WorkUnit TabHeader에서는 표시할 칸반 단계를 선택하고 Body에는 선택한 단계만 표시한다.",
          "basis": "docs/interviews/workunit-kanban-stage-visibility-decision.md#현재-결정",
          "rationale": {
            "status": "recorded",
            "text": "Human이 단계 선택 방식을 확정했다."
          },
          "alternatives": {
            "status": "recorded",
            "items": [
              "여러 칸반 보드 중 하나를 선택하고 5단계 전체를 표시한다.",
              "칸반 보드 선택과 단계 선택을 모두 제공한다."
            ]
          },
          "tradeoffs": {
            "status": "recorded",
            "items": [
              "선택하지 않은 단계는 Body에서 숨겨진다."
            ]
          },
          "consequences": [
            "Done도 선택하지 않으면 숨길 수 있다.",
            "컨트롤 형식, 선택 cardinality와 기본 표시 단계는 계속 미정이다."
          ]
        },
        {
          "id": "DEC-003",
          "decision": "정상 칸반 흐름은 Backlog, Ready, Working, Review, Done이고 Blocked는 예외 상태다.",
          "basis": ".codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json#/$defs/kanbanStatus",
          "rationale": {
            "status": "recorded",
            "text": "canonical schema의 status meanings와 Human decision이 정상 흐름과 예외 상태를 구분한다."
          },
          "alternatives": {
            "status": "not_recorded",
            "items": []
          },
          "tradeoffs": {
            "status": "not_recorded",
            "items": []
          },
          "consequences": [
            "Blocked를 여섯 번째 정상 칸반 단계처럼 표현하지 않는다."
          ]
        },
        {
          "id": "DEC-004",
          "decision": "카드는 title만 표시하는 고정 높이 카드이고 DnD 성공 시 위치와 status가 함께 변경된다.",
          "basis": "docs/work-units/vscode-extension-ui-structure-draft/data/work-unit.json#/scope",
          "rationale": {
            "status": "recorded",
            "text": "Human이 초기 카드 정보, 높이 mode와 DnD 결과를 확정했다."
          },
          "alternatives": {
            "status": "not_recorded",
            "items": []
          },
          "tradeoffs": {
            "status": "not_recorded",
            "items": []
          },
          "consequences": [
            "정확한 높이 값과 긴 제목 처리는 미정이다.",
            "상태 전이와 Human approval boundary를 우회할 수 없다."
          ]
        }
      ]
    },
    "diagrams": {
      "id": "diagram-metadata",
      "items": [
        {
          "id": "ui-tab-structure",
          "type": "ui-flow",
          "source": "diagram/ui-tab-structure.json"
        },
        {
          "id": "work-unit-status",
          "type": "state",
          "source": "diagram/work-unit-status.json"
        }
      ],
      "rendering": {
        "sourceModel": "structured JSON",
        "renderer": null,
        "exportPath": null,
        "status": "unresolved",
        "reportRepresentation": "JSON source에서 생성하는 Human 검토용 HTML 관계 뷰"
      }
    },
    "snapshots": {
      "id": "pre-execution-baseline",
      "capturedOn": "2026-07-14",
      "adoptionTiming": "new-project",
      "checks": [
        {
          "path": "docs/design-documents/vscode-extension-ui-structure/",
          "result": "not_found",
          "meaning": "실행 전 관련 Design Document가 없었다."
        },
        {
          "path": "docs/design-documents/agent-factory/reference/source/software-design-document-essential-elements.md",
          "result": "not_found",
          "meaning": "조건부 필수 essential-elements reference가 저장소에 없었다."
        }
      ]
    },
    "events": {
      "id": "change-history",
      "events": [
        {
          "date": "2026-07-14",
          "type": "design-document-created",
          "change": "확정된 Human Fact와 Work Unit 범위로 초기 Design Document 초안을 생성했다.",
          "basis": "docs/work-units/vscode-extension-ui-structure-draft/data/work-unit.json"
        }
      ]
    }
  },
  "diagrams": [
    {
      "id": "ui-tab-structure",
      "type": "ui-flow",
      "purpose": "활성 탭의 TabHeader·Body 동시 전환과 WorkUnit 단계 표시 선택 관계를 보여 준다.",
      "audience": "Human reviewer",
      "sourceModel": "structured JSON",
      "renderer": null,
      "nodes": [
        {
          "id": "tabs",
          "label": "Dashboard · Intake · Design · WorkUnit",
          "kind": "tab-set"
        },
        {
          "id": "active-tab",
          "label": "활성 탭",
          "kind": "selection"
        },
        {
          "id": "active-tab-header",
          "label": "활성 탭의 TabHeader",
          "kind": "region"
        },
        {
          "id": "active-tab-body",
          "label": "활성 탭의 Body",
          "kind": "region"
        },
        {
          "id": "workunit-stage-selection",
          "label": "WorkUnit 표시 단계 선택",
          "kind": "selection"
        },
        {
          "id": "selected-stages",
          "label": "선택한 정상 칸반 단계만 표시",
          "kind": "region"
        }
      ],
      "edges": [
        {
          "from": "tabs",
          "to": "active-tab",
          "relation": "selects"
        },
        {
          "from": "active-tab",
          "to": "active-tab-header",
          "relation": "activates-together"
        },
        {
          "from": "active-tab",
          "to": "active-tab-body",
          "relation": "activates-together"
        },
        {
          "from": "active-tab-header",
          "to": "workunit-stage-selection",
          "relation": "contains-when-workunit"
        },
        {
          "from": "workunit-stage-selection",
          "to": "selected-stages",
          "relation": "controls-visibility"
        },
        {
          "from": "selected-stages",
          "to": "active-tab-body",
          "relation": "rendered-in-when-workunit"
        }
      ],
      "unresolved": [
        "단계 선택 컨트롤 형식과 선택 cardinality",
        "기본 표시 단계와 선택 상태 저장 범위",
        "Dashboard, Intake, Design의 TabHeader와 Body 상세 내용",
        "다이어그램 renderer와 export path"
      ],
      "traceability": [
        "FR-001",
        "FR-002",
        "FR-003",
        "FR-004"
      ]
    },
    {
      "id": "work-unit-status",
      "type": "state",
      "purpose": "정상 칸반 단계 사이의 canonical 전이와 Blocked 예외 상태 및 Human 승인 경계를 보여 준다.",
      "audience": "Human reviewer",
      "sourceModel": "structured JSON",
      "renderer": null,
      "normalStates": [
        "backlog",
        "ready",
        "working",
        "review",
        "done"
      ],
      "exceptionStates": [
        "blocked"
      ],
      "transitions": [
        {
          "from": "backlog",
          "to": "ready"
        },
        {
          "from": "backlog",
          "to": "blocked"
        },
        {
          "from": "ready",
          "to": "backlog"
        },
        {
          "from": "ready",
          "to": "working"
        },
        {
          "from": "ready",
          "to": "blocked"
        },
        {
          "from": "working",
          "to": "ready"
        },
        {
          "from": "working",
          "to": "review"
        },
        {
          "from": "working",
          "to": "blocked"
        },
        {
          "from": "review",
          "to": "working"
        },
        {
          "from": "review",
          "to": "done",
          "guard": "Human approval required; card drop alone is insufficient"
        },
        {
          "from": "review",
          "to": "blocked"
        },
        {
          "from": "blocked",
          "to": "backlog"
        },
        {
          "from": "blocked",
          "to": "ready"
        },
        {
          "from": "blocked",
          "to": "working"
        },
        {
          "from": "blocked",
          "to": "review"
        }
      ],
      "terminalStates": [
        "done"
      ],
      "invalidTransitionResult": "Work Unit status와 카드 위치를 변경하지 않는다.",
      "source": ".codex/skills/work-unit-planner-af/assets/schema/work-unit.schema.json#/x-statusTransitions",
      "traceability": [
        "FR-008",
        "FR-009",
        "FR-011"
      ]
    }
  ],
  "workUnitSummary": {
    "id": "vscode-extension-ui-structure-draft",
    "title": "VS Code 확장 UI 구조 초안 작성"
  },
  "workUnitReview": {
    "acceptanceCriteria": [
      "Design Document와 Design Report에 Dashboard, Intake, Design, WorkUnit 탭 이름이 정확히 기록된다.",
      "활성 탭이 바뀌면 그 탭의 TabHeader와 Body가 함께 바뀌는 대응 관계가 명확히 표현된다.",
      "WorkUnit TabHeader에서 표시할 칸반 단계를 선택할 수 있고 Body에는 선택한 단계만 표시되며 선택하지 않은 단계는 표시되지 않는다.",
      "Done을 선택하지 않았을 때 Done 단계가 항상 표시되지 않고 숨겨질 수 있다.",
      "단계 선택 컨트롤 형식, 기본 표시 단계와 선택 상태 저장 범위를 임의로 정하지 않고 미정으로 표시한다.",
      "WorkUnit 탭 Body의 정상 칸반이 Backlog, Ready, Working, Review, Done의 정확한 5단계와 순서로 표현된다.",
      "각 Work Unit이 칸반 카드 형태로 표현되고 카드에 보이는 정보는 title뿐이다.",
      "모든 Work Unit 카드는 고정 높이를 사용하며 정확한 높이 값과 긴 제목 처리 방식은 임의로 확정하지 않는다.",
      "카드를 DnD로 canonical x-statusTransitions가 허용하는 목적 단계에 drop하면 카드가 그 단계로 이동하고 Work Unit status가 목적 단계와 일치하도록 변경된다.",
      "허용되지 않은 단계 전환은 Work Unit status를 변경하지 않으며 Review에서 Done으로의 drop은 Human approval을 자동으로 대신하지 않는다.",
      "각 정상 단계의 확정된 의미가 기록되고 Blocked는 정상 5단계가 아닌 진행 불가 예외 상태로 구분된다.",
      "각 칸반 단계가 세로 스크롤을 가지며 스크롤바 너비 0으로 스크롤바는 보이지 않지만 세로 스크롤 동작은 유지된다.",
      "추후 카드 정보·액션, DnD 세부 동작, Blocked 시각화 방식과 스크롤 세부 동작을 임의로 정하지 않고 미정으로 표시한다.",
      "실행 가능한 VS Code 확장 코드나 미승인 기술·시각 디자인이 생성되지 않는다.",
      "Human이 브라우저에서 Design Report를 열어 구조와 미정 항목을 검토할 수 있다."
    ],
    "definitionOfDone": [
      "관련 Design Document 존재 여부를 실행 전에 확인하고 확인·생성 결과가 review evidence와 canonical report에 기록된다.",
      "Design Document JSON source와 Human-facing Design Report 초안이 Work Unit 범위 안에서 작성된다.",
      "정의된 검증을 수행하고 명령·테스트 증거를 evidence JSON 및 필요한 로그에 기록한다.",
      "AI Review와 AI checklist 결과가 기록되고 범위 이탈 및 잔여 위험이 분리된다.",
      "Human checklist와 검토 방법이 준비되어 Human이 승인, 재작업, 병합, PR 승격 여부를 결정할 수 있다."
    ],
    "testCriteria": [
      "모든 Design Document JSON 파일이 엄격한 JSON으로 파싱된다.",
      "source data와 rendered report 모두 네 탭 이름과 활성 탭의 TabHeader·Body 대응을 포함한다.",
      "source data와 rendered report에서 WorkUnit TabHeader가 표시할 칸반 단계를 선택하고 Body가 선택한 단계만 표시하는 관계를 포함한다.",
      "rendered report에서 Done을 선택하지 않는 검토 시나리오에 Done 단계가 표시되지 않는지 확인한다.",
      "source data와 rendered report의 정상 칸반 단계가 Backlog, Ready, Working, Review, Done의 정확한 순서와 개수로 정의된다.",
      "각 Work Unit 카드의 보이는 정보가 title뿐이고 모든 카드가 고정 높이 요구사항을 가지는지 확인한다.",
      "canonical x-statusTransitions가 허용하는 DnD 시나리오에서 카드가 목적 단계로 이동하고 Work Unit status가 목적 단계와 일치하는지 확인한다.",
      "canonical x-statusTransitions가 허용하지 않는 DnD 시나리오에서 Work Unit status가 변경되지 않는지 확인한다.",
      "Review에서 Done으로의 이동이 Human approval을 자동으로 생성하거나 우회하지 않는지 확인한다.",
      "각 칸반 단계의 세로 스크롤 동작과 너비 0의 보이지 않는 스크롤바 요구사항이 source data와 rendered report에 반영되었는지 확인한다.",
      "Blocked가 정상 칸반의 여섯 번째 단계가 아니라 진행 불가 예외 상태로 분리되었는지 확인한다.",
      "검색 또는 구조 검사를 통해 미승인 카드 정보·높이 값·DnD 세부 동작, 단계 선택 컨트롤 세부 사항, Blocked 시각화 방식, 스크롤 세부 동작과 기술 선택이 추가되지 않았음을 확인한다.",
      "Design Report의 HTML, CSS, JavaScript가 정적 검사에 통과하고 브라우저에서 검토 가능한 상태임을 확인한다."
    ],
    "aiChecklist": [
      "모든 요구사항이 Human Fact 또는 repository evidence에 추적되는지 확인한다.",
      "네 탭과 활성 탭별 TabHeader·Body 쌍이 정확히 표현되었는지 확인한다.",
      "WorkUnit TabHeader가 표시할 칸반 단계를 선택하고 Body가 선택한 단계만 표시하며 선택하지 않은 단계를 숨기는지 확인한다.",
      "Done을 선택하지 않는 검토 시나리오에서 Done 단계가 숨겨지는지 확인한다.",
      "WorkUnit 정상 칸반이 Backlog, Ready, Working, Review, Done 순서의 5단계로 정의되었는지 확인한다.",
      "각 Work Unit 카드에 title만 보이고 모든 카드가 고정 높이 요구사항을 가지는지 확인한다.",
      "허용된 DnD 뒤 카드 위치와 Work Unit status가 목적 단계에 맞게 함께 변경되는지 확인한다.",
      "허용되지 않은 DnD와 Review에서 Done으로의 Human approval boundary가 status 변경으로 우회되지 않는지 확인한다.",
      "Blocked가 정상 단계가 아닌 예외 상태로 분리되고 각 칸반 단계가 세로로 스크롤되며 너비 0의 스크롤바가 보이지 않도록 요구사항이 표현되었는지 확인한다.",
      "카드 높이 값·추후 정보·DnD 세부 동작, 단계 선택 컨트롤 세부 사항, Blocked 시각화 방식, 스크롤 세부 동작 등 미정 요소를 발명하지 않고 unresolved 항목으로 유지했는지 확인한다.",
      "Design Document 확인·작성 결과와 검증 증거가 review 및 report에 기록되었는지 확인한다."
    ],
    "humanChecklist": [
      "네 탭 이름과 활성 탭 전환 시 TabHeader와 Body가 함께 바뀌는 구조를 확인한다.",
      "WorkUnit TabHeader에서 표시할 칸반 단계를 선택할 수 있고 Body에는 선택한 단계만 표시되는지 확인한다.",
      "Done을 선택하지 않았을 때 Done 단계가 숨겨지는지 확인한다.",
      "단계 선택 컨트롤 형식, 기본 표시 단계와 선택 상태 저장 범위가 임의로 확정되지 않았는지 확인한다.",
      "WorkUnit 탭 Body가 Backlog, Ready, Working, Review, Done 순서의 5단계 칸반으로 정의되어 있는지 확인한다.",
      "각 Work Unit 카드에 title만 표시되고 모든 카드가 같은 고정 높이 요구사항을 가지는지 확인한다.",
      "허용된 목적 단계로 카드를 DnD했을 때 카드 위치와 Work Unit status가 함께 변경되는지 확인한다.",
      "허용되지 않은 DnD가 status를 변경하지 않고 Review에서 Done으로의 이동이 Human approval을 자동 처리하지 않는지 확인한다.",
      "각 단계가 세로로 스크롤되고 스크롤바 너비 0으로 스크롤바가 보이지 않는지 확인한다.",
      "Blocked가 정상 단계가 아닌 진행 불가 예외 상태로 구분되는지 확인한다.",
      "카드 높이 값·추후 정보·DnD 세부 동작, Blocked 표시 방식, 스크롤 세부 동작과 탭별 상세 내용 등 미정 항목이 임의로 확정되지 않았는지 확인한다.",
      "Design Report가 이해 가능한 초안인지 검토하고 승인 또는 재작업을 결정한다.",
      "병합 및 PR 승격은 별도의 Human 결정으로 남아 있는지 확인한다."
    ],
    "humanReviewMethod": "브라우저에서 docs/design-documents/vscode-extension-ui-structure/report/index.html을 열고 네 탭과 활성 탭별 TabHeader·Body 전환을 확인한다. WorkUnit TabHeader에서 표시할 칸반 단계를 선택하여 Body에 선택한 단계만 표시되는지 확인하고 Done을 선택하지 않았을 때 Done 단계가 숨겨지는지 검토한다. 각 Work Unit 카드에 title만 보이고 카드 높이가 고정인지 확인한다. canonical x-statusTransitions가 허용하는 목적 단계로 카드를 DnD하여 카드 위치와 Work Unit status가 함께 변경되는지 확인하고, 허용되지 않은 전환과 Review에서 Done으로의 drop이 status 또는 Human approval을 우회하지 않는지 검토한다. 이어서 Backlog·Ready·Working·Review·Done 5단계 정의와 순서, 각 단계의 세로 스크롤과 너비 0의 보이지 않는 스크롤바, Blocked 예외 상태, 미정 항목 목록을 검토한다. data JSON과 report 표현을 대조하고 evidence/commands.json, evidence/tests.json 및 canonical data/report.json의 검증 결과를 확인한 뒤 승인 또는 재작업을 결정한다. 병합과 PR 승격은 Human이 별도로 결정한다."
  },
  "projectionCoverage": {
    "projectCore": "sections/project-core",
    "requirements": "sections/requirements",
    "uiStructure": "sections/ui-structure",
    "governance": "sections/governance-and-verification",
    "decisions": "collections/decisions",
    "diagramMetadata": "collections/diagrams",
    "baseline": "collections/snapshots",
    "changeHistory": "collections/events",
    "diagrams": "diagrams",
    "workUnitReview": "workUnitReview"
  }
});
