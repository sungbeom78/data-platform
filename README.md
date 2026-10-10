# data-platform v2 — 데이터 모델링 + 데이터 관리 시스템

기존 **data-modeling 스킬**(사업·데이터 → PostgreSQL 모델 → DDL·pgModeler·엑셀 정의서, 실제 Postgres 검증)에
데이터를 **찾고 · 넣고 · 지키고 · 꺼내 쓰는** 시스템을 붙인 Claude 플러그인입니다.

| 스킬 | 하는 일 |
|---|---|
| `data-modeling` | (기존) 데이터 모델 설계·산출물. v2 선택 옵션: pi 스키마 분리, 암호화 컬럼, 접근정책, 공유 meta, bomiyang-glossary |
| `data-search` | 검색어 → 공공데이터 사이트·데이터 링크 표 → "저장해" 시 적재로 인계(대용량은 디스크 저장 제안) |
| `data-ingest` | csv·excel·json·URL(zip)·Open API → 프로파일 → 기존 테이블 추가 / 새 테이블 생성 → 적재 |
| `data-governance` | 설정 파일·128비트 키, 계정(개인·팀·시스템)·등급(s>a>b…)·분류·역할, 접근정책 → DB 롤 동기화, 개인정보 관리 |
| `data-api` | SELECT 쿼리를 등록해 REST API 로 공개, 관리자만 생성, API 별 사용권한 부여, API 키 |

## 기존 스킬과의 호환
- `skills/data-modeling`은 원본 그대로 동작합니다. 새 기능은 model.json **선택 키**로만 켜지며, 키가 없으면
  `export_all.py`가 v1 과 **바이트 단위로 같은** DDL·.dbm, 값·서식이 같은 xlsx 를 만듭니다(학사 예제로 회귀 검증).
- 단독 스킬로도 계속 쓸 수 있습니다: `skills/data-modeling` 폴더만 zip 해서 올리면 v1 처럼 동작합니다.

## 폴더
```
data-platform/
├── .claude-plugin/plugin.json
├── skills/
│   ├── data-modeling/   SKILL.md · scripts(export_all·check_dictionary·validate_pg.sh/.py) · references · examples(acad, acad_platform)
│   ├── data-search/     SKILL.md · references/sources.md
│   ├── data-ingest/     SKILL.md
│   ├── data-governance/ SKILL.md
│   └── data-api/        SKILL.md
├── runtime/
│   ├── dataplatform/    파이썬 패키지 (python -m dataplatform …)
│   │   ├── config · crypto · glossary · access · accounts · setup · db · compat(Windows 인코딩)
│   │   ├── ingest/      source(다운로드·읽기·Open API) · profile · plan · load · lake
│   │   ├── api/         app(FastAPI) · sqlguard
│   │   └── model/       build_platform_model.py → platform_model.json → platform_ddl.sql (+ .dbm·정의서)
│   ├── config/system.example.yaml
│   ├── requirements.txt
│   └── tests/test_e2e.py
└── pgmodeler_install.md
```

## 빠른 시작
```bash
pip install -r runtime/requirements.txt
cp runtime/config/system.example.yaml config/system.yaml     # database.dsn 수정
export PYTHONPATH=$PWD/runtime
python -m dataplatform --config config/system.yaml keygen --write
python -m dataplatform --config config/system.yaml init --admin-password '…'
python -m dataplatform --config config/system.yaml ingest plan ./data/가게.csv --schema pub
#   → ingest_plan.json 검토·승인(approved=true) 후
python -m dataplatform --config config/system.yaml ingest apply ingest_plan.json --by admin \
    --approval-quote "<사용자 답 그대로>" --physical-quote "<새 테이블 생성 승인 답>"
python -m dataplatform --config config/system.yaml serve      # http://localhost:8800/docs
```

## 공통 스키마
| 스키마 | 테이블 |
|---|---|
| `meta` | word·domain·term·table_catalog·column_catalog(용어·카탈로그, 기존과 동일) + **object_policy**(스키마/테이블 등급·분류) |
| `sec` | grade · category · account · account_category · account_key · role · role_category · role_member · audit_log |
| `api` | api_definition · api_grant · action_policy · call_log |
| `ingest` | source · job · lake_dataset |
| `pi` | `pi_<테이블>` 개인정보(AES-128 암호문·HMAC 해시) — PI 분류 계정만 |

공통 스키마도 data-modeling 규칙으로 설계했습니다(`runtime/dataplatform/model/out/04_table_spec.xlsx` 정의서, `03_model.dbm`).

## 검증
- 회귀: 학사 예제 원본 exporter vs 새 exporter — DDL·.dbm 동일, xlsx 값·서식 동일, 사전 검사 오류 0.
- 종단 테스트 20개(`runtime/tests`): 암호화·키 교체, 이전 설치 DB 업그레이드, 등급×분류 판정과 DB 롤 강제, **다른 앱 스키마 무변경**, 행위 정책, 용어(meta·bomiyang GlossaryWriter 등록), **cp949 콘솔에서 한글·이모지 출력**, csv(cp949) 적재·개인정보 분리·해시 검색·재적재 매칭, **적재 승인 증거(인용 없음·권한 없음·물리 생성 승인 없음 거부)**, 대용량 → Parquet 레이크·DuckDB 조회, SQL 검사, API 전 과정(로그인 등급·생성 권한·사용권한·API 키·정책 403·역할 부여).

## 변경 이력
- **2.1 (2026-10-10)** — 비교 분석(COMPARE 문서) P0-4·5·6 반영
  - 권한 동기화 범위를 관리 대상 스키마로 제한(`access.managed_schemas`) — 같은 DB 의 다른 앱 권한을 건드리지 않음
  - Windows 대응: 자식 프로세스 UTF-8 입출력, CLI 출력 오류 방지, DuckDB 경로 정규화, `validate_pg.py`(bash 없이 DDL 검증)
  - 적재 승인 증거: `--approval-quote`(필수)·`--physical-quote`(새 테이블), INGEST 행위 권한, `ingest.job.aprv_val`·감사 로그에 계획 지문과 함께 기록, `init` 재실행으로 기존 DB 업그레이드
- **2.0 (2026-10-05)** — data-modeling + 데이터 관리 시스템 첫 통합

---
만든 사람: 안숭범 (AI Data Architect)
