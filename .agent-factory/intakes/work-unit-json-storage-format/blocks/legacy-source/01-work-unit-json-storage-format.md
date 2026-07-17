---
id: work-unit-json-storage-format
date: 2026-07-14
type: comparison-research
basis_request: "워크 유닛 저장 포멧을 JSON으로 변경하는 Work Unit을 만들고, 이를 위해 자료 조사부터 수행"
related_artifacts:
  - "docs/interviews/work-unit-json-storage-format-decision.md"
  - "docs/work-units/work-unit-json-storage-format/"
sources:
  - "https://www.rfc-editor.org/info/rfc8259/"
  - "https://www.rfc-editor.org/info/rfc7493/"
  - "https://www.rfc-editor.org/info/rfc8785/"
  - "https://json-schema.org/specification"
  - "https://json-schema.org/draft/2020-12/json-schema-core"
  - "https://json-schema.org/draft/2020-12/json-schema-validation"
  - "https://tc39.es/ecma262/multipage/structured-data.html"
  - "https://dom.spec.whatwg.org/#dom-node-textcontent"
  - "https://html.spec.whatwg.org/multipage/dynamic-markup-insertion.html"
  - "https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html"
  - "https://spec.commonmark.org/spec"
---

# Work Unit JSON 저장 형식 조사

## 조사 질문

Work Unit의 의미 데이터를 JSON 단일 원본으로 저장하고 HTML을 JSON에서 파생 렌더링하는 구조가 현재 프로젝트에 적합한가? 현재 필수 파일인 `output/result.md`는 어떤 JSON 계약으로 대체해야 하는가?

## Human Fact

- Human은 Work Unit 저장 형식을 JSON으로 변경하는 Work Unit 생성을 요청했다.
- Human은 Work Unit을 HTML로 렌더링하기 위한 원본으로 JSON이 적합하다는 방향을 제시했다.
- Human은 구현 전에 자료 조사를 먼저 수행하도록 요청했다.

## 조사 범위와 방법

### 저장소 조사

- `.codex/skills/work-unit-planner-af/`의 스킬, 구조 문서, JSON Schema, manager와 회귀 테스트를 조사했다.
- `.codex/skills/agent-factory-lifecycle-af/references/lifecycle.md`의 역사적 Markdown 패키지 규칙을 조사했다.
- `docs/`, Design Document, 기존 Research와 Work Unit 존재 여부를 조사했다.
- 다음 명령을 사용했다.
  - `rg -n --hidden 'result\.md|output/result|CANONICAL_PACKAGE_FILES' .`
  - `python3 .codex/skills/work-unit-planner-af/assets/scripts/work_unit.py check-schemas`
  - `python3 -m unittest discover -s .codex/skills/work-unit-planner-af/tests -p 'test_*.py'`

### 외부 조사

- JSON의 구조·상호운용성·제약을 RFC 8259와 RFC 7493에서 확인했다.
- JSON의 바이트 단위 정규화가 별도 요구인지 RFC 8785에서 확인했다.
- JSON Schema의 현행 공개 버전, 구조 검증과 한계를 공식 명세에서 확인했다.
- 브라우저의 JSON 파싱과 안전한 DOM 렌더링 경계를 ECMAScript, WHATWG와 OWASP 공식 자료에서 확인했다.
- Markdown 대안은 CommonMark 공식 문서의 블록·인라인 파싱 모델과 raw HTML 허용 범위를 확인했다.

## 저장소 근거

| 근거 | 위치 | 확인 내용 |
| --- | --- | --- |
| Work Unit 원본 규칙 | `.codex/skills/work-unit-planner-af/SKILL.md` | Work Unit source data와 AI/Human checklist는 JSON이며 HTML·Markdown은 파생 렌더링으로 정의되어 있다. |
| 필수 패키지 구조 | `.codex/skills/work-unit-planner-af/SKILL.md`, `references/work-unit-structure.md` | 필수 core package에 `output/result.md`가 남아 있다. |
| manager 계약 | `.codex/skills/work-unit-planner-af/assets/scripts/work_unit.py` | `output/result.md`를 canonical file로 요구하고 생성 시 정적 placeholder를 작성하며, 파일이 없으면 검증이 실패한다. |
| 회귀 테스트 | `.codex/skills/work-unit-planner-af/tests/test_work_unit_manager.py` | 완전한 canonical package에 `output/result.md`가 포함되어야 한다고 검증한다. 기준 회귀 테스트는 현재 통과한다. |
| JSON Schema | `.codex/skills/work-unit-planner-af/assets/schema/*.schema.json` | `2.0.0` 계약의 7개 스키마가 `check-schemas`를 통과한다. 결과 보고서 전용 JSON Schema는 없다. |
| 프로젝트 아티팩트 | `/home/deus/workspace/skills` | 현재 `docs/`와 관련 Design Document가 없으며, 기존 프로젝트 Work Unit도 없다. |
| 스킬 위치 상태 | 프로젝트 `.codex/skills/`와 `/home/deus/.codex/skills/` | 두 사본이 서로 다르고 HOME 쪽에는 현재 manager 파일이 없다. 실행 시 활성 소스 확인이 필요하다. |

## 외부 출처

| 출처 | 등급 | 신선도 | 핵심 근거 |
| --- | --- | --- | --- |
| [RFC 8259](https://www.rfc-editor.org/info/rfc8259/) | T1 authoritative primary | F3: 2017 Internet Standard, 현행 STD 90 | JSON은 경량·텍스트 기반·언어 독립적인 구조화 데이터 교환 형식이다. 객체 순서, 중복 이름과 숫자 표현의 상호운용 한계를 고려해야 한다. |
| [RFC 7493 I-JSON](https://www.rfc-editor.org/info/rfc7493/) | T1 authoritative primary | F3: 2015, 현행 Proposed Standard | UTF-8, 중복 객체 이름 금지, 안전한 숫자 범위 등 예측 가능한 처리를 위한 제약을 제공한다. |
| [RFC 8785 JCS](https://www.rfc-editor.org/info/rfc8785/) | T1 authoritative primary | F3: 2020 | 해시·서명처럼 동일 바이트가 필요할 때는 일반 JSON과 별도의 canonicalization이 필요하다. |
| [JSON Schema Specification](https://json-schema.org/specification) | T1 authoritative primary | F5: 2026 현재 공식 현행 목록 | 현재 공개된 현행 meta-schema는 Draft 2020-12이며 프로젝트의 기존 dialect와 일치한다. |
| [JSON Schema Core 2020-12](https://json-schema.org/draft/2020-12/json-schema-core) | T1 authoritative primary | F3: 2022, 현행 공개 릴리스 | JSON 문서의 구조와 dialect를 선언하고 assertion 기반 검증 계약을 구성할 수 있다. |
| [JSON Schema Validation 2020-12](https://json-schema.org/draft/2020-12/json-schema-validation) | T1 authoritative primary | F3: 2022, 현행 공개 릴리스 | `type`, `required`, `const` 등의 검증을 정의한다. `format`은 기본적으로 강제 assertion이 아니므로 별도 정책이 필요하다. |
| [ECMAScript JSON.parse](https://tc39.es/ecma262/multipage/structured-data.html) | T1 authoritative primary | F5: living specification | 표준 JSON parser는 JSON 문자열을 객체, 배열과 primitive 값으로 변환하므로 브라우저 renderer의 직접 입력으로 사용할 수 있다. |
| [WHATWG DOM textContent](https://dom.spec.whatwg.org/#dom-node-textcontent) | T1 authoritative primary | F5: 2026-03-15 갱신 | `textContent`는 문자열을 Text node로 다루므로 plain-text 렌더링의 안전한 기본 경계가 된다. |
| [WHATWG HTML dynamic markup insertion](https://html.spec.whatwg.org/multipage/dynamic-markup-insertion.html) | T1 authoritative primary | F5: 2026-07-13 갱신 | 동적 HTML 삽입과 sanitization은 별도 보안 경계이며 데이터 형식 검증만으로 대체되지 않는다. |
| [OWASP XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html) | T2 primary expert | F5: 공식 저장소 2026-05-14 변경 확인 | JSON 문자열을 포함한 동적 데이터는 untrusted로 취급하고 `textContent` 같은 safe sink를 사용하며 raw `innerHTML`을 피해야 한다. |
| [CommonMark 0.31.2](https://spec.commonmark.org/spec) | T1 maintainer specification | F3: 2024-01-28 | Markdown은 블록과 인라인의 별도 파싱이 필요하며 raw HTML 구조도 표현할 수 있다. 구조화 UI 데이터의 canonical model보다 파생 문서에 적합하다는 판단 근거가 된다. |

## Findings

1. JSON은 Work Unit의 구조화된 의미 데이터를 기계적으로 검증하고 브라우저에서 직접 소비하기에 적합하다.
2. 현재 프로젝트는 이미 대부분의 의미 데이터와 checklist를 JSON Schema `2.0.0`으로 관리하므로 JSON 단일 원본 방향은 기존 모델과 일치한다.
3. `output/result.md`는 내용 스키마가 없고 정적 placeholder만 생성되지만 manager와 validator가 존재 자체를 강제한다. 현재 모델에서 유일한 필수 Markdown 결과 파일이다.
4. Markdown을 canonical result로 유지하면 JSON과 별도의 parsing·표현 계약이 필요하고 JSON 기반 renderer와 의미가 중복될 수 있다.
5. JSON Schema 검증은 HTML 렌더링의 XSS 방어가 아니다. renderer는 모든 문자열을 untrusted로 취급하고 safe DOM sink 또는 명시적 sanitization을 사용해야 한다.
6. 객체 key 순서는 표시 순서가 아니므로 순서가 필요한 section, checklist와 step은 배열로 모델링해야 한다.
7. 로그와 screenshot 같은 원시 증거 파일까지 JSON으로 인라인할 근거는 없다. 의미 데이터 JSON에서 경로·media type·설명을 참조하는 경계가 더 적합하다.
8. 동일 바이트 해시나 서명 요구가 없으므로 RFC 8785 JCS를 도입할 근거는 없다.
9. `result.md` 필수 계약을 제거하거나 교체하면 기존 `2.0.0` validator와 package contract의 호환성이 깨질 수 있으므로 명시적 버전·마이그레이션 정책이 필요하다.

## 대안 비교

| 대안 | 설명 | 장점 | 단점 |
| --- | --- | --- | --- |
| A | 새 major contract에서 `data/report.json`을 canonical result로 추가하고 필수 `output/result.md`를 제거한다. HTML·Markdown은 선택적 파생물로만 둔다. | JSON source of truth 원칙과 `data/` 소유권이 일치하고 renderer·validator가 한 계약을 공유한다. | 스키마, manager, 문서와 테스트 변경 및 기존 package의 명시적 migration 경계가 필요하다. |
| B | 새 major contract에서 `output/result.json`으로 직접 교체한다. | 현재 `output/` 경로 의미를 가장 적게 바꾼다. | 현재의 `data/`가 JSON source of truth라는 소유권 규칙과 충돌하여 canonical 데이터가 두 디렉터리로 나뉜다. |
| C | 기존 계약에 canonical JSON result를 추가하되 `result.md`를 선택적 파생 export로 유지한다. | 점진적 호환과 사람이 바로 읽는 export를 유지하기 쉽다. | 전환 기간에 두 표현이 생기며 JSON-only core contract를 즉시 달성하지 못하고 drift 방지 규칙이 추가된다. |

## Recommendation

대안 A를 권고한다. `data/report.json`에 실행 결과의 의미 데이터를 두고 HTML을 일방향으로 파생하면 JSON Schema 검증, renderer 재사용과 DRY 원칙이 한 모델에 모인다. 필수 Markdown을 제거하는 변화는 기존 계약을 조용히 바꾸지 말고 새 major package contract로 명시하며, 기존 package는 자동 덮어쓰기 없이 별도 migration 대상으로 유지하는 편이 안전하고 되돌리기 쉽다.

## Work Unit acceptance criteria 후보

- 결과 보고서 전용 JSON Schema를 먼저 정의하고 required field, 추가 필드 정책과 순서 보존 배열을 명시한다.
- 새 package 생성 결과에는 canonical Markdown 파일이 없고 canonical result JSON이 존재한다.
- manager의 `create`, `migrate`, `validate`, `show`, `update`, `transition` 경계를 새 계약에 맞춘다.
- JSON parse, schema validation과 domain invariant 검증을 통과한 데이터만 renderer 입력이 될 수 있다.
- duplicate key, 누락·추가·잘못된 type, 비정상 깊이·크기 입력의 실패 동작을 테스트한다.
- renderer 관련 계약에는 `eval` 금지, plain text의 `textContent` 사용, raw HTML sink 금지와 XSS fixture 검증을 포함한다.
- 기존 package의 source byte를 자동 변경하거나 삭제하지 않고 지원·migration 동작을 명시한다.
- 관련 Design Document가 실행 전에 존재하는지 확인하고, design-impacting 변경 후 업데이트하거나 no-update reason을 review와 report evidence에 기록한다.

## Limitations and unresolved items

- 2026-07-14 Human이 대안 A를 선택했다. `data/report.json`, 새 major contract, 필수 `output/result.md` 제거와 별도 migration 경계가 확정되었다.
- HTML renderer 자체를 같은 Work Unit에서 구현할지는 Human 요청에 포함되지 않았다. 저장 계약 변경 Work Unit에서는 renderer가 사용할 JSON 계약과 보안 acceptance criteria까지만 정의하는 것이 최소 범위다.
- 현재 프로젝트 `.codex/skills/`와 `/home/deus/.codex/skills/`의 동기화·활성 위치가 다르므로 실행 시 변경 대상과 propagation 경계를 확인해야 한다.
- 기존 외부 프로젝트의 `2.0.0` package 개수와 migration 기한은 현재 프로젝트 자료만으로 확인할 수 없다.

## Conclusion

결론은 **supported with caveats**다. JSON을 Work Unit 의미 데이터의 단일 원본으로 두고 HTML을 파생 렌더링하는 방향은 외부 표준과 현재 저장소 구조 모두에 부합한다. Human 결정 A에 따라 `data/report.json` 기반 새 major contract와 별도 migration 경계를 실행 Work Unit의 근거로 사용한다.
