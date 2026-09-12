# Codex용 Agent Factory

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Agent Factory는 사람이 지시하는 소프트웨어 전달을 위한 Codex 플러그인입니다.
범위가 한정된 Agent 워크플로, 근거 탐색 및 공통 프로젝트 규칙을 제공합니다.

## 제품 모드

- **플러그인 전용:** 완전한 로컬 워크플로입니다. Agent Factory MCP 패키지,
  서버, 계정, 테넌트, 연결 또는 인증된 리소스가 필요하지 않습니다.
- **MCP 전용:** 독립적으로 설치된 MCP 애플리케이션이 이 플러그인 없이 자체
  Document, Gather, Tool 및 Workspace 기능을 소유합니다.
- **플러그인과 MCP:** 명시적으로 선택되고 승인된 연결 기능으로 로컬 워크플로를
  확장할 수 있습니다. 이러한 기능은 그래프 권한을 넘겨받거나 로컬 아티팩트를
  암묵적으로 전송하지 않습니다.

## 포함된 Skill 및 Agent 모델

이 플러그인은 정확히 두 개의 공개 Skill을 제공합니다.

- `agent`는 관리형 세션을 통해 `Main -> Work -> Verification` 그래프를 실행합니다.
- `convention`은 핵심 모델과 공통 프로젝트 규칙을 소유합니다.

Main은 사람과 소통하고, 범위가 한정된 작업을 위임하며, 결과를 통합합니다.
Work는 작업을 수행합니다. Verification은 완료된 Work를 독립적으로 확인하고,
사람이 명시적으로 생략하지 않는 한 pass 또는 fail을 반환합니다. 근거 탐색은
Work 기능이고 Interview는 Main 기능이며, 어느 쪽도 Skill이나 역할을 추가하지 않습니다.

Codex CLI가 기본 인터페이스입니다. 동일한 그래프를 `codex exec`로 호스팅하거나
VS Code 확장 프로그램을 통해 표시할 수도 있습니다.

## 설치

GitHub 기반 marketplace를 추가하고 플러그인을 설치합니다.

```bash
codex plugin marketplace add KoreanLeeChangHyun/agent-factory-codex-plugin --ref main
codex plugin add agent-factory@agent-factory
```

게시된 업데이트를 설치하려면 다음을 실행합니다.

```bash
codex plugin marketplace upgrade agent-factory
codex plugin add agent-factory@agent-factory
```

설치 또는 업데이트 후 새 Codex thread를 시작하여 Skill과 도구를 로드하십시오.
플러그인 manifest는 `.codex-plugin/plugin.json`이며 두 배포 Skill은 `skills/` 아래에
있습니다. 저장소 로컬 `.codex/`에는 미러링되지 않습니다.

## 호환성

- **운영체제:** 관리형 실행은 Linux를 지원합니다. WSL은 Linux 검사를 충족해야
  하며 macOS와 네이티브 Windows는 지원하지 않습니다.
- **Python:** 소스 수준 최저 버전은 Python 3.10입니다. 릴리스 검증은 구성된
  Python 3.10 및 3.12 기준을 다룹니다.
- **Codex:** 저장소 전체에 적용되는 CLI 버전을 전제하지 않습니다. 런타임 사전
  검사와 설치된 기능 검색으로 선택한 실행 파일의 준비 상태를 판단합니다.
- **격리:** cgroup v2를 사용하는 사용자 systemd가 권장됩니다. 비공개 프로세스
  그룹 fallback은 하위 프로세스 격리 수준이 더 낮습니다.

이는 호환성 경계이며 특정 호스트, 계정, 모델, tier 또는 sandbox의 준비 상태를
입증하지 않습니다.

## 상세 문서

지속되는 계약은 소유 Skill 및 reference에 유지됩니다.

- [Agent Skill](skills/agent/SKILL.md): 그래프 역할, 위임 및 실행.
- [Convention Skill](skills/convention/SKILL.md): 공통 규칙 및 소유권.
- [핵심 모델](skills/convention/references/agent-factory-core.md): 역할, 기능, 권한 및 제품 경계.
- [런타임 계약](skills/agent/references/home-runtime.md): 관리형 세션, 경로, receipt,
  복구, 격리 및 migration.
- [디렉터리 구조](skills/convention/references/directory-structure.md): 소스, 설치,
  런타임, cloud 및 legacy 레이아웃.
- [Document](skills/convention/references/documents.md): Document 유형, routing,
  형식, projection 및 synchronization.
- [개발](skills/convention/references/development.md): 변경, Git publication,
  기술 문서 및 릴리스 준비.
- [테스트](skills/convention/references/testing.md): 테스트 구성 및 검증 경계.
- [Native Fast 및 Goal](skills/agent/references/native-fast-goal.md)과
  [프로젝트 전문 Work](skills/agent/references/project-specialist.md): 선택적 실행 지침 및 전문화 설계.

## 상태

피드백과 이슈 보고를 환영합니다.

## 라이선스

MIT License입니다. [LICENSE](LICENSE)를 참조하십시오.
