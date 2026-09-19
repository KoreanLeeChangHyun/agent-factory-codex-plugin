# Agent Factory for Codex

[English](README.md) | 한국어

사용자에게는 사용자가 사용하는 언어 또는 명시적으로 선택한 언어로 응답합니다.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Agent Factory는 사용자가 주도하는 소프트웨어 개발·전달을 위한 Codex 플러그인입니다.
범위가 명확한 에이전트 작업 흐름, 근거 탐색, 공통 프로젝트 규칙을 제공합니다.

## VS Code 확장

- 이 플러그인은 단독으로 설치하고 사용할 수 있으며, VS Code 확장은 선택 사항입니다.
- Agent Factory VS Code 확장을 사용하려면 동일한 시맨틱 기본 버전의 플러그인이
  설치되고 활성화되어 있어야 합니다. 예를 들어 확장 `1.0.11`은
  플러그인 `1.0.11+codex.<token>`을 허용합니다.

- 확장은 활성화 시 플러그인의 설치·활성화 상태와 버전을 확인하고, 필요한 경우 자동 설치를 시도합니다.
  호환되는 플러그인이 이미 활성화되어 있으면 추가 설치 없이 사용합니다.
  설치 후에도 호환 상태를 확인할 수 없으면 확장 활성화를 중단하고 오류를 안내합니다.
- 직접 설치하거나 업데이트하려면 아래 [수동 설치](#수동-설치)를 참고하십시오.

## 스킬

플러그인은 세 가지 공개 스킬을 제공합니다.

- [Agent](skills/agent/SKILL.md): Work·Verification 에이전트에 작업을 위임하고,
  세션과 실행 진행 상황 및 결과를 관리합니다.
- [Convention](skills/convention/SKILL.md): 소통, 사용자 의사결정, 개발, 테스트,
  조사와 인터뷰에 적용하는 공통 규칙을 제공합니다.
- [Document](skills/document/SKILL.md): 프로젝트 문서의 작성·분류·저장·검색을 안내하고,
  프로젝트 명세 문서를 Codex 스킬로 동기화합니다.

### 에이전트 실행 방식

- Main은 사용자와 대화하며, 일반 메시지의 작업은 기본적으로 직접 수행합니다.
- 메시지별로 Work(작업 위임), Plan(계획만 작성), Verification(기존 작업 검증)을 선택할 수 있습니다.
  Plan·Work, Work·Verification, Plan·Work·Verification으로 계획·작업·검증을 조합할 수도 있습니다.
- 선택한 실행 방식은 해당 메시지에만 적용됩니다. 자세한 절차는
  [실행 방식 안내](skills/agent/references/execution-modes.md)를 참고하십시오.
- 조사와 인터뷰를 통해 근거를 찾거나 요구사항을 구체화할 수 있습니다.

## 수동 설치

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
  `.codex/skills/`로 동기화되어 Codex에서 프로젝트 스킬로 활용됩니다.
- 에이전트는 `docs/skills/`에 프로젝트 명세 문서를 작성한 후
  [Document 스킬의 동기화 스크립트](skills/document/SKILL.md#continuous-codex-synchronization)를
  실행하고 결과를 확인합니다. 문서를 수정하거나 삭제한 후에도 실행합니다.
- 동기화된 문서를 별도로 편집한 경우 충돌을 보고하고 동기화를 중단하여 변경 내용을 보호합니다.
- 동기화 관리 대상이 아닌 기존 스킬은 수정하지 않고 보존합니다.
  사용자가 문서 마이그레이션을 명시적으로 요청한 경우에만, 요청한 범위 안에서
  Agent Factory 규칙에 따라 마이그레이션할 수 있습니다.

## 호환성

- **운영체제:** Linux와 macOS 실행을 지원하며, WSL에서는 Linux 요구사항을 충족해야 합니다.
  네이티브 Windows는 지원하지 않습니다. macOS는 실제 사용 환경에서 동작 확인이 필요합니다.
- **Python:** Python 3.10+.
- **Codex:** Codex CLI가 설치되어 있어야 합니다. 실행 전에 필요한 기능과 환경을 확인합니다.
- 환경별 조건과 제한은 [호스트 준비 상태 안내](skills/agent/references/home-runtime.md#host-readiness-and-diagnostics)를 참고하십시오.

## 버그 문의

버그는 [m.leechanghyun@gmail.com](mailto:m.leechanghyun@gmail.com)으로 문의해 주세요.

## 라이선스

MIT 라이선스입니다. [LICENSE](LICENSE)를 참고하십시오.
