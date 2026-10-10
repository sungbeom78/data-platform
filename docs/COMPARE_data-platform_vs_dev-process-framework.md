# 데이터 모델링 시스템 비교 — data-platform v2 ↔ dev-process-framework

- 작성: 2026-10-09 · 대상: `devForDevSystem/data-platform`(이하 **DP**) ↔ `dev-process-framework-main.zip`(이하 **DPF**, main 브랜치)
- DPF 는 **읽기만** 했다(공유 서브모듈 규칙). 아래 개선안은 제안이며, 실제 수정은 지시가 있을 때만 한다.
- 실제로 돌려본 것
  - DPF `tests/test_data_modeling.py`·`test_data_stance.py`: 최신 bomiyang-glossary(2026-10-08, 영역 기능 포함)를 넣었을 때 **전부 통과**(10 + 6)
  - DPF 의 공통 사전 검사(`model_glossary`, 영역 모드 `[general, data]`)를 **DP 의 모델에** 돌림 → 결과는 3장
  - DP 의 용어 어댑터를 최신 bomiyang-glossary 에 연결해 해석 결과 확인 → 결과는 3장

- **진행 현황 (2026-10-10, data-platform 2.1):** 4장 P0-4(권한 범위)·P0-5(Windows 인코딩)·P1-6(승인 증거) **완료** — 종단 테스트 20개·v1 회귀 통과. 나머지(P0-1~3 정본 일원화·용어 어댑터 교체·공통 스키마 단어 정리, DPF 쪽 전부)는 미진행.

---

## 1. 한 줄 요약

| | DPF (dev-process-framework) | DP (data-platform v2) |
|---|---|---|
| 정체성 | **개발 과정을 통제**하는 프레임워크 — 승인 게이트·증거·검사·공통 사전 | 데이터를 **찾고·넣고·지키고·꺼내는** 실행 시스템 |
| 데이터 모델링 | `sk-dev-data-modeling` = DP 의 data-modeling v2 와 **스크립트가 같은 파일**(export_all·check_dictionary·validate_pg 바이트 동일) + 프레임워크 연동 절 | 같은 스킬 + 적재·개인정보·권한·API 런타임 |
| 강점 | 용어 일원화(영역·뜻·R2/R3 규칙, 승인 인용, 사전 git 커밋), 논리/물리 승인 기록, 데이터 입장(stance), 산출물 재생성 일치 검사, Windows 대응 | 실제 DB 운영 기능: 적재·PI 암호화·등급×분류 권한(DB 롤)·조회 API·레이크 |
| 약점 | 스킬 문서가 **DPF 에 없는 DP 런타임을 가리킴**(끊긴 참조), 마이그레이션 도구 없음 | 용어 처리가 공통 사전 규칙과 **충돌**, 승인 증거 없음, 정본이 git 밖, 공유 DB 에서 권한 동기화 범위 과다 |

**결론:** 두 시스템은 경쟁 관계가 아니라 **층이 다르다**. DPF 가 "어떻게 만들고 검증하나"를, DP 가 "만든 데이터를 어떻게 운영하나"를 맡는다. 다만 지금은 **데이터 모델링 스킬이 두 곳에 복사돼 이미 갈라지기 시작했고**(2-3), DP 의 용어 처리가 DPF 규칙을 따르지 않는다(3장). 정본 하나 + 연결부 정리가 가장 큰 개선이다.

---

## 2. 항목별 비교

### 2-1. 기능 범위

| 영역 | DPF | DP |
|---|---|---|
| 개념→논리→물리, model.json 정본, DDL/.dbm/xlsx | ✅ (같은 스크립트) | ✅ |
| 확인 게이트 | ✅ 논리 승인 `model-approve --stage logical --quote` 기록이 **없으면 완료 불가**, 물리 생성 자동 승인 금지 | △ SKILL 문장으로만 안내, 적재는 `approved: true` 플래그(누가·무엇에 동의했는지 기록 없음) |
| 공통 용어 사전 | ✅ `model-glossary` 대조표(ok/단어·약어·복합어 추가/충돌/R2/영역 약어) → 승인 인용 → GlossaryWriter → **사전 커밋·리비전 고정** | △ words.json 직접 읽기 + GlossaryWriter 등록만. 영역·뜻(senses)·금지어·충돌 판정 없음 |
| 검증 | ✅ `verify`: model_dictionary · model_glossary · model_export(커밋 산출물 = 재생성 결과) · ddl_postgres(파이썬, Windows 포함) · data_stance · encoding | ✅ 회귀(v1 바이트 동일) + e2e 17개(실 Postgres) — 단 프레임워크 증거로 남지 않음 |
| 데이터 입장(none/owned/external)·역설계·마이그레이션 지침 | ✅ (지침·탐지) — 마이그레이션 **도구는 없음** | ❌ |
| 공공데이터 검색 / 파일·URL 적재 / 대용량 레이크 | ❌ | ✅ |
| 개인정보 pi 스키마 + AES-128/HMAC/argon2 + 키 교체 | 모델 옵션만(스크립트) — 런타임 없음 | ✅ |
| 등급×분류 접근정책 → DB 롤 강제 | 모델 옵션만(`access_policies` → `meta.object_policy` 가 있어야 동작) | ✅ |
| 조회 API(등록 쿼리·사용권한·API 키) | ❌ | ✅ |
| 사용설명서 | ✅ `sk-dev-user-manual`(HTML, 비전공자/전공자) | ❌ README 뿐 |

### 2-2. 품질 장치

| 장치 | DPF | DP |
|---|---|---|
| 작업 상태·인수인계 | task_state·handoff·final_report(JSON+MD) | 없음 |
| 실패 복구 | sk-mgm-failure-recovery(재시도 예산) | 없음 |
| 선행 사례 확인 | sk-dev-prior-art-check | 없음 |
| 배포 | `tools/package_skill.py` → 단독 zip(테스트로 구조 검증) | 손으로 만든 zip 2개(plugin·단독 스킬) |
| 라이선스 | Proprietary / All rights reserved | 미표기 |

### 2-3. 이미 생긴 차이(드리프트) — 같은 스킬, 다른 예제

DPF 는 학사 예제의 단어를 공통 사전에 맞게 고쳤고, DP 는 옛 단어 그대로다.

| 단어 | DP (옛) | DPF (공통 사전 기준) | 이유 |
|---|---|---|---|
| 개인정보 | personal_**information** | personal_**info** | information 미등록 |
| updated_at 의 한글 | 수정 | **갱신** | '수정'은 공통 사전에서 correction |
| 여부(yn) full | yes_no | **yn** | yn 이 이미 단어 |
| 시각(at) full | timestamp | **time** | '시각'은 공통 사전에서 time |

→ 스크립트는 같아도 **예제·단어가 벌써 갈라졌다.** 지금 DP 의 단독 배포 zip(`data-modeling-skill-v2.zip`)은 DPF 기준으로 보면 낡은 예제를 담고 있다.

---

## 3. 실측 — DP 모델을 DPF 공통 사전 규칙으로 검사

### 3-1. DP 공통 스키마 모델(`platform_model.json`, 17 테이블)
`model_glossary` 결과: **실패** — 대조 76건 중 있음 30 / 등록 대상 36 / 충돌 1 / **R2 위반 9**, 사전에서 풀리지 않는 물리명 50개.

| DP 단어 | 공통 사전 상태 | 권장 조치 |
|---|---|---|
| expire(만료) | '만료' = expires | full 을 expires 로 |
| minimum(최소) / min | '최소' = min | full 을 min 으로 |
| definition(정의) / def | '정의' = def | full 을 def 로 |
| provider(제공) | '제공' = serve | 한글명을 '제공기관'으로 구분 |
| job(작업) | '작업' = task, work | full 을 task 로(또는 한글 '적재작업') |
| admin(관리자) | '관리자' = mgr | full 을 mgr 로(또는 한글 '관리권한') |
| rank(순위) | '순위' = ranking | full 을 ranking 으로 |
| updated(수정) | '수정' = correction | 한글 '갱신' |
| timestamp(시각) / at | '시각' = time, at = active_trade | full time + data 영역 약어 at |
| yes_no / yn | yn 이 이미 단어 | full yn |
| millisecond / ms | ms = market_strength | data 영역 약어 ms |

### 3-2. DP 용어 어댑터(`dataplatform.glossary`)를 최신 사전에 연결한 결과
- 단어 999개를 읽지만 **영역(areas.json)·뜻(senses)·금지어(banned.json)를 무시**한다.
- 내장 분류어/구조어가 사전보다 **먼저 등록돼 공통 사전 뜻을 가린다**: `no`→번호, `at`→시각, `yn`→yes_no, `수정`→updated. 공통 사전에서는 각각 금지·active_trade·yn(예/아니오)·correction 이다. 충돌을 **경고 없이 자기 뜻으로 덮는다.**
- `account` 의 한글을 `lang.ko`(계좌)로만 읽어, 영역별 뜻(계정 등)을 모른다.
- 등록 시 영역·뜻을 넣지 않고, 사전 git 커밋·`generate_glossary.py generate`·승인 근거가 없다.

→ DP 로 만든 테이블 이름은 DPF 의 `identifier_audit`·`model_glossary` 를 통과하지 못한다. **용어는 DPF 쪽 구현으로 일원화**해야 한다.

---

## 4. DP(data-platform)에 필요한 개선

### P0 — 먼저 고칠 것
1. **데이터 모델링 스킬 정본을 DPF 로 일원화** — DP 의 `skills/data-modeling` 은 DPF `skills/sk-dev-data-modeling` 을 패키징해 받는다(`package_skill.py` 확장 또는 빌드 시 복사). DP 가 스킬을 따로 고치지 않는다. 지금 생긴 예제 드리프트(2-3)를 이걸로 해소.
2. **용어 어댑터 교체** — `BomiyangGlossary` 를 DPF 의 `devprocess.glossary`/`datamodel.compare` 호출로 바꾼다(영역·뜻·R2/R3·금지어·승인 인용·사전 커밋). DPF 가 없을 때만 지금의 meta 모드로 대체한다. 내장 분류어가 사전 뜻을 덮는 동작은 제거한다.
3. **공통 스키마 단어 정리** — 3-1 표의 11개를 고쳐 `platform_model.json` 이 `model_glossary` 를 통과하게 한다. 테이블·컬럼 물리명이 바뀌는 항목(예: `min_grade_cd`·`admin_yn`)은 DB 마이그레이션을 같이 만든다.
4. **권한 동기화 범위 제한** — 지금 `sync` 는 시스템 스키마를 뺀 **DB 의 모든 테이블**에 `REVOKE ALL FROM PUBLIC` 과 `dp_open` 권한 부여를 한다. 다른 앱과 함께 쓰는 DB 에서는 그 앱의 권한을 건드린다. 설정에 `access.managed_schemas`(허용 목록)를 두고 그 안에서만 동작하게 한다.
5. **Windows 인코딩** — `ingest/load.py` 의 `_run` 과 `glossary.register` 의 `subprocess.run(text=True)` 에 `encoding="utf-8", errors="replace"` 를 넣는다. 지금은 한글 출력에서 cp949 디코딩 오류가 날 수 있다(DPF 에는 Windows 인코딩 테스트가 있다). `validate_pg.sh` 는 bash 전용이므로 DPF 의 파이썬 `ddl_postgres` 를 쓴다.

### P1
6. **승인 증거** — `ingest apply` 는 사용자 답 인용(`--approval-quote`)을 필수로 받아 `ingest.job`·`sec.audit_log` 에 남긴다. 신규 테이블 생성은 DPF 의 물리 생성 게이트(`model-approve --stage physical`)와 같은 형식을 쓴다.
7. **정본을 git 안으로** — 적재로 만든 model.json 이 지금은 `work_dir/models/<table>/`(임시)에 생긴다. 프로젝트의 `db/model.json`(스키마 단위로 합침)에 반영해, DPF 의 `model_export`·`ddl_postgres`·`data_stance(owned)` 가 그대로 검사하게 한다.
8. **스키마 변경 = 마이그레이션** — 기존 테이블에 컬럼이 늘거나 타입이 바뀌면 지금은 apply 가 실패하고 끝난다. model.json 비교 → `ALTER` 마이그레이션을 만드는 기능을 DPF 공용 도구로 만들어 쓴다(5장 P1-5).
9. **DPF 검사에 연결** — DP 의 e2e 테스트를 `check_commands.unit_or_regression` 에 등록하고, 운영 검사 두 개를 추가한다: `pi_plain_scan`(pi 스키마 밖에 개인정보 의심 컬럼이 평문으로 있는지), `access_sync_dryrun`(정책과 실제 GRANT 차이).
10. **사용설명서** — `sk-dev-user-manual` 로 비전공자용(설치→계정→적재→API 호출)과 전공자용(스키마·키·롤·운영)을 만든다.

### P2
11. 레이크 접근 통제가 CLI `--as` 의 문자열 포함 검사뿐이다 → 데이터셋 이름을 파싱해 정책 판정, API 로 열 때는 같은 SET ROLE 체계 대신 DuckDB 앞단 정책 검사.
12. API 운영 보강: 연결 풀, 호출 한도(rate limit), 토큰 폐기 목록, CORS 설정.
13. 설정 파일 권한(600) 을 로딩 시 점검·경고, 키를 환경변수/비밀 저장소로 넣는 옵션.
14. 라이선스 표기(DPF 와 같은 정책인지 결정).

---

## 5. DPF(dev-process-framework)에 필요한 개선

### P0
1. **끊긴 참조 정리** — `sk-dev-data-modeling/SKILL.md` 의 3-1·4-1·"data-platform 묶음" 절, `examples/acad_platform`, `access_policies` 가 DPF 에 없는 것들을 가리킨다: `python -m dataplatform`, data-search/ingest/governance/api 스킬, `meta.object_policy`, `dataplatform.crypto`. 둘 중 하나를 고른다.
   - (a) data-platform 을 DPF 의 구성요소로 편입(`catalog/components.yaml` 에 `pl_data_platform`, 런타임은 DPF 정책·검사와 연결)
   - (b) 해당 절을 "data-platform 이 설치된 경우" 조건부로 바꾸고, 단독 배포 zip 에서는 빼거나 표시
   이 상태로는 `package_skill.py` 가 만든 수강생용 zip 에도 끊긴 안내가 그대로 들어간다.
2. **검사 스크립트 하나로** — 스킬의 `validate_pg.sh`(bash 전용)와 프레임워크의 `ddl_postgres`(파이썬, Windows 대응)가 같은 일을 따로 한다. 파이썬 구현을 스킬 `scripts/validate_pg.py` 로 옮기고, 프레임워크 검사는 그것을 호출하게 한다(단독 사용자도 Windows 에서 검증 가능).

### P1
3. **엑셀 정의서도 일치 검사** — `model_export` 는 커밋된 DDL·.dbm 만 재생성 결과와 비교한다. 커밋된 `04_table_spec.xlsx` 도 셀 값 단위로 비교한다(바이트는 생성 시각 때문에 매번 다르다).
4. **`data` 영역 기본값** — `data_model.stance: owned` 인데 `glossary.areas` 가 없으면 분류어 충돌(no·at·yn)이 경고로만 끝난다. owned 프로젝트의 기본 영역을 `[general, data]` 로 하거나, 영역이 없으면 안내를 띄운다.
5. **마이그레이션 도구** — SKILL 은 "개선은 마이그레이션으로"라고 요구하지만 도구가 없다. `model-diff`(git 이전 정본 ↔ 현재 정본 → `ALTER` 스크립트 + 위험 표시: 컬럼 삭제·타입 축소·NOT NULL 추가)와, owned 프로젝트에서 정본이 바뀌었는데 마이그레이션이 없으면 실패하는 검사를 추가한다. DP 의 적재 append 에도 그대로 쓴다.
6. **acad_platform 예제 스모크 테스트** — 개인정보 컬럼이 bytea 라 학사 스모크를 그대로 못 쓴다. 암호문 자리값(`'\x01…'::bytea`)으로 업무 규칙(중복 수강·CASCADE·pi 스키마 분리)을 확인하는 `smoke_test.sql` 을 추가한다.
7. **데이터 운영 작업 유형** — 실제 DB 에 적재·권한 변경을 하는 일을 `work_type: data_ops` 로 다룬다(필수 검사: 대상 DB 확인, 승인 인용, 행 수·작업 ID 증거, 롤백 방법). 지금 work_type 은 코드·모델 중심이다.

### P2
8. `data_stance` 흔적 탐지에 data-platform 신호 추가(`system.yaml` 의 database, `data_lake/` 의 parquet, `sec.account` DDL) — 레이크는 owned 이지만 DB 밖 저장소라는 점을 reason 에 적게 한다.
9. 사전 대조표(`render`)를 사용설명서·보고서에 그대로 넣을 수 있게 HTML/JSON 출력도 제공.

---

## 6. 권장 통합 구조

```
dev-process-framework (정본·통제)                data-platform (실행)
├─ skills/sk-dev-data-modeling  ── 패키징 ──▶   skills/data-modeling (복사본, 직접 수정 금지)
├─ devprocess.glossary / datamodel ◀── 호출 ──  runtime: 용어 대조·등록 (어댑터 교체)
├─ model-approve (logical/physical) ◀── 기록 ── ingest apply / init (승인 인용 필수)
├─ verify: model_* · ddl_postgres · data_stance ◀── db/model.json (적재 결과 반영)
│          + pi_plain_scan · access_sync_dryrun (DP 가 제공하는 검사)
├─ model-diff → migrations/          ──▶       append·스키마 변경 시 사용
└─ sk-dev-user-manual                ──▶       DP 설명서 생성
```

**순서 제안**
1. DPF 5-1(끊긴 참조 결정: 편입 a / 조건부 b) — 결정만 하면 나머지가 정해진다
2. DP 4-1·4-2·4-3(정본 일원화·용어 어댑터 교체·공통 스키마 단어 정리)
3. DP 4-4·4-5(권한 범위·Windows 인코딩) — 작고 위험을 바로 줄임
4. DPF 5-5 마이그레이션 도구 → DP 4-8 에서 사용
5. 나머지 P1, P2
