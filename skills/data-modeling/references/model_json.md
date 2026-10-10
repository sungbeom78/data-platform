# model.json — 정본 구조

모든 산출물(DDL · .dbm · xlsx · DBML …)은 이 파일에서 생성한다. 손으로 고치는 산출물은 없다.

## 최상위 키

| 키 | 타입 | 설명 |
|---|---|---|
| project, version, generated_at | string | 보고·정의서 개요에 사용 |
| db, db_version | string | `postgresql`, `16` |
| schema | string | 업무 스키마명 (예: `acad`) |
| meta_schema | string | 사전 스키마명 (기본 `meta`) |
| modeling_tool | string | 예: `pgModeler 1.1` |
| assumptions[] | string | 설계 가정 — 개요 시트·보고에 그대로 |
| open_questions[] | string | 열린 질문 |
| words[] | object | 단어 사전: `kor`, `abbr`(컬럼 토큰), `full`(테이블 토큰), `is_class`, `desc` |
| domains[] | object | `name`, `type`(PG 자료형), `check`(컬럼명 뒤에 붙는 식, 예 `BETWEEN 0 AND 10`, `IN ('A','B')`), `example`, `desc` |
| terms[] | object | 용어 = 물리명 전수: `kor`, `phys`, `word_path`("학생>번호"), `domain`(테이블은 null), `desc` |
| tables[] | object | 아래 참조 |
| relationships[] | object | exporter가 관계 시트에 씀: `from, from_col, to, to_col, type("N:1"/"1:1"), optional, on_delete, meaning` |
| pi_suggestions[] | string | 개인정보 보호 제안 (검토메모 시트) |
| dq_notes[] | string | DQ 체크 결과 요약 |
| denormalization_notes[] | string | 반정규화 결정과 이유 (없으면 "없음 — 3NF 유지") |
| change_scenarios[] | string | 향후 변화 시나리오별 영향 |

## tables[] 항목

```json
{
  "name": "student",          // 물리명 — 영문 전체형 토큰을 _ 로 연결
  "kor": "학생",              // 논리명 → COMMENT, .dbm alias, 정의서
  "kind": "기준",             // 기준 | 거래 | 코드 | 이력 | PI  (.dbm 배치 행 결정)
  "is_pi": false,
  "description": "재학생. 성명은 pi_student",
  "columns": [ ... ],
  "seed": [["SELF","본인",1]]  // 선택. 코드 테이블 초기값 — columns 앞 3개 순서
}
```

## columns[] 항목

```json
{
  "name": "stud_no",          // 약어 토큰을 _ 로 연결, 분류어는 끝에
  "kor": "학생번호",
  "domain": "번호(10)",       // domains[].name 참조 — 자료형·CHECK 는 도메인에서 옴
  "nullable": false,
  "pk": true,                 // 복합 PK 는 여러 컬럼에 pk:true
  "unique": true,
  "identity": true,           // bigint GENERATED ALWAYS AS IDENTITY
  "default": "now()",         // SQL 식 그대로
  "fk": {"table": "department", "column": "dept_id", "on_delete": "RESTRICT"},
  "pi": true,                 // 개인정보 컬럼 — pi_ 테이블 안에만 허용
  "pi_type": "성명",          // 선택. 개인정보 시트 '유형' 열
  "sensitive": true,          // 선택. 민감정보 표시
  "description": "업무 자연키"
}
```

## 규칙 (check_dictionary.py 가 검사)
- 테이블명·컬럼명의 모든 토큰이 words 의 abbr 또는 full 에 있어야 한다. 구조 단어(`pi`, `code`, `hist`)도 등록한다.
- 모든 테이블명·컬럼명이 terms 에 있어야 한다.
- 모든 테이블에 pk 가 하나 이상, 모든 fk 는 실제 테이블·컬럼을 가리키고 on_delete 가 있어야 한다.
- pi:true 컬럼은 `pi_` 로 시작하는 테이블에만.
- created_at / updated_at 이 없으면 경고.

## v2 선택 키 (data-platform 모드) — 없으면 v1 과 같은 결과

| 위치 | 키 | 예 | 효과 |
|---|---|---|---|
| 최상위 | `pi_schema` | `"pi"` | `pi_*` 테이블을 그 스키마에 생성(이름 접두 `pi_` 유지) |
| 최상위 | `meta_mode` | `"shared"` | meta 사전 `CREATE TABLE IF NOT EXISTS` + 시드 `ON CONFLICT DO NOTHING` — 플랫폼 DB·여러 모델 공존 시 필수 |
| 최상위 | `pi_crypto_required` | `true` | `pi:true` 컬럼에 `crypto` 가 없으면 검사 오류 |
| 최상위 | `access_policies[]` | `{"schema":"acad","table":"enrollment","min_grade":"c","category":"SCORE","meaning":"…"}` | 플랫폼이 있으면 `meta.object_policy` 등록(DO 블록), 정의서 '접근정책' 시트 |
| 테이블 | `schema` | `"sec"` | 테이블별 스키마(여러 스키마를 한 모델에) |
| 테이블 | `uniques` | `[["schema_nm","table_nm"]]` | 복합 UNIQUE `uk_<table>_<a>_<b>` |
| 테이블 | `checks` | `[{"name":"target","expr":"(a IS NOT NULL) <> (b IS NOT NULL)"}]` | 테이블 CHECK `ck_<table>_<name>` |
| 테이블 | `seed_cols` | `["act_cd","act_nm","min_grade_cd","admin_yn"]` | seed 에 쓸 컬럼(기본 앞 3개) |
| 컬럼 | `crypto` | `"aes"` \| `"hmac"` \| `"argon2"` | 암호화 방식 표시 — COMMENT `[암호화:…]`, 개인정보 시트. aes/hmac 은 `bytea` 도메인, argon2 는 `text` |

검사기 추가 규칙: crypto 값·도메인 자료형 일치, pi 테이블이 `pi_schema` 밖에 명시 배치되지 않았는지, `uniques`/`seed_cols` 컬럼 존재.
