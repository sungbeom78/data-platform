---
name: data-ingest
description: csv·excel·json 파일, 다운로드 URL(zip 포함), 공공데이터 Open API 를 받아 프로파일(타입·결측·개인정보·규모)한 뒤 기존 테이블에 추가하거나 용어사전 규칙대로 새 테이블을 만들어 PostgreSQL 에 저장한다. 개인정보는 pi 스키마에 암호화해 분리하고, 대용량·로그성 데이터는 디스크(Parquet+DuckDB) 저장을 제안한다. "이 파일 DB에 넣어줘", "데이터 적재", "엑셀 테이블로 만들어", "URL 데이터 받아서 저장", "csv 업로드", "데이터 저장해" 등에 사용.
---

# 데이터 저장 (data-ingest)

`$RT` = 플러그인 루트 `runtime/`(이 스킬 폴더 기준 `../../runtime`), `$CFG` = 시스템 설정 파일. 명령은 `PYTHONPATH=$RT python -m dataplatform --config $CFG …`(아래 `dp …`로 줄여 씀). 처음이면 data-governance 의 설치 절차(keygen → init)를 먼저 한다.

## 흐름 (확인 게이트 — 승인 증거 없이 DB 에 쓰지 않는다)

```
원천(파일/URL/API) → dp ingest plan → ingest_plan.json 초안
→ Claude 가 빈칸 채움(테이블명·미등록 단어·개인정보 판정 검토·저장 방식)
→ [게이트] 사용자에게 요약 보여주고 승인 → approved=true
→ (새 테이블이면) [물리 생성 게이트] 테이블 생성 승인을 따로 받음
→ dp ingest apply … --approval-quote "<사용자 답 그대로>" [--physical-quote "<사용자 답 그대로>"]
→ 결과 보고(행 수·변환 실패·개인정보 분리·생성 산출물·접근정책)
```

### 1. 계획 초안
```bash
dp ingest plan <파일경로|URL> [--sheet 시트명] --schema pub --name "<데이터명>" [--provider 기관 --license 라이선스 --type PUBLIC]
```
자동으로 하는 일: 다운로드·zip 해제, 인코딩(utf-8/cp949)·구분자 감지, 앞 5만 행 프로파일, 전체 행 수 추정, 타입 추론(앞자리 0 은 문자, YYYYMMDD 일자 등), **개인정보 후보 탐지**(이름·값 패턴: 주민번호·전화·이메일·성명·주소·계좌·카드…; 사업장명·도로명주소 같은 공개 정보는 제외), 한글 컬럼명을 사전 단어로 분해해 물리명 제안, **기존 테이블 매칭**(이전 적재의 원본 컬럼명 기록 → 같으면 append 제안).

### 2. 초안 채우기 (Claude)
`ingest_plan.json`을 열어:
- `columns[].name`이 null 인 것: `missing`의 한글 단어를 `words_to_register`에 **영문 전체형(full)·약어(abbr)** 로 채운다. 이름 규칙은 data-modeling 3장과 같다(테이블=full 조합, 컬럼=abbr 조합 + 분류어 `_nm _cd _no _dt _at _yn _amt _cnt _val`). 같은 뜻의 단어가 사전에 이미 있으면 새로 만들지 말고 그걸 쓴다.
- `target.table`: 영문 전체형 조합(예: `daycare_center`). `pi_`로 시작하면 안 됨.
- `columns[].pi`: 탐지 결과를 검토. `crypto` = `aes`(다시 볼 값) / `hmac`(검색만) / `aes+hmac`(둘 다). 개인정보가 아니면 `null`. 필요 없는 컬럼은 `"skip": true`.
- `target.policy`(선택): `{"min_grade":"b","category":"SALES"}` — 이 테이블 접근 등급·분류.
- `store`: `DB` 또는 `LAKE`. LAKE 면 `lake.partition_by`(월 파티션 기준 시각 컬럼) 확인.
- 용어 시스템이 bomiyang 이면 단어 등록은 GlossaryWriter 로 그 저장소에 들어간다 — 사용자에게 등록 목록을 보여준다.

### 3. 게이트 — 사용자 승인 (증거로 남는다)
짧게 보여준다: 대상(`schema.table`, 신규/추가), 행 수, 컬럼 이름 매핑 표(원본 → 물리명·타입), 개인정보 컬럼과 처리(암호화 방식), 새로 등록할 단어, 저장 방식과 이유, 접근정책. 승인되면 `"approved": true`.
- **사용자의 답을 고치지 말고 그대로** `--approval-quote` 에 넣는다. 요약·의역·Claude 가 지어낸 문장 금지 — 답이 없으면 실행하지 않는다.
- **새 DB 테이블을 만드는 적재**(target.mode=new, store=DB)는 물리 생성 승인을 **따로** 묻는다: "pub.daycare_center 테이블을 새로 만들까요?" → 그 답을 `--physical-quote` 로. 기존 테이블 추가·레이크 저장은 필요 없다. 자동 승인 금지.
- 사용자가 미리 "다 알아서 해"라고 했어도 대상 DB·테이블을 한 번은 확인하고, 그 답을 인용한다.

### 4. 실행
```bash
dp ingest apply ingest_plan.json --by <실행 계정 login_id> \
   --approval-quote "<사용자 답 그대로>" [--physical-quote "<새 테이블 생성 승인 답 그대로>"]
```
- 실행 전 검사(하나라도 실패하면 단어 등록·DB 변경 없이 멈춤): `approved=true`, 인용 있음, `--by` 계정이 **INGEST 권한**(기본 a 등급 이상, `api.action_policy` 로 조정), 새 테이블이면 물리 생성 인용.
- 증거: `ingest.job.aprv_val` = {승인자, 인용, 물리 생성 인용, 시각, **계획 지문(plan_sha256)**, 대상, 개인정보 컬럼, 등록 단어}, 같은 내용이 `sec.audit_log`(INGEST_APPLY, 실패 시 INGEST_FAIL)에. `dp ingest jobs` 에 승인자·인용이 보인다.
- 신규: plan → **data-modeling 형식 model.json**(meta 공유·pi 스키마·암호화 필수) → `check_dictionary.py` → `export_all.py`(DDL·.dbm·정의서 xlsx) → DDL 실행 → 접근 동기화(sync). 산출물은 `ingest.work_dir/models/<table>/`.
- 적재: 개인정보 없으면 COPY, 있으면 본 테이블 INSERT → 같은 키로 `pi.pi_<table>`에 `<컬럼>_enc`(AES-128)·`<컬럼>_hash`(HMAC) 저장. 원문은 어디에도 남지 않는다.
- 변환 실패 값은 NULL 로 넣고 컬럼별 건수를 보고한다(`bad_values`). 이력은 `ingest.source`·`ingest.job`.
- LAKE: `lake_dir/<schema>__<table>/ym=YYYYMM/*.parquet`(zstd), 개인정보는 `hmac`(검색 해시만) 또는 `drop`(설정 `ingest.lake_pi_policy`). 카탈로그 `ingest.lake_dataset`. 조회:
  ```bash
  dp lake-query "SELECT ym, count(*) FROM pub__access_log GROUP BY 1" [--as <login_id>]
  ```
  레이크 접근 제한이 필요하면 `dp policy set lake --table <데이터셋명> --min-grade b --category SYS`.

### 5. 결과 보고
```
## 적재 결과 — pub.daycare_center (신규)
- 행 30,412 · 변환 실패: open_dt 3건(NULL) · 개인정보: rep_psn_nm(aes), tel_no(aes+hmac) → pi.pi_daycare_center
- 산출물: model.json · DDL · .dbm · 정의서 xlsx (경로)
- 접근: pub.daycare_center = b/SALES, pi.* = PI 분류만
- 다음: data-api 로 조회 API 를 만들까요?
```

## 대용량 판단 기준 (설정으로 조정)
| 조건 | 기본값 | 제안 |
|---|---|---|
| 행 수 | ≥ 1천만 (`ingest.large_rows`) | LAKE |
| 파일 크기 | ≥ 2GB (`ingest.large_bytes`) | LAKE |
| 시각 컬럼 + 대량 append(행 ≥ 기준의 1/10) | — | LAKE (로그성) |
DB 가 꼭 필요하면 대안: 월 단위 선언적 파티션 테이블 + 오래된 파티션 분리·아카이브, DB 에는 일/월 집계 테이블만.

## 주의
- 기존 테이블에 append 할 때 컬럼 타입이 다르면 apply 가 실패한다 — 대상 테이블 구조를 바꾸는 건 data-modeling 으로.
- 운영 DB 로 보이면 apply 전에 한 번 더 확인한다.
