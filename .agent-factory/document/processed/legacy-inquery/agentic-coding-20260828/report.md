# 에이전틱 코딩 공개 웹 자료 종합 조사

> 상태: AI가 작성한 비정제 Inquiry 작업물. 조사 기준일 2026-08-28 (Asia/Seoul), 공개 웹 원문 기준. 제품 기능·가격·모델·순위는 계속 바뀐다. “웹의 모든 자료”를 완전 열거할 수 없으므로, 핵심 1차 자료와 대표적인 반증·비판 자료가 검색 포화에 이를 때까지 범주별로 조사했다.

## 한눈에 보는 요약

**관찰된 사실.** 에이전틱 코딩은 단순히 다음 코드 조각을 제안하는 자동완성이 아니라, 모델이 목표를 받아 저장소와 실행 환경을 탐색하고, 계획을 조정하며, 파일·셸·테스트·브라우저·외부 서비스 같은 도구를 반복 호출해 검증 가능한 변경을 만드는 방식이다. Anthropic은 미리 정해진 코드 경로를 따르는 *workflow*와 모델이 자신의 과정·도구 사용을 동적으로 지휘하는 *agent*를 구별한다. 코딩은 테스트라는 환경 피드백이 있어 에이전트에 특히 적합하지만, 테스트 통과가 요구사항·보안·유지보수성을 보장하지 않으므로 사람의 리뷰가 여전히 필요하다고 명시한다 ([Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)).

**분석.** “자율성”은 제품 이름이 아니라 연속축이다. (1) 인라인 완성, (2) 대화형 다중 파일 편집, (3) 로컬 터미널에서 사람이 승인하는 실행, (4) 격리된 클라우드에서 비동기 PR 생성, (5) 장시간·멀티에이전트 운영으로 갈수록 행동 반경과 검증 부담이 함께 커진다. 같은 모델도 harness(프롬프트, ACI, 도구, 컨텍스트, 예산, 샌드박스)에 따라 성능과 위험이 크게 달라진다. SWE-agent 연구도 모델뿐 아니라 agent-computer interface가 성능을 크게 좌우한다고 보였다 ([paper](https://arxiv.org/abs/2405.15793)).

**강한 결론.** 현재 가장 재현성 높은 운영 원리는 작고 명확한 작업, 저장소 안의 지속 지침, 최소 권한·격리 환경, 자동화된 테스트/정적 분석, 작은 diff, 독립 리뷰, 추적 가능한 로그, Git 기반 롤백이다. 에이전트의 “완료” 선언이나 공개 리더보드 점수를 배포 승인으로 사용하면 안 된다.

**혼재된 결론.** 생산성은 과업과 사용자에 따라 방향까지 달라진다. 제한된 신규 HTTP 과제에서는 Copilot 사용자가 55.8% 빨랐지만 ([Microsoft Research](https://www.microsoft.com/en-us/research/publication/the-impact-of-ai-on-developer-productivity-evidence-from-github-copilot/)), 자기 저장소에 매우 익숙한 숙련 오픈소스 개발자 16명의 246개 실제 과제를 무작위 배정한 연구에서는 2025년 초 도구가 완료 시간을 19% 늘렸다 ([METR paper](https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf)). 두 결과는 모순이라기보다 과업·도구 세대·전문성·검토비용이 다른 외적 타당성의 경고다.

**아직 모르는 것.** 장기 유지보수 비용, 장애·보안 사건률, 팀 학습과 주니어 역량, 여러 에이전트의 실제 순생산성, 사설 대형 저장소에서의 일반화, 모델/도구 업데이트에 따른 효과 지속성에 대한 독립적 장기 연구가 부족하다.

## 1. 정의와 경계

### 작업 정의

이 조사에서 **에이전틱 코딩(agentic coding)** 은 다음 다섯 조건 중 적어도 3–5번을 포함하는 AI 보조 소프트웨어 개발로 정의한다.

1. 사람이 목표·제약·완료 조건을 자연어 또는 이슈/스펙으로 준다.
2. 모델이 저장소·문서·오류·과거 상태에서 필요한 컨텍스트를 선택한다.
3. 모델이 다음 행동(검색, 읽기, 편집, 명령 실행, 테스트, 외부 도구 호출)을 동적으로 고른다.
4. 행동 결과를 관찰하고 계획·패치를 반복 수정한다.
5. 변경, 테스트 증거, diff/PR, 로그 같은 검토 가능한 산출물을 내고 사람 또는 정책 게이트에 넘긴다.

ReAct는 reasoning과 environment action을 교차시키는 일반 토대를 제시했고 ([ICLR paper](https://arxiv.org/abs/2210.03629)), Reflexion은 실패 피드백을 언어적 메모리로 다음 시도에 반영했다 ([NeurIPS paper](https://arxiv.org/abs/2303.11366)). CodeAct는 고정 JSON 도구 호출 대신 실행 가능한 코드 행동을 제안했다 ([paper](https://arxiv.org/abs/2402.01030)). 이 연구 흐름이 실제 코딩 harness의 탐색–행동–관찰–수정 루프와 연결된다.

### 무엇과 다른가

| 형태 | 주 제어자 | 행동 범위 | 피드백 루프 | 전형적 산출물 |
|---|---|---|---|---|
| 코드 자동완성 | 사람 | 커서 주변 텍스트 | 거의 없음 | 한 줄/함수 제안 |
| AI pair programming | 사람과 모델 | 채팅, 선택 영역, 몇 파일 | 사람이 대화로 반복 | 코드 조각·설명·diff |
| 에이전틱 코딩 | 모델이 다음 단계를 동적 선택, 사람이 경계 설정 | 저장소, 파일, 터미널, 테스트, 웹/API | 실행 결과를 스스로 관찰·수정 | 검증된 다중 파일 변경/PR |
| 고정 자동화/워크플로 | 미리 작성된 프로그램 | 정의된 단계 | 고정 분기 | 빌드·배포·정형 결과 |
| 완전 자율 개발 | 모델/에이전트 팀 | 설계부터 운영까지 장시간 | 광범위·지속적 | 제품/서비스 전체; 아직 제한적·고위험 |

“vibe coding”은 결과 코드를 충분히 이해하지 않은 채 자연어와 실행 결과 위주로 만드는 사용자 행태를 가리키는 경우가 많아, agentic coding과 겹치지만 동의어는 아니다. 전문 개발자가 엄격한 테스트·리뷰 아래 에이전트를 쓰는 것도 agentic coding이며 vibe coding일 필요는 없다.

### 연대표

| 시기 | 관찰된 이정표 | 의미 |
|---|---|---|
| 2021-06 | GitHub Copilot 기술 프리뷰; OpenAI Codex 기반 “AI pair programmer” ([GitHub](https://github.blog/news-insights/product-news/introducing-github-copilot-ai-pair-programmer/)) | 자동완성 중심 대중화 |
| 2022–2023 | ReAct, Reflexion; 2023년 SWE-bench 공개 ([paper](https://arxiv.org/abs/2310.06770)) | 도구 행동 루프와 실제 GitHub 이슈 평가 |
| 2024 | SWE-agent/CodeAct/OpenHands 연구; Devin 공개; SWE-bench Verified; MCP 공개 | 저장소·터미널 ACI, 자율 실행, 도구 상호운용 |
| 2025 | Claude Code, Codex, Copilot coding agent, Cursor background agents, Gemini CLI 등 확산; SWE-Lancer·Terminal-Bench·SWE-bench Live/Pro | 로컬/클라우드 비동기 PR, 더 현실적인 평가와 오염 대응 |
| 2026-08 기준 | 병렬·장기·스킬 기반 에이전트, GitHub agentic workflows, 강화된 격리/감사; 동시에 공개 벤치마크 신호 저하 논쟁 | 모델 단독 경쟁에서 orchestration·governance 경쟁으로 이동 |

MCP는 2024-11-25 Anthropic이 공개한 도구·데이터 연결 표준이다 ([announcement](https://www.anthropic.com/news/model-context-protocol)). `AGENTS.md`는 저장소별 빌드·테스트·규칙을 여러 코딩 에이전트에 전달하는 단순 Markdown 관례다 ([agents.md](https://agents.md/)). 둘은 각각 “무엇에 연결할지”와 “이 저장소에서 어떻게 일할지”를 표준화하지만, 권한 안전성이나 결과 정확성을 자동 보증하지 않는다.

## 2. 전형적 시스템 구조와 실행 루프

```text
사람/이슈/스펙
   ↓ 목표·제약·승인 정책
오케스트레이터/하니스 ── 저장소 지침·스킬·메모리
   ↓                         ↑ 요약/상태
모델(계획·다음 행동 선택) ↔ 컨텍스트 관리자/코드 검색
   ↓ tool call
ACI: 파일·patch·git·terminal·IDE·browser·MCP/API
   ↓ 격리 환경의 관찰
빌드·테스트·lint·type/security scan·실행 로그
   ↺ 실패 분석 및 수정
   ↓
diff/commit/PR + 증거 + 사람/정책 리뷰 → CI → 제한적 merge/deploy
```

### 구성요소

- **모델:** 코드·자연어 추론과 도구 선택을 담당한다. 모델 이름만으로 제품 성능을 설명할 수 없고, reasoning budget, sampling, context, harness가 함께 고정돼야 비교 가능하다.
- **계획/오케스트레이션:** 짧은 과제에는 암묵적 todo면 충분할 수 있다. 긴 과제는 명시적 계획, 체크포인트, 서브태스크 의존성, 중단 조건이 필요하다. 복잡성을 추가하면 latency·cost·오류 전파도 늘어난다 ([Anthropic patterns](https://www.anthropic.com/engineering/building-effective-agents)).
- **코드 탐색:** 파일 트리, 텍스트/심볼 검색, LSP, repo map, 임베딩 검색을 조합한다. 전체 저장소를 컨텍스트에 넣기보다 질문에 맞는 증거를 점진적으로 로드하는 편이 일반적이다.
- **컨텍스트/메모리:** 현재 대화, 선택 파일, `AGENTS.md`/`CLAUDE.md`/rules, 테스트 출력, 압축 요약, 세션/프로젝트 메모리로 나뉜다. 요약은 정보 손실, 자동 메모리는 오염·낡은 규칙 위험이 있다.
- **ACI와 도구:** 읽기/편집/patch, shell, git, test, browser, issue tracker, CI/CD, cloud가 핵심이다. SWE-agent는 에이전트용 인터페이스 설계 자체가 중요한 성능 변수임을 실험했다 ([paper](https://arxiv.org/abs/2405.15793)).
- **검증 루프:** 빠른 관련 테스트 → 정적 검사 → 넓은 테스트 → 보안/의존성 검사 순으로 비용을 단계화한다. 숨은 요구사항과 비기능 품질은 사람·별도 evaluator가 본다.
- **Human-in-the-loop:** 계획 승인, 위험 명령 승인, diff 리뷰, merge/deploy 결정 등 위험에 비례해 배치한다. 승인 피로 때문에 모든 셸 호출을 묻는 것도 안전하지 않으므로 deny-by-default와 위험 기반 정책을 결합한다.
- **멀티에이전트:** 병렬 탐색·구현·리뷰에 유리하지만 중복 작업, 충돌, 공통 오판, 비용, 공유 상태 오염이 생긴다. Anthropic의 2026 C compiler 사례는 16개 에이전트/약 2,000 세션/약 $20,000라는 유용한 stress test이나 한 공급자의 사례이며 일반 생산성 증명은 아니다 ([case study](https://www.anthropic.com/engineering/building-c-compiler)).
- **샌드박스·권한:** 프로세스/VM 격리, 네트워크 egress, mount, token scope, secret broker, allowlisted tools, 승인, audit가 모델 외부의 핵심 통제다. OpenAI의 내부 운영은 경계·고위험 승인·agent-native telemetry를 강조한다 ([Running Codex safely](https://openai.com/index/running-codex-safely/)).

### 정상 종료 조건

에이전트의 자연어 “완료”가 아니라 (a) 수용 기준과 대응 테스트, (b) 허용된 변경 범위, (c) 깨끗한 diff와 금지 파일 무변경, (d) 보안/라이선스/CI 게이트, (e) 사람이 이해 가능한 설명을 기계적으로 확인해야 한다. 시간·토큰·비용·반복 횟수 상한과 “같은 실패 N회면 중단”도 필요하다.

## 3. 주요 제품·도구·오픈소스 프로젝트

기능은 **2026-08-28 스냅샷**이며 “주요”는 대표성·공식 근거·서로 다른 배포 형태를 기준으로 선별했다. 가격은 급변하므로 비교하지 않았다.

| 도구 | 형태/공식 근거 | 핵심 기능 | 공개 라이선스 | 주요 한계·주의 |
|---|---|---|---|---|
| OpenAI Codex | 앱·IDE·CLI·클라우드 ([official](https://openai.com/codex/), [CLI repo](https://github.com/openai/codex)) | 저장소 읽기/편집/명령, 클라우드 과제, 병렬 worktree/agent, skills | CLI Apache-2.0; 서비스 독점 | 모델·서비스 의존, 비용/권한/데이터 정책 확인; 마케팅 사례는 독립 근거 아님 |
| Anthropic Claude Code | 로컬 CLI·IDE·SDK ([docs](https://docs.anthropic.com/en/docs/claude-code/getting-started)) | 파일/셸, MCP, subagent, hooks/skills, 세션 resume, permission mode | 클라이언트 전체를 일반 OSS로 간주하면 안 됨; 상용 서비스 | 로컬 셸/네트워크의 큰 blast radius; `--dangerously-skip-permissions` 고위험 |
| GitHub Copilot cloud/coding agent | IDE·CLI·GitHub 비동기 PR ([concepts](https://docs.github.com/en/copilot/concepts)) | 이슈 위임, PR 반복, agentic workflows, code review, third-party agents | 상용 | Actions/AI credit 비용, GitHub 권한; preview 기능 변동; 테스트 통과 후 리뷰 필요 |
| Cursor Agent/Cloud Agents | VS Code 계열 IDE·CLI·원격 VM/API ([overview](https://cursor.com/docs/agent/overview), [background](https://docs.cursor.com/background-agent)) | 코드 검색/편집/터미널, background branch/PR, 최대 다중 실행 | 상용 | 원격 에이전트 자동 명령+인터넷은 prompt injection/유출 위험; 며칠 데이터 보관 필요 |
| Windsurf Cascade | IDE/플러그인 ([docs](https://docs.windsurf.com/windsurf/cascade/cascade)) | Code/Chat, tool call, 계획, rules/memory, checkpoint/revert, MCP | 상용 | 공급자 문서/모델/크레딧 변동; 자동 메모리·도구 권한 검토 |
| Devin | 원격 자율 SWE workspace/API ([docs](https://docs.devin.ai/get-started/devin-intro)) | 계획, 브라우저/셸/editor, Jira/Linear 과제, 세션/knowledge/playbook | 상용 | “3시간이면 대체로 가능”은 공급자 경험칙; 실제 저장소별 검증 필요 |
| Replit Agent | 호스팅 IDE/배포 플랫폼 ([docs](https://docs.replit.com/learn/build-with-agent)) | 자연어 앱 구축, plan, browser test, optimization, checkpoint | 상용 | 호스팅 생태계 결합, 모드별 비용 급증 가능; production 보안/아키텍처 리뷰 필요 |
| AWS Kiro / Amazon Q Developer | agentic IDE·CLI, AWS 통합 ([AWS transition](https://aws.amazon.com/blogs/devops/amazon-q-developer-end-of-support-announcement/)) | spec-driven requirements→design→tasks, steering, hooks, subagents, MCP | 상용 | Q IDE plugin 신규 가입 종료/2027-04 지원 종료 예정; Kiro 이전 경로 확인 |
| Google Antigravity / Gemini CLI | agent-first IDE/CLI; Gemini CLI repo ([transition](https://github.com/google-gemini/gemini-cli/discussions/27274), [repo](https://github.com/google-gemini/gemini-cli)) | 파일/셸/web, MCP, skills/hooks/subagents; 개인 terminal은 Antigravity로 이동 | Gemini CLI Apache-2.0 | 2026-06 개인 Gemini CLI 서비스 중단, enterprise/API는 존속; 이름과 지원상태 혼동 주의 |
| OpenHands | SDK·CLI·cloud/enterprise ([repo](https://github.com/OpenHands/OpenHands), [paper](https://arxiv.org/abs/2407.16741)) | composable agent SDK, sandboxed execution, browser/terminal, scale-out | core MIT; `enterprise/` 별도 source-available | 운영 인프라·모델 비용; enterprise 디렉터리 라이선스 구분 |
| SWE-agent | 연구용 agent/harness ([repo](https://github.com/SWE-agent/SWE-agent), [paper](https://arxiv.org/abs/2405.15793)) | ACI 연구, SWE-bench 실행, sandbox(SWE-ReX) | 저장소 라이선스 원문 확인 필요 | 연구/eval 중심, 범용 팀 제품과 다름 |
| Aider | terminal pair programmer ([repo](https://github.com/Aider-AI/aider)) | repo map, multi-model, git commits/undo, lint/test loop | Apache-2.0 | 2025-08 표시 릴리스 이후 유지보수 상태를 도입 시 재확인; 주로 단일 사용자 CLI |
| Cline | VS Code/JetBrains·CLI·SDK·Kanban ([repo](https://github.com/cline/cline)) | approval 기반 도구, browser, headless CI, worktree multi-agent | Apache-2.0(일부 JetBrains 코드는 비공개 표기) | 모델/API 비용과 MCP 공급망; 기능별 공개 범위 구분 |
| goose | 로컬 desktop·CLI·API ([official](https://block.github.io/goose/)) | 일반 목적 local agent, code/shell, MCP extensions | Apache-2.0 | coding 전용이 아니며 확장별 신뢰·권한을 별도 평가 |
| Continue | CLI·VS Code·JetBrains ([repo](https://github.com/continuedev/continue)) | model/provider configurable coding agent | Apache-2.0 | 2026년 repo가 read-only/비활성 유지보수라고 명시; 신규 도입 위험 |

**비교 해석.** “오픈소스”는 harness 코드의 공개만 뜻할 수 있고 모델, 호스팅, 엔터프라이즈 기능, 데이터 처리까지 공개·자체 호스팅된다는 뜻은 아니다. 제품 선택은 데모보다 (1) 배포 경계, (2) 저장소/secret 처리, (3) 권한·감사·보존 정책, (4) 모델 고정/교체, (5) 내부 과제 성공률과 총비용, (6) 라이선스·지원수명으로 해야 한다.

## 4. 연구와 벤치마크

| 평가 | 무엇을 측정 | 강점 | 함정/한계 |
|---|---|---|---|
| HumanEval/MBPP | 독립 함수 생성, hidden unit tests | 싸고 반복 가능 | 저장소 탐색·도구·장기 변경을 거의 측정하지 않음 |
| SWE-bench Original/Lite/Verified | GitHub issue와 과거 repo에서 patch가 FAIL_TO_PASS/PASS_TO_PASS tests 통과하는지 ([paper](https://arxiv.org/abs/2310.06770), [Verified](https://openai.com/index/introducing-swe-bench-verified/)) | 실제 이슈·저장소, end-to-end agent 비교 | Python/12 repos 편중, 공개 데이터 오염, 테스트가 의도 전체를 대표하지 않음; Verified 500도 노후화 |
| SWE-bench Multilingual/Multimodal | 9개 언어 300 과제; UI screenshot이 필요한 visual issue ([multilingual](https://www.swebench.com/multilingual.html)) | Python/text 편향 완화 | 규모·repo 표본, 공개 오염, 환경 재현 문제 잔존 |
| SWE-bench Live | 최근 live repo activity 1,319 초기 과제로 contamination 완화 ([paper](https://arxiv.org/abs/2505.23419)) | 시간 기반 fresh 평가 | 지속 수집/환경 유지 비용, 모델 cutoff 검증 필요 |
| SWE-bench Pro | 41 repos, 1,865 public/held-out/commercial 장기 과제 ([paper](https://labs.scale.com/papers/swe_bench_pro)) | 사설·기업 코드, 더 큰 patch/난도 | 운영 주체의 비공개 subset을 완전 독립 재현 불가; 2026 OpenAI가 설계·오염 문제를 비판함 |
| SWE-Lancer | 1,488 Upwork IC/manager 과제, 실제 지급액과 end-to-end tests ([paper](https://openai.com/index/swe-lancer/)) | 경제적 규모·full-stack/관리 판단 | 한 플랫폼/과거 프로젝트, 달러가 보편 가치 아님; 공개 split과 전체 재현 차이 |
| Terminal-Bench 2.x | Docker terminal에서 현실적 CLI 과제, 상태 verifier ([official](https://www.tbench.ai/news/announcement)) | 코딩+시스템 작업, agent trajectory | 환경/의존성 drift, reward hacking, timeout/compute가 순위에 영향 |
| Terminal-Bench Challenges | compiler 같은 단일 대형 장기 프로젝트 ([official](https://www.tbench.ai/news/terminal-bench-challenges)) | 장기 컨텍스트·자율성 stress test | 표본 수가 매우 작고 비용이 큼; 일반 생산성 추론 불가 |
| RE-Bench | 7개 8시간 ML R&D 환경에서 인간 전문가와 agent ([repo](https://github.com/METR/RE-Bench)) | 인간 비교, open-ended research engineering | 일반 제품 SWE가 아닌 AI R&D; 과제 적고 안전상 solution 보호 |
| METR time horizon | 사람이 걸리는 과제 길이에 따른 agent 50% 성공시간 ([research](https://metr.org/research/)) | “몇 분짜리 과제인가”라는 직관적 축 | 인간시간 추정·과제 분포·scaffold에 민감; 업무 대체 시간과 같지 않음 |

### 점수 해석 체크리스트

1. **모델과 agent를 분리한다.** 같은 모델도 scaffold, prompt, tools, attempts, token/시간 budget이 다르면 다른 시험이다.
2. **pass@1과 다중 시도/best-of-N을 구분한다.** N을 늘리면 성공률과 비용이 함께 오른다.
3. **분모와 실패를 본다.** setup/pod 실패를 모델 실패에서 제외했는지, 미제출 과제를 어떻게 처리했는지 확인한다. Anthropic은 인프라 오류가 과제의 최대 6%에 이르렀고 자원·시간 차이가 비교를 왜곡한다고 보고했다 ([infrastructure noise](https://www.anthropic.com/engineering/infrastructure-noise)).
4. **오염과 benchmark optimization을 본다.** 공개 이슈·gold patch·tests가 훈련/검색/에이전트 지침에 노출될 수 있다. OpenAI는 2026년 SWE-bench Verified가 설계·오염 문제로 의미 있는 신호를 잃었다고 주장했다 ([analysis](https://openai.com/index/separating-signal-from-noise-coding-evaluations/)). 이는 이해관계 있는 공급자 분석이므로 독립 검증과 함께 읽어야 한다.
5. **테스트의 타당성을 본다.** patch가 hidden tests를 통과해도 maintainability, UX, security, license, 운영 적합성은 측정하지 않을 수 있다. 반대로 brittle test가 정답을 거절할 수 있다.
6. **환경과 날짜를 고정한다.** base commit, container image, dependency mirror, network, CPU/RAM, tool versions, model snapshot, sampling, 비용, 전체 trajectory를 기록한다.
7. **비용 대비 성능을 본다.** 성공률만이 아니라 성공 1건당 모델 토큰·wall time·compute·인간 검토/재작업을 포함한다.
8. **내부 eval로 종결한다.** 과거 내부 이슈를 시간 분할하고 보안·품질 rubric과 실제 CI를 써서 제품 후보를 같은 harness/예산으로 평가한다.

## 5. 실무 운영 플레이북

### 도입 전

1. **과제 등급화:** 문서/테스트/기계적 refactor(저위험), 기능/버그(중간), auth/결제/infra/migration/production(고위험)으로 나누고 허용 도구와 승인자를 매핑한다.
2. **baseline:** lead time, review time, change failure/revert, escaped defect, security findings, compute 비용, 개발자 만족을 4–8주 측정한다. LOC/PR 수만 최적화하지 않는다.
3. **대표 과제 eval:** 공개 벤치마크가 아니라 우리 repo의 완료된 이슈를 시간 분할해 blind test한다. 모델·harness·비용·인간 시간을 함께 기록한다.

### 한 과제 실행

1. 이슈에 목적, non-goals, 수용 기준, 관련 경로, 재현법, 금지사항, 필요한 문서 링크를 쓴다.
2. `AGENTS.md` 등 repo instruction에는 정확한 build/test/lint 명령, 디렉터리별 규칙, architecture boundary, generated file 정책, secret/production 금지를 둔다. 짧고 실행 가능하게 유지하고 CI와 불일치하지 않게 한다.
3. 큰 목표는 독립적으로 검증 가능한 작은 vertical slice로 나눈다. 병렬화는 파일/소유권 경계가 명확할 때만 한다.
4. 먼저 읽기 전용 탐색과 계획을 요구한다. 에이전트가 인용한 파일/심볼/테스트를 사람이 spot-check한 뒤 쓰기 권한을 연다.
5. 깨끗한 worktree/branch, 최소 secret, 제한된 network, 고정 dependency mirror에서 실행한다. 외부 문서·issue·README·tool output은 신뢰하지 않는 데이터로 취급한다.
6. 빠른 관련 테스트를 먼저 돌리고, 실패 원인을 보존한다. 같은 패치를 반복하거나 범위가 커지면 중단한다.
7. 생성된 테스트만으로 생성된 구현을 검증하지 않는다. 기존 회귀 test, 독립적인 새 acceptance test, lint/type/static/security/dependency scan을 조합한다.
8. diff size와 파일 범위를 제한한다. generated lockfile/vendor/CI/security 설정 변경은 별도 승인을 요구한다.
9. PR에는 목표, 접근, 변경 파일, 실행한 정확한 명령/결과, 실행하지 못한 검증, 위험/rollback을 구조화해 기록한다. 원시 agent 로그와 비용/모델 버전은 감사 저장소에 둔다.
10. 작성 에이전트와 독립된 사람 또는 review agent가 요구사항→테스트→코드 순으로 검토한다. 중요한 변경은 CODEOWNERS/보안/DB 승인 후 merge한다.

### CI·관찰 가능성·롤백

- CI token은 read-only가 기본이고, write는 PR 생성 같은 선언된 safe output으로 제한한다. GitHub agentic workflows도 firewalled container, read-only token, safe outputs를 기본 원리로 설명한다 ([docs](https://docs.github.com/en/copilot/concepts/agents/about-github-agentic-workflows)).
- 기록할 것: actor/model/harness/version, prompt/request hash, repo/base SHA, tool calls, approvals, network destinations, patches, tests, token/cost/wall time, terminal state. reasoning 전문은 필수가 아니며 행동 증거가 더 감사 가능하다.
- merge 후 feature flag/canary와 SLO를 연결한다. 이상 시 자동 배포 중단, revert commit/roll-forward runbook을 준비한다. 에이전트에게 직접 production rollback 권한을 주지 않는다.
- 월별로 성공률, 인간 수정률, reverted/escaped defects, 비용을 task class별로 재평가한다. 모델 업데이트는 새 공급자처럼 regression eval한다.

## 6. 위험–통제 매트릭스

| 위험 | 전형적 경로/영향 | 우선 통제 | 남는 한계 |
|---|---|---|---|
| 간접 prompt injection | README, issue, 웹, 로그, MCP 결과가 “secret 전송/명령 실행” 지시 | 외부 콘텐츠를 data로 태깅; 도구와 데이터 plane 분리; egress allowlist; 고위험 행동 승인; injection red-team | 모델 필터만으로 완전 제거 불가 ([OWASP](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)) |
| 과도한 권한 | 광범위 repo/cloud token, root shell → 파괴·권한 상승 | least privilege, per-task ephemeral credential, read-only default, JIT scoped token, VM/container | 승인 피로, 샌드박스 escape/설정 오류 |
| secret/코드 유출 | prompt/context/telemetry, network upload, public PR | secret 없는 sandbox, egress proxy, DLP/secret scan, privacy/retention contract, private logs | 추론 가능한 민감정보, 공급자/플러그인 하위처리자 |
| 공급망 공격 | 악성 dependency/installer, MCP/skill/hook, typosquat | lock/pin/hash, private registry, SBOM/SLSA, signed extension, dependency diff 승인, malware/advisory scan | trusted upstream compromise, transitive dependency |
| 취약/틀린 코드 | hallucinated API, unsafe default, test gaming | secure coding rules, SAST/DAST/fuzz, threat model, independent test/review, production telemetry | 도구 false negative, 논리/권한 결함 |
| 범위 이탈/파괴 | 대규모 rename/delete, migration, config 수정 | path denylist, diff/file/command budget, protected branch, snapshot/worktree, human gate | 허용 범위 안의 의미적 손상 |
| 메모리/컨텍스트 오염 | 오래되거나 악의적인 instruction이 세션을 지배 | provenance·scope·TTL, immutable policy 우선순위, memory review/delete, fresh session | 자연어 충돌 해석의 불확실성 |
| 멀티에이전트 오류 전파 | 공통 가정, 공유 workspace 충돌, peer injection | 격리 worktree, 명시적 ownership, typed handoff, independent verifier, merge queue | 상관된 모델 오류, 비용 폭증 |
| 라이선스/IP | public code와 유사한 출력, copyleft/미확인 snippet, 학습·기밀 계약 | provenance/reference filter, license scan, approved models/data terms, legal policy, human attribution | 생성물 기원 입증의 구조적 한계 |
| 개인정보/규제 | 고객 데이터가 prompt/log에 유입 | data classification, minimization/redaction, region/retention controls, DPIA, access audit | 국가·계약별 해석, 삭제/학습 정책 변화 |
| 책임소재/감사 실패 | 누가 무엇을 승인했는지 불명 | named owner, immutable event log, PR attestation, segregation of duties, incident runbook | 모델 내부 이유의 완전한 설명 불가 |
| 비용/서비스 종속 | loop, 큰 context, model/API 변경, 제품 sunset | token/time/retry budget, cost alerts, provider abstraction, exportable instructions/evals | portability 차이, 성능 회귀 |

OWASP는 prompt injection, excessive agency, supply chain을 agentic system의 핵심 위험으로 다루고 ([Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)), NIST SP 800-218A는 AI 모델/시스템 생산자와 구매자를 위한 SSDF 보완 프로필을 제공한다 ([NIST](https://www.nist.gov/publications/secure-software-development-practices-generative-ai-and-dual-use-foundation-models-ssdf)). 그러나 일반 프레임워크는 각 코딩 도구의 실제 sandbox, network, token, data flow threat model로 구체화해야 한다.

## 7. 생산성·품질·경제성의 실증 근거

### 서로 다른 결과

- **속도 향상 RCT:** 95명의 전문 개발자가 제한된 JavaScript HTTP server 과제를 수행한 Copilot 실험에서 treatment가 55.8% 빨랐다 ([paper](https://arxiv.org/abs/2302.06590)). 한 과제·초기 세대 completion 도구이므로 전체 SDLC나 agentic tool의 효과로 일반화할 수 없다.
- **속도 저하 RCT:** METR의 2025년 초 연구는 자기 mature OSS repo에 평균 5년 경험이 있는 16명, 246개 실제 이슈에서 AI 허용 조건이 19% 느렸다(95% CI +2%~+39%). 참가자는 사전 24%, 사후에도 20% 빨라졌다고 믿어 지각과 시간 측정이 어긋났다 ([paper](https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf)). 표본이 작고 특정 도구 세대·매우 숙련된 repo라는 한계가 있다. METR은 2026년 더 큰 후속 연구로 설계를 바꾸고 있다고 공개했다 ([update](https://metr.org/blog/2026-02-24-uplift-update/)).
- **조직 설문/관찰:** DORA 2024는 AI 채택이 개인의 flow·만족·생산성과 양의 관련, delivery throughput·stability와 음의 관련을 보고했다; 25% AI 증가와 1.5% throughput 감소, 7.2% stability 감소의 연관을 제시했다 ([report](https://dora.dev/ai/gen-ai-report/report/)). 이는 인과 RCT가 아니며 2025 후속 보고는 throughput 방향이 바뀌었다고 요약되어 기술·조직 맥락 변화가 크다는 점을 보여준다.
- **실사용 관찰:** Anthropic은 2025-10~2026-04 약 40만 Claude Code 세션의 privacy-preserving 분석에서 사람이 주로 “무엇을”, Claude가 “어떻게”를 결정하고 domain expertise가 성공과 연관된다고 보고했다 ([study](https://www.anthropic.com/research/claude-code-expertise)). 공급자 소유 로그와 성공 판정 방식이므로 독립 연구와 구분한다.

### 경제성 계산

총효과는 `절약된 인간시간 가치 – (모델/compute + 설정/대기 + 검토/수정 + 실패/incident 기대손실 + 플랫폼 전환비용)`으로 봐야 한다. “토큰당 가격”이나 “생성 LOC”는 대리변수일 뿐이다. task class별로 median/p90 완료시간, first-pass acceptance, 인간 수정분, review burden, escaped defect, success당 비용을 같이 측정한다. 병렬 에이전트는 wall-clock을 줄여도 총 compute와 검토 큐를 늘릴 수 있다.

## 8. 역할별 학습 로드맵

### 입문자

1. Git, branch/diff/revert, shell, unit test와 CI 기본을 먼저 익힌다.
2. Copilot 초기 소개로 completion과 pair programming을 이해한다 ([GitHub 2021](https://github.blog/news-insights/product-news/introducing-github-copilot-ai-pair-programmer/)).
3. ReAct와 Anthropic의 workflow/agent 정의를 읽고 “생각하는 챗봇”보다 “도구+피드백 loop”로 이해한다.
4. 작은 toy repo에서 읽기 전용 설명 → 한 테스트 추가 → 작은 bug fix를 수행하고 모든 diff를 설명한다.
5. prompt injection·secret·dependency 위험을 OWASP secure coding/agent cheat sheet로 학습한다 ([secure coding](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Coding_with_AI_Cheat_Sheet.html)).

### 실무 개발자

1. Claude Code best practices의 explore–plan–code–commit, 테스트, 컨텍스트 패턴을 공급자 조언으로 비판적으로 읽는다 ([guide](https://www.anthropic.com/engineering/claude-code-best-practices)).
2. 자신의 repo에 짧은 instruction 파일, 정확한 test commands, architecture constraints를 작성한다.
3. worktree/sandbox, network/secret 최소화, 작은 PR, 독립 리뷰를 일상 루프로 만든다.
4. SWE-agent 논문으로 ACI와 harness가 모델만큼 중요함을 이해하고, 공개 benchmark score를 내부 과제와 대조한다.
5. 한 달간 task class별 시간·수정률·실패·비용을 기록해 자신에게 실제로 빠른 영역만 확대한다.

### 팀 리드 / 플랫폼·보안 팀

1. threat model과 data flow(repo→context→provider→tool→network)를 그린다. NIST SSDF 800-218/218A와 OWASP agent controls를 정책에 매핑한다.
2. 중앙 gateway, approved model/tool/MCP registry, ephemeral sandbox, scoped identity, egress, audit, budgets를 제공한다.
3. golden internal eval set과 adversarial tests를 만들고 model/harness update gate로 사용한다.
4. CODEOWNERS, safe outputs, CI/security scan, provenance, rollback/incident response를 강제한다.
5. DORA와 RCT의 상반 결과를 반영해 팀/제품 outcome을 측정하고 좌석 수·PR 수를 성공으로 보지 않는다.

### 연구자

1. ReAct → Reflexion/CodeAct → SWE-agent/OpenHands → SWE-bench 계열 순으로 architecture와 평가를 연결해 읽는다.
2. 동일 model snapshot과 scaffold를 고정하고 trajectory, environment image, budget, cost를 공개한다.
3. contamination-resistant temporal/private split, flaky infra audit, semantic/human review를 설계한다.
4. 단일 pass rate를 넘어 calibration, failure taxonomy, security, maintainability, human-agent interaction, long-term cost를 측정한다.
5. 연구 solution/benchmark의 공개 자체가 contamination을 만들므로 protected evaluation과 재현성의 긴장을 명시한다.

## 9. 결론의 강도와 연구 공백

### 근거가 강한 결론

- agentic coding은 동적 도구 선택과 환경 피드백 loop라는 점에서 completion과 구별된다.
- 모델 외부의 ACI/harness, 저장소 지침, 테스트, 권한 경계가 결과를 크게 좌우한다.
- 테스트 가능한 작은 과제와 명확한 수용 기준이 더 적합하며, 사람의 요구사항·보안·merge 판단은 필요하다.
- 공개 benchmark는 모델 능력의 제한된 대리변수다. 모델+agent+budget+환경+날짜를 함께 보고해야 한다.
- 셸·네트워크·secret·외부 콘텐츠를 연결한 agent는 prompt injection과 excessive agency 때문에 전통적 coding assistant보다 큰 blast radius를 가진다.

### 혼재된 결론

- 평균 생산성 향상의 크기와 방향: 초보/낯선 과제/보일러플레이트에는 이점 가능성이 높지만, 익숙한 복잡 repo에서는 검토·대기 비용이 앞설 수 있다.
- 생성 코드 품질: 테스트와 리뷰를 강화하면 개선 도구가 될 수 있으나 agent가 만든 테스트와 공개 benchmark만으로는 취약성·유지보수성을 보장하지 않는다.
- 멀티에이전트: 큰 실험에서 가능성을 보였지만 단일 agent 대비 순효과와 일반화된 비용-품질 증거가 약하다.
- 자연어 spec-driven 개발: 명료성·추적성을 높일 수 있으나 잘못된 spec을 빠르게 확장하는 위험도 있다.

### 아직 모르는 것

- 1–3년 뒤 agent-authored code의 결함, 보안사고, 이해가능성, 유지보수·폐기 비용.
- 주니어 학습, mental model, 디버깅 역량과 senior review load의 장기 변화.
- 사설 monorepo, legacy, embedded/safety-critical, 규제 산업에서의 독립 RCT.
- 여러 모델/에이전트가 상관된 오류를 만드는 정도와 독립 reviewer의 실제 효과.
- prompt injection을 완전히 막지 못하는 상황에서 허용 가능한 egress/권한의 정량 경계.
- 코드 provenance와 라이선스 유사성 판정의 신뢰성, 국가별 책임 배분.
- 빠른 모델·제품 교체 속도에서 재현 가능한 경제성 비교 방법.

## 조사 한계와 최소 후속 Inquiry

공개 웹 전체를 완전 열거하지 못했다. 검색은 영어 1차 자료에 편향되어 있고, 중국권/일본권 도구, 소규모 프로젝트, 사내 비공개 평가, 유료 시장 보고서, 로그인 뒤 문서는 충분히 다루지 못했다. 공급자 문서는 자기 제품의 성공사례와 최신 기능을 가장 잘 설명하지만 독립 효능 근거가 아니다. 2026-08-28 현재라는 환경 날짜에 맞춰 2026 문서를 포함했으나 계속 갱신되는 페이지는 후일 내용이 달라질 수 있다. 접근 실패·제외·검색 포화 기준은 `search-log.md`, 중복 제거된 주석형 원문은 `sources.md`에 있다.

**가장 작은 유용한 후속 Inquiry:** 특정 조직의 20–40개 과거 실제 이슈를 위험/언어/크기로 층화하고, 후보 2개 agent를 동일 모델 예산·ephemeral sandbox·hidden acceptance tests 아래 비교하는 사전등록형 내부 pilot 설계. 산출물은 성공률뿐 아니라 인간 총시간, review 수정량, 보안 finding, 성공당 비용, rollback을 측정하는 eval protocol이어야 한다. 제품 선택이나 배포 승인은 Human-owned decision으로 남긴다.
