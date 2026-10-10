# data-modeling v2 → 데이터 관리 플랫폼 작업 계획

- 작성: 2026-10-05 (월) 저녁 · 목표: **오늘 밤 MVP 완성** (약 8시간)
- 기준 버전: 현재 설치된 `data-modeling` SKILL.md (게이트 3개 · model.json 정본 · meta 사전 · pi_ 분리 · 실 Postgres 검증)
- 용어 시스템: `bomiyang-glossary` 저장소 구조 확인 완료 (words.json / compounds.json / terms.json, `generate_glossary.py check-id`, `core/writer.py` GlossaryWriter)

---

## 0. 먼저 확정할 것 (괄호 = 답이 없을 때 기본값)

| # | 결정 | 기본값 |
|---|---|---|
| D1 | 구글 드라이브 원본 경로 — 메시지에 경로가 빠져 있음. `scripts/`·`examples/acad` 포함 원본이 필요 | 설치본 SKILL.md 기준으로 시작, scripts는 원본 받으면 병합 |
| D2 | 산출 형태 | **플러그인 `data-platform`** (스킬 5개 + 공용 런타임). 수강생 배포는 플러그인 zip 1개 |
| D3 | API 서버 스택 | Python 3.11 · FastAPI · psycopg3 · PostgreSQL 16 |
| D4 | 암호화 위치 | **애플리케이션 계층** (키가 DB·SQL 로그로 넘어가지 않음). pgcrypto는 대안으로만 문서화 |
| D5 | 대용량(로그성) 저장 | 날짜 파티션 **Parquet + DuckDB 조회**, DB에는 카탈로그·요약만 |
| D6 | 공통 스키마 이름 | `meta` 유지 (용어 대체 테이블·카탈로그·도메인) |
| D7 | admin과 등급 관계 | admin은 등급과 별개 플래그. API **생성·관리 = admin AND 등급 ≥ a** (정책 테이블로 조정 가능) |

> 연결된 `devForDevSystem` 폴더는 현재 비어 있고, 로컬 쉘 마운트가 실패해 작업은 클라우드 작업공간에서 하고 결과물을 폴더로 내려보냄.

---

## 1. 목표 아키텍처

```
data-platform/                      (플러그인)
├─ skills/
│  ├─ data-modeling/   ← 기존 스킬 업그레이드 (용어 어댑터·PI 암호화·권한 메타 반영)
│  ├─ data-search/     ← 공공데이터 검색 → 링크 제공 → "저장해" 시 data-ingest로 인계
│  ├─ data-ingest/     ← csv/excel/URL/API → 프로파일 → 기존/신규 테이블 매핑 → 적재
│  ├─ data-governance/ ← 개인정보(pi) · 등급/분류 권한 · 계정/팀/역할 관리
│  └─ data-api/        ← 쿼리 등록형 조회 API 생성·권한 부여·운영
├─ runtime/            ← 공용 파이썬 패키지 (스킬들이 호출하는 실제 코드)
│  ├─ config.py        system.yaml 로딩 (DB, 암호화 키, 용어 모드, 임계치)
│  ├─ glossary/        adapter: bomiyang | meta
│  ├─ crypto.py        AES-128-GCM / HMAC-SHA256 / argon2
│  ├─ ingest/          profiler · mapper · loader · large_store(parquet)
│  ├─ access/          policy → PostgreSQL ROLE/GRANT 동기화
│  └─ api/             FastAPI 앱 (인증·쿼리 레지스트리·실행기)
├─ sql/                스키마별 DDL (meta, sec, pi, api, ingest) + 시드
├─ config/system.example.yaml
└─ tests/              실제 Postgres e2e (pytest)
```

### 스키마 분리

| 스키마 | 내용 | 접근 |
|---|---|---|
| `meta` (공통) | 용어 대체 테이블(word/term/domain), table/column 카탈로그, 객체 등급·분류 | 전체 조회, 변경은 관리자 |
| `sec` | 계정, 팀, 등급, 분류, 계정-분류, 역할, 역할 멤버, 감사로그 | 관리자 |
| `pi` | 개인정보 테이블(`pi.<entity>`), 마스킹 뷰 | **`pi_manager` 역할만** |
| `api` | API 정의, 쿼리, 파라미터, 사용 권한, 호출 로그, 액션 정책 | 관리자 / 등급별 |
| `ingest` | 적재 작업, 원천 소스, 프로파일 결과, 대용량 파일 카탈로그 | 관리자 |
| 업무 스키마 | 모델링 결과 | 정책에 따름 (기본 전체 허용) |

---

## 2. 기능별 설계 요약

### 2-1. 용어 시스템 (어댑터)
- `GlossaryAdapter` 인터페이스: `lookup(token)`, `check_identifier(name)`, `propose(words)`, `register(word)`.
- **BomiyangAdapter** (기본): `words.json`·`compounds.json` 읽기, `generate_glossary.py check-id`로 검증, 등록은 반드시 `GlossaryWriter` 경유 (JSON 직접 수정 금지 규칙 준수).
  - 매핑: 테이블 토큰 = `id`(영문 전체형), 컬럼 토큰 = `variants[type=abbreviation]`, 한글명 = `lang.ko`.
  - ⚠ bomiyang의 `domain`(trading/system…)은 **주제 분류**라 데이터 도메인(금액·일자·전화번호)과 다름 → 데이터 도메인은 bomiyang 모드에서도 `meta.domain`에 둔다.
  - ⚠ 약어 variant가 없는 단어가 많을 수 있음 → 약어 후보를 제안 목록으로 만들어 승인 후 등록.
- **MetaAdapter** (대체): bomiyang 경로가 없으면 기존 `meta.word/term/domain` 사용.
- `system.yaml`의 `glossary.mode: bomiyang|meta`, `glossary.path`로 선택. 경로가 없거나 검증 실패 시 자동으로 meta 모드 + 경고.

### 2-2. 개인정보(PI) 관리
- 모든 PI는 `pi` 스키마. 본 테이블 PK = PI 테이블 PK/FK (1:1, CASCADE) — 기존 규칙 유지, 위치만 `pi_` 접두 → `pi` 스키마로 이동.
- 역할: `pi_manager`(복호화·조회), `pi_writer`(적재), 그 외 계정은 `pi` 스키마 USAGE 없음 → 마스킹 뷰만.
- 암호화 (모든 PI 컬럼 암호화, 성격별 방식):

| 성격 | 방식 | 예 | 저장 컬럼 |
|---|---|---|---|
| 복원 필요 | **양방향 AES-128-GCM** (128bit 키) | 성명, 전화, 이메일, 주소, 계좌, 카드, 주민번호 원문 | `<col>_enc bytea` + `key_ver smallint` |
| 일치 검색만 | **단방향 HMAC-SHA256** (128bit 키를 pepper로) | 주민번호·전화·이메일 검색키 | `<col>_hash bytea` (양방향 컬럼과 짝) |
| 인증용 | **단방향 argon2id** (솔트, 키 불필요) | 비밀번호 | `pwd_hash text` |

- 키: `system.yaml`의 `crypto.keys: {1: <32 hex>, 2: ...}`, `crypto.active_key: 1`. 키 버전 컬럼으로 교체(rotation) 지원, 재암호화 스크립트 제공. 설정 파일 권한 600·저장소 제외(.gitignore) 가이드.
- 모델링 단계에서 PI 컬럼마다 `pi_type`, `crypto: aes|hmac|argon2|aes+hmac`을 model.json에 기록 → DDL·정의서·적재기가 같은 정보를 사용.

### 2-3. 권한·접근 관리 (등급 × 분류)
- 등급: `sec.grade(grade_cd, rank)` — s=100, a=90, b=80, c=70, d=60, e=50 … (추가 가능). 계정은 **등급 1개**.
- 분류: `sec.category` — 개인정보, 매출, 성적, 인사, 총무, 시스템 … 계정은 **분류 N개** (`sec.account_category`).
- 객체 정책: `meta.object_policy(schema, table NULL=스키마 전체, min_grade, category NULL)`. 정책 없음 = 전체 허용(기본).
- 판정: `계정.rank ≥ 객체.min_rank AND (객체.category IS NULL OR 계정이 그 분류 보유)`; 테이블 정책이 스키마 정책보다 우선.
- 계정 유형: user / team / system. 팀 계정·시스템 계정은 API 키 발급. **역할(role)**: 분류·API 권한 묶음을 계정에 부여.
- 강제 방식 2중:
  1. **DB 네이티브**: 정책 → PostgreSQL ROLE/GRANT 동기화(`access/sync.py`). 계정마다 로그인 롤, 보호 테이블마다 `r_<schema>_<table>` 롤 생성 후 판정 통과 계정에만 GRANT. 기본 허용 객체는 `r_public_read`.
  2. **API 계층**: 같은 판정 함수로 사전 차단 + 실행은 `SET ROLE <계정롤>`로 DB가 최종 확인.
- 모든 권한 변경은 `sec.audit_log`에 기록.

### 2-4. 조회 API
- 액션 정책 `api.action_policy` (기본값, 테이블로 조정 가능):

| 액션 | 조건 |
|---|---|
| 로그인 | 등급 ≥ b (= 목록 조회 이상) |
| API 목록 조회 | 등급 ≥ b |
| API 생성·변경·삭제 | admin 플래그 AND 등급 ≥ a |
| API 사용권한 부여 | admin 플래그 |
| API 호출 | 해당 API에 대한 **명시적 사용권한** (계정·팀·역할 단위) |

- 쿼리 등록: 이름, SQL(이름 붙은 파라미터 `:from_dt`), 파라미터 타입, 최대 행수, 타임아웃.
  - 등록 시 `pglast`로 파싱 → **SELECT 단일문만 허용**, 참조 테이블 추출 → 객체 정책 사전 점검.
  - 실행 시 읽기 전용 트랜잭션, `statement_timeout`, 행 제한, `SET ROLE` 후 바인드 실행.
- 엔드포인트: `POST /auth/token`, `GET /apis`, `POST/PUT/DELETE /apis/{id}`, `POST /apis/{id}/grants`, `GET|POST /q/{api_name}`, `GET /tables/{schema}/{table}`(정책 통과 시 단순 조회).
- 호출 로그(`api.call_log`): 계정, API, 파라미터 해시, 행수, 소요시간, 결과코드.

### 2-5. 공공데이터 검색 (data-search)
- 입력: 검색어 → Claude가 웹검색으로 후보 수집 (공공데이터포털 data.go.kr 파일/Open API, KOSIS, 지자체 열린데이터광장, 각 부처 포털 등).
- 출력 표: 데이터명 | 제공기관 | 링크 | 형식(CSV/XLSX/API) | 갱신주기 | 규모 추정 | 라이선스 | 비고(API 키 필요 등).
- "○○ 저장해" → 해당 링크로 **data-ingest 인계** (규모 판정 포함).
- data.go.kr Open API는 서비스키를 `system.yaml`의 `public_data.service_key`로.

### 2-6. 데이터 저장 (data-ingest)
1. 수집: 로컬 csv/xlsx(시트별), URL(파일·zip), Open API(JSON/XML 페이징).
2. 프로파일: 인코딩(cp949/utf-8) 감지, 타입 추론, 결측·중복·카디널리티, PI 후보 탐지(컬럼명+값 패턴).
3. 매핑: 용어 어댑터로 컬럼명 → 표준 용어 변환, 기존 테이블과 유사도 비교 → **기존 테이블 적재 / 신규 테이블 생성** 제안.
4. 신규면 data-modeling 파이프라인(model.json → DDL) 재사용, **게이트(사용자 승인)** 후 생성.
5. 적재: `COPY` 대량 적재, PI 컬럼은 암호화 후 `pi` 스키마로 분리 적재, 적재 이력·원천 URL 기록(`ingest.job`, 계보).
6. **대용량 분기**: 추정 행수 > 1천만, 또는 크기 > 2GB, 또는 append-only 시계열 → 로그성 저장 제안:
   - Parquet(날짜 파티션) + DuckDB 조회 스크립트, `ingest.large_dataset` 카탈로그 등록, DB에는 일/월 집계 테이블만.
   - 대안: PostgreSQL 선언적 파티션 + 오래된 파티션 아카이브. 장단점 표와 함께 제안 → 사용자가 선택.

---

## 3. 오늘 밤 일정 (MVP)

| 시간 | 단계 | 산출물 | 완료 기준 |
|---|---|---|---|
| 0:00–0:30 | P0 준비 | 원본 스킬 확보(D1), 플러그인 골격, system.example.yaml, 결정 D1–D7 확정 | 폴더 구조·설정 로딩 동작 |
| 0:30–1:30 | P1 공통 기반 | `sql/meta,sec,pi,api,ingest` DDL, 용어 어댑터 2종 | 실 Postgres에서 DDL 통과, bomiyang `check-id` 연동 |
| 1:30–2:30 | P2 권한 | 등급·분류·계정·역할 테이블, 판정 함수, ROLE/GRANT 동기화 | 등급/분류 조합 6케이스 테스트 통과 |
| 2:30–3:30 | P3 개인정보 | `crypto.py`, pi 스키마 규칙, 마스킹 뷰, `pi_manager` | 비권한 계정 pi 조회 거부, 복호화·HMAC 검색 테스트 |
| 3:30–5:00 | P4 적재 | profiler · mapper · loader · large_store | csv·xlsx·URL 각 1건 적재, 대용량 분기 제안 출력 |
| 5:00–5:45 | P5 공공데이터 검색 | data-search SKILL.md + 결과 표 형식 + 인계 규약 | 검색어 1개로 링크 표 → 저장까지 연결 |
| 5:45–7:00 | P6 조회 API | FastAPI 앱, 인증(API 키+JWT), 레지스트리, 실행기, 액션 정책 | 등급별 로그인/목록/변경 차단, 미부여 API 호출 403 |
| 7:00–8:00 | P7 통합 | 5개 SKILL.md 정리, data-modeling 본문 갱신, e2e 시나리오, 플러그인 패키징 | e2e 통과, zip 생성, 폴더에 배포 |

### 시간이 모자랄 때 뒤로 미룰 것 (순서대로)
1. Open API(JSON/XML) 페이징 수집 → 파일·URL만 먼저
2. 키 교체(rotation) 재암호화 스크립트 → 키 버전 컬럼만 먼저
3. 웹 관리 화면 → API(Swagger UI)로 대체
4. PostgreSQL 파티션 대안 → Parquet 경로만 먼저

---

## 4. 검증 시나리오 (e2e, 실제 Postgres)

1. 공공데이터 CSV(cp949) URL 적재 → 신규 테이블 생성 승인 → 행수 일치.
2. PI 포함 엑셀 적재 → `pi` 스키마에 암호문만 존재, 본 테이블에 PI 없음, HMAC로 전화번호 일치 검색 성공.
3. 등급 c 계정: 로그인 거부 / 등급 b: 목록만 / a+admin: API 생성 성공 / a 비admin: 생성 거부.
4. 분류 "매출" 정책 테이블: 분류 없는 s 등급 계정도 거부, 분류 보유 b 계정 허용.
5. 사용권한 없는 팀 계정 API 호출 403 → 부여 후 200, 호출 로그 기록.
6. 등록 쿼리에 `DELETE`/다중문 포함 → 등록 거부.
7. bomiyang 경로 제거 → meta 모드로 자동 전환, 사전 밖 토큰 0개 검사 통과.
8. 대용량 추정 데이터 → Parquet 저장 제안 및 DuckDB 조회 예시 실행.

---

## 5. 리스크·메모
- 개인정보 암호화 기준(일방향: 비밀번호 / 양방향: 고유식별정보·계좌·카드 등)은 개인정보 안전성 확보조치 기준의 일반적 구분을 따름 — 실제 적용 범위는 운영 기관 기준으로 최종 확인.
- 암호화 키를 설정 파일에 두는 방식은 요구사항대로 제공하되, 운영 시 KMS/비밀 저장소로 옮기는 옵션을 문서에 남김.
- PostgreSQL 롤 수가 테이블 수만큼 늘어남 → 보호 정책이 걸린 테이블만 롤 생성(기본 허용 객체는 공용 롤 하나).
- bomiyang-glossary는 코드 식별자용(트레이딩 도메인 중심) 사전이라 데이터 용어가 부족할 수 있음 → 첫 적용 시 단어 등록 후보가 많이 나올 것.
