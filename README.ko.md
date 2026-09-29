# Agent Factory for Codex

[English](README.md) | 한국어

사용자에게는 사용자가 사용하는 언어 또는 명시적으로 선택한 언어로 응답합니다.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Agent Factory는 사용자가 주도하는 소프트웨어 개발·전달을 위한 Codex 플러그인입니다.
범위가 명확한 에이전트 작업 흐름, 근거 탐색, 공통 프로젝트 규칙을 제공합니다.

## 핵심 기능

### 1. 문서 시스템

- 원본 출처, 조사·분석, 합의된 명세, 작업 진행 기록, 교훈을 구분하여 관리합니다.
- 문서별 편집 정본을 하나로 유지하고, 근거·가정·사용자가 확정한 결정을 구분합니다.
- 문서 마이그레이션을 요청하면 기존 내용과 참조를 보존하며 프로젝트 구조에 맞게 정리합니다.
- 합의된 명세는 프로젝트 스킬로 동기화하여 이후 작업에서 활용할 수 있습니다.
  문서를 작성하거나 요약한 사실만으로 프로젝트 규칙이 되지는 않습니다.

### 2. 계약 → 작업·검증 루프

- 대화에서 목표, 개별 작업, 완료 기준을 도출하고 파일 변경이 필요한 경우 경로와 작업 종류를 계약에 명시합니다.
- 작업별 범위와 결과를 연결하며, 범위 변경을 확정하면 이전 버전을 보존하고 계약을 갱신합니다.
- Main은 요청과 실행을 조율하고, Work는 구현과 자체 검사를 수행하며, Verification은 결과를 독립적으로 확인합니다.
- 검증에서 발견한 문제는 Work로 돌아가 수정한 뒤 다시 검증합니다. 해결되지 않은 문제는 결과에 남깁니다.
- 일반 메시지는 Main이 직접 처리할 수 있으며, 별도 검증은 선택한 실행 방식에 따라 수행합니다.

### 3. 인터뷰

- 기존 대화와 자료로 해결할 수 없는 중요한 요구사항이나 결정을 질문으로 구체화합니다.
- 한 번에 하나의 결정을 다루고, 선택지별 장단점과 권고를 제시합니다. 답변에 따라 다음 질문을 조정합니다.
- 사용자는 질문을 건너뛰거나 보류하고, 내용을 수정하거나 범위를 좁힐 수 있습니다.
- 인터뷰를 마치면 결정과 미해결 사항을 요약합니다. 요청하거나 작업 흐름에서 필요할 때 문서로 보존하여 계약과 계획에 활용합니다.

### 4. 교훈

- 복구된 실패를 포함한 오류와 사용자·에이전트의 판단 차이를 기록합니다. 당시 상황, 원인, 시도한 해결책과 결과를 함께 남깁니다.
- 관련 작업 전에 기존 교훈을 조회하고, 적용 결과와 재발 여부를 기록합니다. 불명확한 원인과 미해결 문제는 명확히 구분합니다.
- 같은 문제가 다시 발생하면 이전 기록을 지우지 않고 근거를 추가합니다.
- 사용자가 통합을 요청하면 근거가 충분한 교훈을 프로젝트 규칙에 반영합니다. 교훈 기록만으로 명세가 되거나 백그라운드 변경이 시작되지는 않습니다.

## VS Code 확장

- 이 플러그인은 단독으로 설치하고 사용할 수 있으며, VS Code 확장은 선택 사항입니다.
- Agent Factory VS Code 확장을 사용하려면 동일한 시맨틱 기본 버전의 플러그인이
  설치되고 활성화되어 있어야 합니다. 예를 들어 확장 `1.0.17`은
  플러그인 `1.0.17+codex.<token>`을 허용합니다.

- 확장은 활성화 시 플러그인의 설치·활성화 상태와 버전을 확인하고, 필요한 경우 자동 설치를 시도합니다.
  호환되는 플러그인이 이미 활성화되어 있으면 추가 설치 없이 사용합니다.
  설치 후에도 호환 상태를 확인할 수 없으면 확장 활성화를 중단하고 오류를 안내합니다.
- 직접 설치하거나 업데이트하려면 아래 [수동 설치](#수동-설치)를 참고하십시오.

## 독립 구성 요소

- **익스텐션 + 플러그인:** MCP 없이 로컬 작업 흐름을 제공합니다. 플러그인은 익스텐션 없이도 사용할 수 있습니다.
- **MCP:** 별도로 설치·운영하는 서비스이며 로컬 플러그인의 필수 의존성이 아닙니다.

## 스킬

플러그인은 네 가지 공개 스킬을 제공합니다.

- [Agent](skills/agent/SKILL.md): Work·Verification 에이전트에 작업을 위임하고,
  세션과 실행 진행 상황 및 결과를 관리합니다.
- [Convention](skills/convention/SKILL.md): 소통, 사용자 의사결정, 개발, 테스트,
  조사와 인터뷰에 적용하는 공통 규칙을 제공합니다.
- [Document](skills/document/SKILL.md): 프로젝트 문서의 작성·분류·저장·검색을 안내하고,
  프로젝트 명세 문서를 Codex 스킬로 동기화합니다.
- [Tool](skills/tool/SKILL.md): 플러그인 스크립트 목록과 각 스크립트의 규칙을 담당하는 스킬을 안내합니다.

### 에이전트 실행 방식

- Main은 사용자와 대화하며, 일반 메시지의 작업은 기본적으로 직접 수행합니다.
- 메시지별로 Work(작업 위임), Plan(계획만 작성), Verification(기존 작업 검증)을 선택할 수 있습니다.
  Plan·Work, Work·Verification, Plan·Work·Verification으로 계획·작업·검증을 조합할 수도 있습니다.
- 선택한 실행 방식은 해당 메시지에만 적용됩니다. 자세한 절차는
  [실행 방식 안내](skills/agent/references/execution-modes.md)를 참고하십시오.
- 조사와 인터뷰를 통해 근거를 찾거나 요구사항을 구체화할 수 있습니다.

### 모델과 세션

- 에이전트를 Claude Code로도 실행할 수 있습니다. `claude-opus-5-5`, `claude-sonnet-5`,
  `claude-fable-5-1`, `claude-haiku-4-5-20251001` 같은 `claude-*` 모델이나 `claude-opus`,
  `claude-sonnet`, `claude-haiku` 별칭을 선택하십시오.
- 모든 실행 방식을 Claude로 사용할 수 있습니다. Plan은 Claude의 plan 모드로 계획한 뒤 같은 세션에서 실행합니다.
  실행 권한은 가장 가까운 Claude 권한 모드로 연결되며 OS 샌드박스가 아닙니다.
  자세한 내용은 [실행 방식 안내](skills/agent/references/execution-modes.md#7-execution-providers)를 참고하십시오.
- Antigravity CLI(`agy`)로 Google AI 구독 모델을 사용해 에이전트를 실행할 수도 있습니다. `gemini-*` 모델은
  Antigravity를 선택하며, 그 밖의 모델은 `antigravity/<id>` 형식으로 지정합니다. Antigravity 실행은 텍스트만 지원합니다.
  자세한 내용은 [Antigravity](skills/agent/references/execution-modes.md#71-antigravity)를 참고하십시오.
- 이 패키지는 Codex로 설치하며, Claude와 Antigravity 실행은 런타임이 시작합니다.
  Claude Code에서는 별도의 [Claude Code 배포판](https://github.com/KoreanLeeChangHyun/agent-factory-claude-plugin)을 설치하십시오.

## 수동 설치

- 실행 도구의 공식 설치 안내: [Codex CLI](https://developers.openai.com/codex/cli/) · [Claude Code](https://code.claude.com/docs/en/setup).

- Agent Factory VS Code 확장을 사용하면 기본적으로 플러그인이 자동 설치됩니다.
- 플러그인을 단독으로 사용하거나 수동으로 설치하려면 다음 명령을 실행합니다.

  ```bash
  codex plugin marketplace add KoreanLeeChangHyun/agent-factory-codex-plugin --ref main
  codex plugin add agent-factory@agent-factory
  ```

- 게시된 업데이트를 설치하려면 다음 명령을 실행합니다.

  ```bash
  codex plugin marketplace upgrade agent-factory
  codex plugin add agent-factory@agent-factory
  ```

- 설치 또는 업데이트 후에는 스킬과 도구를 불러올 수 있도록 새 Codex 스레드를 시작합니다.

## 문서 동기화

- Agent Factory 규칙에 따라 `docs/skills/`에 작성한 프로젝트 명세 문서는
  `.codex/skills/`와 `.claude/skills/`로 동기화되어 Codex와 Claude Code에서 프로젝트 스킬로 활용됩니다.
- 에이전트는 `docs/skills/`에 프로젝트 명세 문서를 작성한 후
  [Document 스킬의 동기화 스크립트](skills/document/references/host-sync.md#continuous-codex-synchronization)를
  실행하고 결과를 확인합니다. 문서를 수정하거나 삭제한 후에도 실행합니다.
- 동기화된 문서를 별도로 편집한 경우 충돌을 보고하고 동기화를 중단하여 변경 내용을 보호합니다.
- 동기화 관리 대상이 아닌 기존 스킬은 수정하지 않고 보존합니다.
  사용자가 문서 마이그레이션을 명시적으로 요청한 경우에만, 요청한 범위 안에서
  Agent Factory 규칙에 따라 마이그레이션할 수 있습니다.

## 호환성

- **운영체제:** Linux, macOS, 네이티브 Windows 실행을 지원하며, WSL에서는 Linux 요구사항을 충족해야 합니다.
  Windows에서는 Git Bash 등에서 네이티브 Python(python.org 또는 Microsoft Store)을 사용하십시오.
  MSYS2/Cygwin용 Python은 지원하지 않습니다. macOS와 Windows는 실제 사용 환경에서 동작 확인이 필요합니다.
- **Python:** Python 3.10+.
- **Codex:** Codex CLI가 설치되어 있어야 합니다. 실행 전에 필요한 기능과 환경을 확인합니다.
- 환경별 조건과 제한은 [호스트 준비 상태 안내](skills/agent/references/installation.md#host-readiness-and-diagnostics)를 참고하십시오.

## 버그 문의

버그는 [m.leechanghyun@gmail.com](mailto:m.leechanghyun@gmail.com)으로 문의해 주세요.

## 라이선스

MIT 라이선스입니다. [LICENSE](LICENSE)를 참고하십시오.
