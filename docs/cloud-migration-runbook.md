# 클라우드 이전·전환·복구 운영 절차

이 문서는 Human이 승인한 1–13단계 클라우드 아키텍처를 운영 환경에 적용하기 위한 실행 전 검토본이다. 작성일은 2026-09-06이다. 작성 Work는 테스트·검증·배포·공급자 호출·DB 변경·실제 전환을 실행하지 않았다. 아래 명령은 대상과 권한이 확정된 운영자 및 독립 Verification이 수행할 예시다. 코드 존재, 단위 테스트 통과, 운영 전환 완료를 구별한다.

개발 체크아웃의 `../../mcp/` 링크는 이 문서에서 본 형제 서버 저장소다. 설치 환경에서는 선택한 인증 서버의 광고 스키마·패키지 리소스를 사용한다. 이 상대 경로나 `/tmp` handoff는 설치 의존성이 아니다. platform/contracts의 독립 검증은 통과했고 아래 ledger에 기록했다. 최종 retirement 변경은 별도 독립 검증 대상이며 최종 commit·image digest·설치 패키지에 대해 통합 조건을 확인한다. 불일치는 해당 동작의 개방을 막는 사유이며 기존 수락 데이터나 실행 상태를 바꿀 이유가 아니다.

## 1. 권한과 대상 확정

클라우드 선택은 이미 승인되었다. 아키텍처 승인을 다시 요구하지 않는다. 다만 없는 계정·tenant·credential·파괴적 효과 권한을 추정하지 않는다. 운영 기록에는 다음 실제 값을 명시하며 비밀값은 쓰지 않는다.

- 원본 프로젝트 절대 경로, 저장소 식별자·검토된 Git commit, 이전 묶음 ID, 실행자·승인 근거, 변경 창과 원천 writer 정지 범위.
- 대상 public base URL/root prefix, 정확한 MCP endpoint와 끝 슬래시, organization/workspace/user UUID, 허용 효과·scope, 별도 리허설 환경.
- DB 인스턴스·백업 시점/LSN·schema version, object bucket/prefix·버전 snapshot, 암호화 키 버전과 secret-manager 복구 참조.
- 공급자별 실제 계정 ID, provider catalog UUID, connection UUID, 승인 scope, 선택 경계, 시험 한도, OAuth callback과 비밀 참조. OneDrive tenant도 명시적으로 결정하고 코드의 `common` 기본값을 운영 결정으로 쓰지 않는다.
- reporting의 기존 ReportAgent UUID·소유 reporting-user UUID, project/recipient 식별자, credential 파일 참조. 보존 기간·RPO/RTO·중단 기준·전환 책임자는 Human/운영자가 정한다.

| 항목 | 이전 원천·권위 | 이전 후 권위·보존 |
| --- | --- | --- |
| Original/Processed | `.agent-factory/document/{original,processed}/`의 직접 자식 패키지, 기존 타입·출처·바이트 | cloud immutable revision; PostgreSQL 메타데이터와 object storage 바이트. 로컬 원본은 보존 |
| 배포 Skill/Human 명세 | `skills/<id>/`와 버전 관리되는 `.agent-factory/document/specification/<id>/`; Git 저작 권위 | Git는 계속 배포 소스 권위. 검토된 양쪽 snapshot의 cloud accepted revision이 게시 권위. 설치 복사본은 독립 편집 가능한 진실이 아님 |
| 소비자 Project Skill | 확정된 `.codex/skills/<category>-<title>/` 등 AI locator | 설치·소스·cloud locator를 명시적으로 연결. 이 플러그인에 `.codex/` Skill 미러를 만들지 않음 |
| 수집 설정 | `document/sync.json`, 공급자별 선택·결과 메타데이터 | 계정/암호화 credential connection + 독립 immutable collection + run/checkpoint/source mapping |
| SQLite catalog | `.agent-factory/db.sqlite` 및 WAL/SHM; 비권위 projection | 새 검색은 cloud Document/reporting. catalog는 legacy 백업·참조이며 import journal이 아님 |
| 실행·그래프·복구 | `.agent-factory/agent/<id>/session.json`, `runs/<run>/`, loop·dispatch·결과·receipt | 계속 로컬 exec/loop 권위. reporting outbox/ack/semantic intent도 로컬 복구 상태 |
| 공유 보고 | 명시적 결과와 실제 관측 근거 | cloud reporting은 관측·의미 보고 projection. 실행·그래프 END를 지시하지 않음 |
| credential/OAuth cache | 기존 credential authority | 서버 암호화 credential 권위. legacy token 파일은 Document 콘텐츠로 업로드하지 않음 |
| Workspace/확장 | 기존 extension의 exec/loop 명령·경로와 legacy browser 복사본 | 서버가 도메인 UI 소유. 확장의 기존 로컬 실행 경로 유지; 새 프로젝트 로컬 서버/browser tree는 설치하지 않음 |

물리 이전은 타입 변환이 아니다. `legacy-inquery-*`는 비활성 Processed의 provenance/status다. 기존 Markdown Processed를 이전하면서 임의 HTML 변환이나 Original 승격을 하지 않는다. 새 Processed 저작 표현과 물리 이전은 별도 작업이다.

## 2. 원천 목록과 일관된 백업

원본 Document writer와 legacy sync 예약 실행을 정지하는 변경 창을 확보한다. 진행 중 Agent를 임의 종료하지 않는다. 실행 복구 snapshot은 Agent 소유자와 조정하며 과거 PID 상태 복원으로 실행을 재개하지 않는다. 서버 DB/object writer 정지 또는 일관된 PITR 경계도 별도로 정한다.

`rg --files --hidden --no-ignore .agent-factory/document`로 후보를 발견하되 내용을 터미널에 일괄 출력하지 않는다. ignored/숨김 항목과 package 내부 vendor/assets도 포함한다. 직접 자식 패키지별 타입·stable identity·상대 경로·크기·SHA-256·provenance·현 revision·중복/누락/symlink/특수 파일을 기록한다. Git tracked 파일 목록만으로 원본 inventory를 대신하지 않는다. `sync.json`은 계정 참조와 선택을 분리하고 token 값은 전송하지 않는다.

운영 manifest는 API payload와 별개인 검토 기록이다. 버전, 묶음 ID, 확정 tenant, allowlist 대상, source inventory/digest, 승인 효과, expected cloud ID/revision, 실제 receipt, pair publication group, 충돌·중단 조건·복구 방법을 담는다. 모델의 prose/code/SQL이나 schema 모양 제안은 실행 권한이 아니다. 실행 직전 원천 hash와 target revision을 다시 대조한다.

다음은 writer가 정지된 원본 보관 예다. `AF_SOURCE`는 확정 프로젝트, `AF_BACKUP`은 원천 밖 새 private 백업 디렉터리로 먼저 지정한다. tracing을 끄고 credential authority 디렉터리는 별도 백업한다. `.agent-factory` 전체를 포괄 복사하지 않는다.

```sh
umask 077
mkdir -m 700 "$AF_BACKUP"
tar -cpf "$AF_BACKUP/document-source.tar" -C "$AF_SOURCE" .agent-factory/document
sha256sum "$AF_BACKUP/document-source.tar" > "$AF_BACKUP/document-source.tar.sha256"
```

tar는 symlink를 따라가지 않지만 보관할 수 있다. 보관 성공과 import 허용은 다르다. 안전하지 않은 항목은 격리 기록하고 자동 해제/경로 수정하지 않는다. sync 설정에 비밀이 섞여 있으면 archive도 비밀 백업으로 분류해 암호화·접근 제한하고 Document import에서는 제외한다.

catalog는 기존 파일이 있을 때만 SQLite online backup API 등 기존 DB 도구로 일관된 사본을 만든다. 실행 중 DB 파일 하나만 복사하지 않는다. 정지 snapshot이면 DB/WAL/SHM을 같은 시점에 보존한다. DB가 없으면 새 catalog를 초기화하지 않는다. Agent 실행 트리·loop·outbox는 별도 private snapshot으로 보존하며 일반 Document import에서 제외한다. 필요한 durable 실행 증거만 자체 권한으로 업로드한다.

서버 [backup.sh](../../mcp/deploy/backup.sh)의 `pg_dump`와 `mc mirror`는 순차 실행이다. `COMPLETED`는 DB/object 동시 snapshot이나 복구 성공 증거가 아니다. writer 정지와 object version snapshot, 또는 DB 시점까지의 모든 참조 object를 보존하는 방식으로 경계를 묶는다. DB·object manifest·checksum·image digest·schema head·암호화 키 버전·credential 복구 참조를 하나의 backup set에 연결한다. 스크립트는 DSN을 `pg_dump` 인자로 넘기므로 password가 든 DSN을 그대로 넣지 않는다. private libpq service/passfile을 쓰는 직접 `pg_dump --format=custom --file=...` 등 비밀이 argv에 없는 승인된 수단을 사용한다. `mc` 인증도 private authority가 공급한다. 암호화된 원격 불변 보관과 격리 복원 시험이 필요하다.

기존 서버 [legacy_import](../../mcp/app/modules/document/legacy_import.py)의 목록 명령은 최종 패키지에서 먼저 도움말을 확인한다.

```sh
python -m app.modules.document.legacy_import --help
python -m app.modules.document.legacy_import --source "$AF_SOURCE" --manifest "$AF_BACKUP/legacy-documents.json"
```

`--apply` 없는 명령은 원천 목록화다. [기존 migration 문서](../../mcp/config/migration.md)의 `--apply --organization-id --workspace-id --user-id`는 DB/object를 직접 변경하는 별도 경로다. 아래 authenticated import의 reviewed pair/idempotency 계약을 우회하는 대안으로 쓰지 않는다. 목록 도구가 legacy 표현만 다루면 양쪽 Git publication source와 실행 복구 목록을 별도로 더한다.

## 3. 배포 전 독립 리허설과 통합 개방 조건

독립 Verification은 disposable PostgreSQL·별도 object bucket·테스트 identity/credential·실제 설치 이미지에서 시험한다. 운영 DB URL을 재사용하지 않는다. [testing](../../mcp/config/testing.md), [migration tests](../../mcp/tests/integration/test_migrations.py), [deployment tests](../../mcp/tests/test_deployment.py)를 따른다. 아래 cwd는 서버 패키지이며 환경 선택 후 격리 환경에서만 실행한다.

```sh
alembic -c config/alembic.ini heads
alembic -c config/alembic.ini history
alembic -c config/alembic.ini current
alembic -c config/alembic.ini upgrade head
```

`upgrade`는 변경 명령이다. 복원 사본에서 먼저 시험하고 운영 적용은 지정된 대상·변경 창 권한하에 수행한다. 예상 graph는 `0017 -> 0018 -> 0019 -> 0020 -> 0021`, 최종 단일 head다. 최종 파일 `down_revision`, history/heads, 배포 current를 대조한다. 임의 stamp/reset/downgrade로 불일치를 숨기지 않는다.

| 개방 조건 | 최종 설치 패키지의 관측 증거 |
| --- | --- |
| 모델·라우터·MCP | [models](../../mcp/app/db/models.py), [server](../../mcp/app/mcp/server.py), [main](../../mcp/app/main.py)에 Document/Upload/Collection 등록. 인증된 광고 목록에 import/read/write/search/index/prepare_upload/finalize_upload 및 새 document_template 도구와 integration/collection 도구가 실제 나타남 |
| 권한·발급 | `document:read/write`, `integration:read/manage`, `agent:read/report`와 RBAC 검사. 기존 token에 새 write/manage scope가 생기지 않음. 새 권한은 적합한 소유자의 새 발급/동의로만 부여. 타 tenant·read-only write 거부 |
| DB/object 실패 | 실제 비특권 PostgreSQL RLS, 동일 key 동시 요청, stale revision, receipt 유실, object write/readback 실패, commit 직후 연결 손실에서 최신 accepted revision/bytes 보존 |
| Worker | [tasks](../../mcp/app/worker/tasks.py), [authority](../../mcp/app/worker/authority.py), [handler](../../mcp/app/worker/integration_handlers.py)의 실제 `integration.sync`. claimed Job tenant/user에서 권위 재확인, payload는 `collection_run_id`만. cancel/retry-after/terminal failure checkpoint 기록 |
| DB pool·동시성 | [platform guide](../../mcp/docs/cloud-platform.md)에 따라 활성 collection worker당 최소 4개 pooled 연결을 확보하고 취소/재인가 probe와 API/스케줄러/control-plane 요청 여유를 별도로 예약. 프로세스별 유효 pool과 동시 실행 수, 배포 전체 DB 연결 예산을 대조하고 disposable 동시 수집·취소 리허설 통과 후 개방. 계정 refresh advisory lock, session RLS가 내부 commit 후 유지. legacy disconnect/edit도 같은 guard를 사용하거나 동시 사용 차단 |
| 패키징 | checkout docs 없는 이미지에서 integrations/reporting guide 읽기. pair parser PyYAML 직접 dependency, wheel/image 포함. exec/loop의 `runtime/cloud_reporting.py` 설치 후 import 가능 |
| OAuth·로그 | 인증 사용자/workspace/state에 묶인 실제 callback/exchange. 단순 legacy begin 존재만으로 완료 아님. ingress/API/APM의 query/body·authorization/capability·HTTP debug 로그 차단. denial은 교환 없이 종료, no-store/no-referrer/깨끗한 결과 URL |
| preview | 정확히 인증된 GET package preview 성공 응답만 서버 `PREVIEW_HEADERS` 보존. root prefix에서도 동작. member/download/error/shell의 CSP/XFO는 전역 완화하지 않음 |

연결 산정은 [job claim·취소/재인가](../../mcp/app/worker/authority.py), [Job/domain session](../../mcp/app/worker/tasks.py), [connection guard](../../mcp/app/modules/integration/cloud_repository.py)를 기준으로 한다. 전용 Job claim 연결, 유지되는 Job 권한 session, 별도 domain session, 계정 guard 연결이 겹칠 수 있으며 fresh 취소/재인가 probe는 추가 session을 연다. 따라서 4개는 여유를 포함한 충분조건이 아니다. [pool 설정](../../mcp/app/db/session.py)의 `database_pool_size`와 `database_max_overflow`가 각각 `pool_size`와 `max_overflow`로 적용된다. 유한한 pool 설정에서 프로세스별 유효 상한 `pool_size + max_overflow`가 `4 × 해당 프로세스의 최대 동시 활성 collection 수 + 동시 취소/재인가 probe 예약량 + 같은 pool의 API/스케줄러/control 요청 예약량` 이상인지 기록한다. 프로세스마다 pool이 별도이므로 다른 프로세스의 남는 연결을 빌릴 수 있다고 계산하지 않는다. 배포 전체에서는 worker·API·scheduler 프로세스와 replica별 pool 상한을 합산하고 DB의 다른 client 및 운영 제어용 여유를 포함해 서버 연결 한도 안에 두어야 한다. overflow를 지속 부하의 무제한 여유로 취급하지 않는다.

개방 전 독립 Verification은 [platform guide의 격리 harness](../../mcp/docs/cloud-platform.md)를 바탕으로 disposable DB와 provider fixture에서 계획한 최대 동시 collection 수·실제 프로세스별 pool 설정을 재현한다. collection이 claim/권한/domain/계정 guard를 점유한 동안 취소 요청과 fresh 재인가 probe, API/스케줄러/control 요청을 겹쳐 실행한다. pool checkout timeout이나 연결 고갈로 취소·재인가가 막히지 않고, 취소가 durable Job/collection 상태에 반영되며, 이미 저장된 Original과 checkpoint가 보존되고, 종료 후 연결이 반환되는 증거를 남긴다. 실제 설정·동시 실행 수·최대 연결 사용량·대기/timeout·취소 결과를 기록하며 부족하면 동시성을 낮추거나 전체 DB 예산 안에서 pool을 조정한 뒤 재리허설한다. 이 문서 Work는 해당 리허설을 실행하지 않았다.

리허설에는 실제 여섯 Skill pair의 모든 파일, 8 MiB 이상 package, native PDF/DOCX/image, Unicode 경로, 잘못된 ZIP, stale review, 교차 tenant, token 회전, upload expiry를 넣는다. vendor나 필수 파일을 빼서 작은 fixture에 맞추지 않는다. [browser suite](../../mcp/tests/browser/cloud-document-delivery.cjs) 외에 통합 앱 header도 확인한다. sandbox는 `allow-scripts`만 허용하고 `allow-same-origin`은 금지한다. wrapper의 `frame-src blob:`, `connect-src 'none'`, `frame-ancestors 'self'`, `X-Frame-Options: SAMEORIGIN`을 보존한다. parent DOM·cookie·storage·network·top navigation 차단과 한글 본문·상대 CSS/JS·탭·SVG·링크 읽기를 함께 시험한다. 외부 dependency, 동적 import/fetch, eval, iframe/srcset 제한은 바이트 손실과 구별해 기록한다.

## 4. Document import와 수락 바이트 대조

실제 [cloud_schemas.py](../../mcp/app/modules/document/cloud_schemas.py)와 [MCP 서명](../../mcp/app/mcp/documents.py)을 읽는다. unknown field는 거부된다. Document 요청은 `schema_version: "1"`; MCP 바깥 인자는 실제 `organization_id`, `workspace_id`, 안쪽은 `request`다. 암묵적 tenant 기본값에 의존하지 않는다.

항목마다 invariant `document_type`, stable `source_identity`, 원천 locator, collection context, filename/MIME, byte digest·크기를 확정한다. 이동한 절대 경로만으로 identity를 새로 만들지 않는다. content revision과 metadata CAS revision은 구별한다. 신규는 `document_id` 없이 `expected_revision: 0`; 기존은 읽은 ID와 정확한 최신 content revision을 넣는다.

아래는 `document_import`의 `request` 예시다. 실제 `hello` 5바이트의 base64/digest에만 해당한다. 운영 원본은 같은 바이트에서 계산한 값으로 바꾼다. 예시 자체를 실제 출처 증거처럼 수입하지 않는다.

```json
{
  "schema_version": "1",
  "idempotency_key": "notes-import-1",
  "expected_revision": 0,
  "title": "회의 기록",
  "slug": "meeting-notes",
  "document_type": "original",
  "filename": "notes.md",
  "media_type": "text/markdown",
  "content_base64": "aGVsbG8=",
  "source_sha256": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
  "source_identity": "git:repository/notes.md",
  "collection_context": "Human-authorized upload from resolved repository"
}
```

작은 단일 파일의 준비 예시다. `AF_INPUT_FILE`은 확정 snapshot의 일반 파일, `AF_PAYLOAD_PART`는 원본 밖 새 private 파일이다. 기존 shell/Python을 사용하는 예시이며 새 배포 migration script가 아니다. 부모 경로 symlink·동시 변경은 inventory 단계에서 제외한다.

```sh
umask 077
python3 - <<'PY'
import os, pathlib, hashlib, base64, json
p = pathlib.Path(os.environ['AF_INPUT_FILE'])
if p.is_symlink() or not p.is_file():
    raise SystemExit('일반 파일을 지정하세요')
b = p.read_bytes()
if not 0 < len(b) <= 256 * 1024:
    raise SystemExit('staging upload 경로를 사용하세요')
with open(os.environ['AF_PAYLOAD_PART'], 'x', encoding='utf-8') as f:
    json.dump({'content_base64': base64.b64encode(b).decode(),
               'source_sha256': hashlib.sha256(b).hexdigest()}, f)
PY
```

생성 파일은 완성된 API payload가 아니다. metadata와 합친 후 허용 필드만 전송한다. `size_bytes`를 inline import에 추가하지 않는다. 민감한 base64를 콘솔에 출력하지 않는다.

### Native·큰 package staging

1. inline 한도는 256 KiB다. native 원본은 허용 MIME 그대로 보존한다. unsupported MIME/multipart는 원형 artifact bytes와 파일명/MIME/hash manifest를 담은 안전한 ZIP으로 표현할 수 있으나 변환 여부와 패키지 계약을 검토한다. PDF/DOCX/image text extraction을 제공한다고 가정하지 않는다.
2. 같은 `ImportMetadata`에서 `content_base64`를 빼고 정확한 `size_bytes`를 넣어 `document_prepare_upload`를 호출한다. 반환 `upload_id/path/method/header/capability`와 만료·크기·digest를 받는다. capability는 private 임시 파일에만 두고 일반 manifest/로그에는 넣지 않는다.
3. 확정된 동일 서버의 반환 상대 path로 raw bytes를 PUT한다. `/api/...`는 app 상대일 수 있으므로 확정 public base의 `/factory` 등 root prefix를 보존해 같은 origin URL을 만든다. MCP endpoint 뒤에 path를 붙이거나 object URL로 보내지 않는다. redirect는 금지한다. bearer와 `X-Document-Upload-Capability` 모두 필요하다. browser는 session+CSRF를 사용한다.
4. 아래 `AF_UPLOAD_URL`은 비밀 없는 확정 URL, `AF_UPLOAD_HEADERS`는 credential authority가 만든 0600 파일이다. 이 파일에 실제 Authorization와 upload capability header를 공급한다. 비밀을 shell argument/heredoc/prompt/tracked 파일로 쓰지 않는다. `-v`, trace, `-L`을 추가하지 않는다.

```sh
curl --fail --silent --show-error --request PUT \
  --header @"$AF_UPLOAD_HEADERS" --data-binary @"$AF_PACKAGE" \
  --output "$AF_UPLOAD_RESPONSE" "$AF_UPLOAD_URL"
```

5. 인증 MCP `document_finalize_upload`에 `request={"schema_version":"1","upload_id":"실제 반환 UUID"}`와 같은 tenant 인자를 보낸다. ack 불명확 시 정확히 같은 metadata로 prepare를 재시도한다. prepare는 15분 만료 갱신·capability 회전을 하므로 최신 capability를 쓴다. 같은 intent의 uploaded bytes는 보존된다. 필요할 때만 PUT하고 같은 upload ID를 finalize한다. 성공 finalize의 동일 retry는 만료 후에도 기존 receipt를 돌려준다.
6. [delivery guide](../../mcp/docs/cloud-documents.md)의 기본 upload 25 MiB/상한 128 MiB, expanded 64/256 MiB, member 16/64 MiB, entries 2048/8192, compression ratio 200/1000과 실제 `document_max_upload_bytes`, `DOCUMENT_PACKAGE_*` 설정을 대조한다. ingress body/시간/동시성, 메모리와 staging 총량 예산도 설정한다. ZIP은 안전한 NFC 상대 경로, link/special/collision/encryption 없음이 필요하다. 서버는 ZIP을 파일시스템에 풀지 않는다.

같은 key와 정확히 같은 요청은 원래 receipt로 복구한다. 어느 필드든 바뀌면 conflict다. 새 key는 기존 slug나 stale revision을 우회하지 못하며 삭제된 대상을 retry로 살리지 않는다. 충돌은 최신 revision/provenance를 읽고 의도된 새 revision인지 결정한 후 새 요청으로 처리한다. 불명확한 commit 뒤 staging object를 삭제하지 않는다.

### 완전한 명세 pair 게시

[Specification 계약](../skills/document/references/specification.md)과 [package validator](../../mcp/app/modules/document/package.py)를 따른다. 여섯 stable ID 각각 AI root 하나와 Human root 하나만 담은 ZIP을 만든다. reciprocal locator와 `SKILL.md`, Human `index.html/styles.css/app.js`, 내부 자산 전부를 유지한다. 실제 Git 저장소·검토된 commit과 inventory를 묶으며 dirty 소스를 다른 commit snapshot이라고 표기하지 않는다.

`SKILL.md` 먼저, 나머지 Markdown과 `agents/` YAML을 정렬해 전부 수록한다. `lang=ko`, reciprocal metadata, `data-ai-source/data-ai-sha256`, 연속 `data-source-lines/data-source-sha256`이 원천 모든 줄을 정확히 한 번 같은 순서·계층으로 대응해야 한다. frontmatter/YAML도 제외하지 않는다. coverage 뒤 독립 검토자가 한국어의 주장·명령·예외·관계·권한·완료 조건을 대조한다. 누락·요약·재배열·중복·오역은 게시 중단 사유다.

`pair` 필드는 `specification_id`, `ai_root`, `human_root`, `git_repository`, `git_commit`, `review`다. `review`는 `reviewer/evidence/authority_reference/ai_sha256/human_sha256/verdict`를 요구하고 verdict 값은 `aligned`다. 각 root의 모든 파일 상대 경로→파일 SHA-256 mapping을 Python `json.dumps(..., sort_keys=True, separators=(',', ':'))`의 기본 ASCII escaping으로 직렬화한 UTF-8 bytes의 SHA-256이 representation hash다. 검토 후 바이트가 바뀌면 다시 검토한다. 없는 reviewer/승인/attestation을 만들지 않는다. 의미 검토가 없으면 게시만 보류하고 소스와 준비 결과를 보존한다.

서버는 전체 pair를 고유 immutable object로 쓰고 readback hash를 비교한 뒤 revision/current pointer/index/idempotency receipt를 한 DB transaction으로 게시한다. object와 DB는 하나의 transaction이 아니다. 실패 시 이전 accepted pointer를 유지하고 orphan staging은 복구 증거로 보존한다. `review_attested`는 제출 검토 기록이며 자동 의미 수락이 아니다. metadata create 또는 한쪽 revision upload로 우회하지 않는다.

### 수락 대조·검색

receipt의 Document ID/revision을 manifest에 연결한다. `document_read`의 `get/revisions/provenance`로 identity/type/history/source를 대조하고 그 정확한 revision을 읽는다. `download`는 256 KiB 이하 base64다. 큰 것은 인증된 기존 revision download/브라우저 경로를 사용한다. package manifest/member/preview는 [실제 HTTP router](../../mcp/app/router/cloud_documents.py)의 revision-scoped 경로다. 가상의 MCP member 도구는 없다. GET은 session 권한 경로이므로 PUT의 bearer 지원을 모든 REST에 일반화하지 않는다.

독립 Verification이 accepted revision 전체 bytes·파일별 hash·representation hash·provenance·타입·source identity·history·object 참조를 source snapshot과 비교한다. 표본만으로 전체 migration을 완료 처리하지 않는다. 총 package/file/bytes와 제외·충돌 항목을 조정한다. 변하는 provider export는 같은 관측 시점 비교 또는 변환/provenance 차이를 설명해야 한다.

`document_search`의 request 예는 `{"schema_version":"1","query":"한국어 식별자","limit":20}`다. 필요한 특정 revision은 `document_index`로 색인한다. embedding 없이 현재 nondeleted revision의 제한된 lexical 결과를 확인한다. binary 추출 부재, chunk 경계 누락, bounded limit를 표시한다. 검색 hit·preview는 바이트나 의미 수락 증거를 대신하지 않는다.

## 5. Legacy gather를 connection·collection으로 전환

남아 있는 `skills/gather/assets/schema/sync.schema.json`은 legacy 목록 판독 근거로만 사용한다. 퇴역 후에는 보존된 commit/backup으로 읽고 runtime 의존성을 만들지 않는다. [cloud Selection](../../mcp/app/modules/integration/cloud_schemas.py)과 [수집 가이드](../../mcp/docs/cloud-integrations.md)가 새 계약이다.

legacy 선택마다 provider·계정·root/query/channel·recursion·기간·attachments·page/count/bytes·기존 cursor/결과·fidelity 제한을 기록한다. 같은 계정은 connection을 공유할 수 있지만 다른 선택은 각각 collection으로 만든다. 선택은 불변이고 변경 시 새 collection이 필요하다. local destination은 보내지 않고 확정 workspace Original로 resolve한다. legacy cursor를 API input으로 업로드하거나 공유 connection cursor 하나로 모든 선택을 합치지 않는다.

| 공급자 | 명시할 Selection | 권한·원본 보존·제한 |
| --- | --- | --- |
| Google Drive | `folder_id` 또는 `file_id` 하나, `recursive` | `https://www.googleapis.com/auth/drive.readonly`; binary 원형, Docs/Slides/Drawings PDF·Sheets XLSX는 변환 명시. unsupported native·shortcut 제한 보존 |
| Gmail | 비어 있지 않은 `query` 또는 승인된 `allow_all=true` | `https://www.googleapis.com/auth/gmail.readonly`; RFC message·첨부 원형, header/thread provenance. query를 전체 계정으로 넓히지 않음 |
| Slack | `channel_id`, 정확한 `channel_type`, 필요한 `oldest/latest` | 해당 `channels/groups/im/mpim:history`, 첨부 시 `files:read`; API evidence·file bytes. thread replies 미순회 제한 기록 |
| Notion | `page_id` | integration read-content와 페이지 공유 확인. page/block API·파일 원형. permission enumeration unsupported. hosted URL은 새 API로 갱신, temporary/private URL 제거 |
| Discord | `channel_id`, 필요 시 `before` 또는 `after` 하나 | bot VIEW_CHANNEL/READ_MESSAGE_HISTORY와 message-content intent 확인. 메시지·첨부; 빈 content를 완전 수집으로 해석하지 않음 |
| OneDrive | `item_id` 또는 상대 `path` 하나, `recursive`; 필요한 `drive_id/include_shared` | `Files.Read`; 공유/명시 drive는 승인된 `include_shared=true`와 `Files.Read.All`. refresh는 `offline_access` 명시. Graph 원형 bytes, remote-item 제한 보존 |

모든 selection에 `max_items/max_pages/max_bytes/attachments`를 명시한다. items/pages는 각각 1–1000, bytes는 최대 500,000,000이다. items는 반환 문서 수가 아니라 방문 폴더·선택 Notion page 등을 포함한 검사 entry 수다. metadata·retry·첨부도 byte 한도에 포함되고 source unit당 artifact는 최대 100개다. 공급자와 무관한 필드·임의 URL·cursor는 거부된다.

### 실제 인증 경로

인증된 서버 `GET /api/integration-providers`에서 실제 provider UUID를 찾고, session+CSRF와 `integration.manage`로 `POST /api/organizations/{organization_id}/workspaces/{workspace_id}/integrations`의 [ConnectionCreate](../../mcp/app/modules/integration/schemas.py)를 사용한다. 기존 목록과 계정 식별자를 먼저 대조한다. credential 없는 connection 준비와 실제 인증 완료를 구별한다.

OAuth는 광고된 `integration_oauth_begin(connection_id, scopes, organization_id, workspace_id)`와 같은 사용자/workspace에 묶인 callback의 `integration_oauth_complete(state, code, ...)`로 수행한다. 서버 설정은 `AF_GOOGLE_DRIVE_OAUTH_`, `AF_GMAIL_OAUTH_`, `AF_ONEDRIVE_OAUTH_`, `AF_SLACK_OAUTH_`, `AF_NOTION_OAUTH_` 각각의 `CLIENT_ID/CLIENT_SECRET/REDIRECT_URI`다. 비밀은 managed secret에서 공급한다. Google/Microsoft PKCE와 Slack/Notion confidential exchange, 동의 만료·single-use, provider denial·refresh 회전을 리허설한다. legacy REST begin이 state만 만들면 live exchange 완료 증거가 아니다.

Slack/Notion/Discord token은 보호된 secret-entry 경로에서 동일 `integration_token_set(connection_id, token, approved_scopes, ...)` 서비스를 호출하도록 한다. MCP token 인자는 client transcript에 남을 수 있으므로 일반 채팅·Agent 도구 transcript에 실제 token을 넣지 않는다. 최종 서버에 보호 UI/route와 log redaction이 없으면 해당 token 설정을 미완료로 기록하고 임시 route를 발명하지 않는다. 서버 `integration_encryption_key`/versioned SecretCipher만 persisted credential 권위다. 키 교체는 owning secret 인프라가 수행하며 legacy token/cache는 Document에 넣지 않는다.

`integration_inspect(connection_id, live=false)`는 cached 확인이다. `live=true`는 외부 계정 API 호출이므로 확정 계정·scope 권한하에 수행한다. requested scopes, observed grant와 시점, stale/unknown, account health, selection 접근을 따로 기록한다. identity 성공은 모든 selection 권한 증거가 아니다. 승인 범위를 넘는 실제 grant나 필수 grant 누락은 수집 차단 사유다.

### 시험 수집과 재시도

1. 승인된 작은 selection으로 `collection_create(request={connection_id,name,selection}, organization_id,workspace_id)`를 호출한다. create는 외부 I/O를 하지 않는다. 예를 들어 Gmail의 request는 아래 형태이며 UUID/query/한도는 실제 승인 값으로 치환한다.

```json
{
  "connection_id": "00000000-0000-4000-8000-000000000001",
  "name": "프로젝트 메일 시험 수집",
  "selection": {
    "query": "from:example@example.com after:2026/01/01",
    "max_items": 10,
    "max_pages": 2,
    "max_bytes": 5000000,
    "attachments": true
  }
}
```

2. `collection_start(collection_id, request_key, ...)`는 서버 job/Original 쓰기, 공급자 read API·rate limit·OAuth refresh 효과가 있다. 공급자 문서 수정/삭제는 하지 않지만 무효과 dry-run은 아니다. 승인된 시험 request key를 기록한다.
3. `collection_status(run_id, ...)`, `collection_results(run_id, ...)`에서 durable ID/revision/hash/제한을 수집한다. provider/connection/collection/source ID/selection/source metadata와 revision의 run·조회 시점을 원천 inventory와 비교한다. 하나의 source unit은 collection마다 하나의 Original이며 겹치는 collection은 의도적으로 별도 provenance를 갖는다.
4. native 한 파일은 직접 저장한다. multipart·현재 MIME 비허용 EML/XLSX·빈 bytes는 원형 artifact와 manifest를 가진 deterministic ZIP일 수 있다. ZIP digest뿐 아니라 member bytes/MIME/hash도 대조한다. 외부 source를 억지 Document 간 derivation으로 만들지 않는다.
5. `bounded`는 공급자 끝 전에 한도에 도달했다는 뜻이며 전체 mirror가 아니다. provider exhaustion을 관측한 결과와 구별한다. 같은 시점·범위의 count/hash/provenance를 조정한다. 새 key는 같은 한도로 처음부터 scan하며 한도 이후 continuation이 아니다.
6. start ack가 불명확하면 같은 key로 같은 run/job을 회수한다. worker는 source 저장 후 checkpoint, page 전체 저장 후 cursor를 전진시킨다. stable slug와 latest content/provenance hash로 commit 후 checkpoint 전 실패를 복구해야 한다. cursor expiry·권한 거부는 선택 확대나 새 run 자동 생성 사유가 아니다.
7. `collection_cancel(run_id, ...)`는 협력 취소다. HTTP 시도/chunk/대기/source 저장 경계에서 확인하며 이미 진행 중 저장은 끝날 수 있다. accepted Original을 제거하지 않는다. HTTP retry 최대 3회와 worker budget을 구별하고 Retry-After보다 이른 retry 금지, 최종 dead/failed와 마지막 checkpoint를 확인한다. crash 시 미정산 byte 예약으로 한도가 보수적으로 소진될 수 있다. 이를 0으로 고쳐 재개하지 않는다.

여섯 공급자의 실제 OAuth/token·선택 접근·refresh/revocation·rate limit·취소·native/첨부·egress는 각 실계정 증거가 필요하다. mock API 테스트는 대체 증거가 아니다. Notion 외부 파일과 Graph/CDN redirect의 host/IP/TLS pinning, private/metadata 주소 egress 차단을 배포 transport에서 확인한다. provider token을 CDN에 전달하거나 임의 URL fetch를 열지 않는다. 일반 비밀 없는 외부 URL의 의미 있는 query는 provenance에 보존하고 서명·access/refresh token query는 제거한다.

## 6. 선택적 로컬 reporting 연결

정확한 소스는 [exec.py](../skills/agent/scripts/exec.py), [loop.py](../skills/agent/scripts/loop.py), [cloud_reporting.py](../skills/agent/runtime/cloud_reporting.py)다. 작성 시 실제 옵션은 `exec.py submit|send --reporting-config`, 선택적 `--reporting-loop-id`; loop start는 `--work-reporting-config`, `--verification-reporting-config`다. 병행 계약 문서에 `--reporting-config-file` 표기가 있으면 소스와 충돌하므로 그대로 실행하지 않는다. 최종 설치된 `exec.py submit --help`, `exec.py send --help`, `loop.py start --help`와 유지 문서가 일치해야 release 가능하다. 없는 flag를 만들지 않는다.

아래는 치환할 구성 형태이며 예시 UUID는 기본값이 아니다. 실행 사용자 소유, 0600 이하, 일반 파일, 안전한 부모 경로, symlink/traversal 없음이 필요하다. 설정과 credential은 tracked 파일·실행 evidence 밖 private 경로에 둔다.

```json
{
  "version": 1,
  "endpoint": "https://recipient.example/factory/mcp/",
  "recipient_id": "accepted-recipient-identity",
  "project_ref": "accepted-project-identity",
  "organization_id": "11111111-1111-4111-8111-111111111111",
  "workspace_id": "22222222-2222-4222-8222-222222222222",
  "reporter_user_id": "33333333-3333-4333-8333-333333333333",
  "cloud_agent_id": "44444444-4444-4444-8444-444444444444",
  "credential_file": "/absolute/owning-credential-store/reporting.json",
  "allow_loopback_http": false
}
```

credential 파일의 정확한 필드는 `version: 1`, `target`, `token`이다. target은 설정의 `endpoint/recipient_id/organization_id/workspace_id/reporter_user_id/cloud_agent_id`를 정확히 반복한다. 실제 `afm_...` token은 credential authority가 공급하며 어떤 `.agent-factory` 경로 아래에도 둘 수 없다. token은 argv·환경 덤프·설정·run·outbox·receipt에 복사하지 않는다. token bytes만 같은 owning reference에서 교체하고 target binding은 유지한다.

실제 cloud ReportAgent가 해당 reporting-user 소유로 이미 등록되어 있어야 한다. adapter는 Agent를 자동 생성/편집하지 않는다. 실제 Codex session이 durable해진 뒤 run당 새 cloud task UUID를 만든다. 같은 session의 새 run은 새 task이고 동일 run의 reconnect/retry는 같은 task다. 실제 `agent:read`+`workspace.read`, `agent:report`+`workspace.manage`, workspace-scoped endpoint의 기존 `workspace:read`를 확인한다. Agent owner 조회는 현재 1000개 snapshot 한도가 있으므로 밖에 있는 Agent의 ownership을 임의로 인정하지 않는다.

opt-in flag가 없는 새 turn은 로컬로 동작하고 이전 turn의 recipient를 상속하지 않는다. Main이 이미 승인된 submit/send에 config를 추가한다. reporting 시험을 위해 execution을 다시 제출하지 않는다. 기존 opted-in run은 다음으로 확인·전달한다. cwd는 실제 plugin 설치 루트이며 설치 locator를 먼저 resolve한다.

```sh
python3 skills/agent/scripts/exec.py status --project-root "$AF_PROJECT" --agent "$AF_AGENT" --run-id "$AF_RUN"
python3 skills/agent/scripts/exec.py reporting-deliver --project-root "$AF_PROJECT" --agent "$AF_AGENT" --run-id "$AF_RUN"
```

delivery는 선택된 recipient에 대한 외부 write 권한하에 수행한다. AI turn·submit·`agent_run_submit`을 호출하지 않는다. extension의 기존 Agent 경로·run layout·명령을 유지하고 opt-in 시 이 flag와 전달 명령만 연결한다.

`reporting.json`, `reporting-receipts/`, `reporting-error.json`, semantic intent/proof를 백업한다. immutable command/key/expected revision/binding을 전송 전에 durable하게 기록하고 ack를 durable하게 남긴 뒤 완료 처리한다. lost ack는 같은 명령/key로 전달만 재시도한다. recipient/user/target 변경·revision conflict를 새 key나 outbox 편집으로 우회하지 않는다. pending cap은 512개이며 가득 차도 기존 항목을 먼저 drain할 수 있다.

`reporting_capture_pending`, `reporting_semantic_pending`, `semanticPending`, pending 수가 남으면 결과/receipt identity와 durable intent를 보존하고 전달/capture만 재시도한다. 파일 교체·수정, credential binding 불일치, 거부, timeout, clock skew는 고정된 비밀 없는 진단으로 남는다. 오래된 completed run의 exit/status만으로 의미 결과를 재구성하지 않는다. 결과 hash는 explicit delivery에서 읽으며 heartbeat/termination hook는 본문·receipt·네트워크에 대기하지 않는다.

실제 observed time의 `process_alive/process_exited/unreachable`와 receipt time을 구별한다. 오래된 heartbeat 재전송은 현재 alive 증거가 아니다. cloud semantic completed는 Verification pass나 loop END가 아니다. local validated receipt와 loop만 그 권위를 갖는다. cloud read/search로 execution을 취소·재개하지 않는다. transport는 MCP 2026-07-28 per-request 방식이다. 정확한 endpoint/TLS·무redirect·설치 SDK 호환성을 검증한다. HTTP는 명시 허용된 literal loopback 시험만 가능하다. send별 전체 5초와 socket 2초 제한, delivery 호출 약 10–15초 경계에서도 pending과 local 실행 독립성을 확인한다.

## 7. 실제 전환과 코드 퇴역

[운영 절차](../../mcp/config/operations.md), [release.sh](../../mcp/deploy/release.sh), [production compose](../../mcp/deploy/compose.production.yaml)를 읽고 최종 image·대상 설정을 고정한다. release.sh는 migration/API/worker/scheduler/proxy를 실제 변경하므로 검증 명령처럼 실행하지 않는다. 승인된 one-shot migration 후 DB readiness, API, worker 순서로 진행하고 Beat는 정확히 하나 유지한다. public prefix 포함 `/factory/live`, `/factory/ready`, 인증 MCP·Workspace를 확인한다. base가 다르면 확정 배포 설정을 따른다.

1. 신규 기능 활성화와 old script 퇴역 전에 복원 리허설·최종 설치 통합 Verification pass, 미해결 충돌, 정확한 변경 권한·backup set을 검토한다.
2. legacy writer 정지 후 최종 delta inventory를 만든다. source/target revision 변화는 요청을 재검토하며 이미 accepted cloud revision을 옛 snapshot으로 덮지 않는다.
3. 전체 대상 accepted bytes/revision/provenance/pair를 대조하고 여섯 계정별 trial·제한을 기록한다. 미수집/비권한 selection은 미완료다.
4. 새 Document/search/collection/reporting 작업을 cloud로 지정하고 확장 로컬 실행을 유지한다. 제한된 대상부터 활성화하고 명시한 관측 기준 충족 후 범위를 늘린다. 임의 이중 writer를 켜지 않는다.
5. 검증된 대체 경로에 따라 [retirement 변경](cloud-retirement.md)은 catalog/SQL·legacy gather/document/tool domain 실행 파일을 퇴역하고 재사용 Document 템플릿을 MCP 패키지의 인증된 document_template 전달로 옮겼다. `exec.py`, `loop.py`, 최소 runtime support와 여섯 Human 독립 표현 자원은 유지한다. 최종 package/resource·extension 호환과 변경된 한국어 쌍은 독립 Verification에서 확인한다. 기존 사용자 데이터는 삭제하지 않는다.
6. 전환 시각·source fence·마지막 old/첫 new revision·release digest·활성 tenant/collection·pending 보고·미완료 항목·독립 receipt를 기록한다. **코드 퇴역 성공 후에도 Original, sync 설정, catalog, runtime 복구 기록, 백업은 별도 삭제 권한 없이는 그대로 보존한다.**

## 8. 실패별 복구와 되돌림

| 관측 | 조치 | 금지되는 복구 |
| --- | --- | --- |
| import/PUT/finalize ack 불명확 | 같은 tenant/key/metadata/upload ID로 조회·retry, accepted revision/receipt/object digest 대조 | staging 삭제, 새 key 강제 덮기, accepted pointer 되감기 |
| stale revision/slug/review conflict | 원천·대상 revision과 review를 보존하고 의도 결정 후 새 요청 | revision 임의 증가, fake aligned attestation |
| object readback 불일치 | 게시 중단, key/version·DB 참조 격리 조사, 정상 이전 게시 유지 | hash 재기록으로 정상화, 최신 object 삭제 |
| collection crash/cancel | 같은 run/key의 checkpoint/job/source mapping부터 읽고 복구 | Original 삭제, byte 예약/cursor 초기화, 새 scan을 continuation으로 표기 |
| reporting 유실/충돌 | immutable outbox/ack/binding·local receipt 보존, 전달만 복구 | execution replay, cloud status로 local END 설정 |
| 새 앱 오류 | 신규 쓰기/수집을 제한하고 schema 호환을 증명한 이전 image로만 rollback; 새 accepted data 보존 | production blind downgrade/restore, 이전 앱을 미검증 새 schema에 연결 |

복원 리허설에서는 격리 DB/object namespace와 네트워크 차단으로 worker/scheduler/outbox가 provider·production recipient에 보내지 못하게 한다. 필요한 암호화 키 버전과 credential 참조의 복구 가능성을 확인하되 운영 비밀은 로그에 출력하지 않는다. backup 시점 DB가 참조할 immutable object 버전을 먼저 복원·확인하고 같은 backup set의 DB를 별도 인스턴스에 복원한다. DB를 먼저 읽어 참조 inventory를 만드는 경우에도 object 전체 대조 전 writer는 열지 않는다. orphan object는 보존한다. DB current/revision/receipt/RLS/키 버전 검사 뒤 호환 앱의 읽기, 이후 격리 쓰기·실패 복구를 시험한다.

실제 사고에서는 최신 accepted writes와 audit/receipt를 먼저 보호한다. 옛 dump를 production에 복원하면 백업 이후 수락 데이터가 사라지므로 직접 덮지 않는다. 별도 환경에서 PITR/추가 immutable object/receipt를 조정해 손실 범위를 산정하고 roll-forward 또는 검증된 복원 전환을 선택한다. DB/object 시점이 맞지 않으면 기능을 닫아 두고 참조 누락을 해소한다. downgrade는 복원 사본 시험·최신 데이터 보존 방법·해당 파괴적 효과의 별도 Human 승인 없이는 하지 않는다. 로컬 session snapshot 복원은 과거 process가 살아 있다는 판단이나 새 turn 자동 실행 권한이 아니다.

## 9. 1–13단계 수락 증거 대장

아래는 정확한 기존 독립 Verification 결과·receipt에 근거한 코드/격리 리허설 기록이다. 이 retirement Work의 통과 주장이 아니다. 실계정·운영 배포·데이터 전환은 별도 기록한다. 과거 runtime-error loop를 임의 END로 바꾸지 않는다.

- Platform: `run-20260905T175343294928Z-6b638ce3`, revised Work `run-20260905T174955804567Z-9c23782b`, request SHA-256 `e077eac51fb0b98510854d86d753bfe99cc24a24bc5a18a1fca62ebf4a428da4`, pass. 14 realDB integration + 22 shared + 2 independent races; 이전 175 domain·wheel·실제 worker kill/restart·인증 preview 근거 유지. 유지되는 [platform guide](../../mcp/docs/cloud-platform.md)와 [integration tests](../../mcp/tests/test_cloud_platform_integration.py)가 재현 경로다. Docker 권한이 없으면 해당 근거의 rootless private PostgreSQL 격리 대안을 쓸 수 있으며 특권 Docker를 필수로 요구하지 않는다.
- Contracts: `run-20260905T175258360448Z-5806adfb`, revised Work `run-20260905T174802685875Z-815b6fdf`, request SHA-256 `5b9901c64ef33b3ebe540c24928315b27aaacd88f880946d035e24dea086ad51`, pass. 49 sources 전체 한국어·6 validators·quick validation·9 diagrams/91 relationships desktop/mobile/JS-disabled/sandbox. 현재 퇴역에 따른 쌍 변경은 새 독립 검토 대상이다.
- Local reporting: `run-20260905T170937643006Z-a0b4cd52`, pass, 97 tests와 추가 독립 hook probe. [로컬 tests](../tests/test_agent_cloud_reporting.py) 유지.
- Runbook: `run-20260905T174238670396Z-463beb30`, revised Work `run-20260905T173954081246Z-e0bc16d4`, pass. 기존 backup/config/schema와 4 connections + headroom 지침은 유지하며 현재 상태/link 변경은 retirement 검토에 포함한다.

| 단계 | 유지되는 구현·테스트·문서 | 현재 근거와 최종 수락 증거 |
| --- | --- | --- |
| 1 계약·pair | [Skills](../skills/), [Human 소스](../.agent-factory/document/specification/), [명세 계약](../skills/document/references/specification.md) | Contracts 독립 pass; 이번 퇴역의 의미·소스맵 변경은 재검토 대기. |
| 2 CRUD·upload | [guide](../../mcp/docs/cloud-documents.md), [base tests](../../mcp/tests/test_cloud_documents.py), [delivery tests](../../mcp/tests/test_cloud_document_delivery.py), [HTTP tests](../../mcp/tests/test_cloud_document_delivery_http.py) | Platform 실제 인증 HTTP/MCP·대형 native/pair 전달·격리 preview 통과. 현재 template 전달은 독립 검증 대기. |
| 3 scope·auth | [authorization](../../mcp/config/authorization.md), [MCP auth](../../mcp/app/mcp/auth.py), [server](../../mcp/app/mcp/server.py) | Platform scope·RBAC·RLS·token 비확대·교차 Workspace 거부 통과. 운영 tenant/계정 설정은 미실행. |
| 4 legacy import | [importer](../../mcp/app/modules/document/legacy_import.py), [legacy tests](../../mcp/tests/test_legacy_document_import.py), [cloud service](../../mcp/app/modules/document/cloud_service.py) | Domain 및 platform 격리 import/replay/conflict·바이트 근거 유지. 실제 사용자 전체 데이터 가져오기는 미실행. |
| 5 검색 | [Document guide](../../mcp/docs/cloud-documents.md), [report search](../../mcp/app/modules/reporting/search.py), [tests](../../mcp/tests/test_cloud_reporting.py) | Platform 실제 DB 검색 및 domain 한글/identifier·scoped literal retrieval 통과. 실제 사용자 데이터 색인은 미실행. |
| 6 collection 설정 | [schemas](../../mcp/app/modules/integration/cloud_schemas.py), [collection tests](../../mcp/tests/test_cloud_integrations_collections.py) | Domain 및 platform의 immutable selection·cursor·run persistence·중복/실패 복구 통과. |
| 7 공급자 인증 | [guide](../../mcp/docs/cloud-integrations.md), [MCP integration](../../mcp/app/mcp/integrations.py) | Platform callback·현재 권한 및 domain 암호화/refresh·mock/TLS 근거 통과. 실계정 인증은 미실행. |
| 8 Worker | [handler](../../mcp/app/worker/integration_handlers.py), [tasks](../../mcp/app/worker/tasks.py), [policy](../../mcp/config/workers.md) | Platform 실제 Job 권위/RLS·동시성·cancel/retry/recovery와 유지된 OS kill/restart 근거 통과. 운영 pool 크기는 대상별 별도 리허설. |
| 9 여섯 공급자 | [provider tests](../../mcp/tests/test_cloud_integrations_providers.py), [guide](../../mcp/docs/cloud-integrations.md) | 여섯 공급자 API shape·native fidelity·redaction·bounds·exhaustion fixture 근거 유지. 실계정 수집은 미실행. |
| 10 원자적 pair 게시 | [pair 계약](../skills/document/references/specification.md), [tests](../../mcp/tests/test_cloud_documents.py), [delivery](../../mcp/app/modules/document/delivery_service.py) | Contracts 의미 검토 및 platform의 pair 실패 시 prior publication 보존 통과. 이번 쌍 revision의 의미 검토·게시 승인은 별도. |
| 11 reporting | [runtime](../skills/agent/runtime/cloud_reporting.py), [local tests](../tests/test_agent_cloud_reporting.py), [recipient tests](../../mcp/tests/test_cloud_reporting.py), [guide](../../mcp/docs/cloud-reporting.md) | Local 97 tests+독립 probe pass; platform 실제 DB/auth/transport/reporting 근거 유지. 선택적 실제 recipient 설정/전달은 미실행. |
| 12 퇴역 | [Agent](../skills/agent/SKILL.md), [README](../README.md), [layout](../skills/convention/references/directory-structure.md) | 소스 퇴역·MCP template 이동·테스트 소유권 갱신 구현. 최종 retirement Verification 대기. 사용자 원본 삭제 없음. |
| 13 release·복구 | [deployment tests](../../mcp/tests/test_deployment.py), [migration tests](../../mcp/tests/integration/test_migrations.py), [browser](../../mcp/tests/browser/cloud-document-delivery.cjs), [operations](../../mcp/config/operations.md), 이 문서 | Schema 0021 단일 head와 격리 upgrade/downgrade/re-upgrade, wheel/resource 및 통합 리허설 근거 유지. 최종 retirement 검증과 운영 별도 backup 복원·배포·실전환은 미실행. |

코드/unit 근거, 격리 통합 pass, 실제 배포·수집·이전 결과를 각각 기록한다. 기존 platform/contracts pass와 이번 retirement 검증 대기를 구별하고 운영 증거가 없는 실제 작업을 완료로 표시하지 않는다. 선택적 운영 대상 provisioning은 코드 1–13 수락의 추가 blocker가 아니다. 남은 Human-owned 결정은 실제 대상/계정·허용 scope·충돌 의도·의미 수락·보존/삭제 정책·변경 창이며, 이미 승인된 클라우드 아키텍처를 다시 여는 항목은 아니다.
