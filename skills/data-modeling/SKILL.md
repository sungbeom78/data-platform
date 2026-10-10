---
name: data-modeling
description: 사업 소개·업무 설명·담당자 직무·샘플/실데이터·공공데이터를 입력받아 그 사업을 표현하는 PostgreSQL 데이터 모델(개념→논리→물리)을 설계하고, pgModeler(.dbm)·DDL 스크립트·엑셀 테이블 정의서를 산출한다. 용어/단어 사전으로 테이블명·컬럼명을 관리하고, 개인정보 컬럼을 pi_ 테이블로 분리하며, DQ 제약과 정규화, 향후 변화 대응을 설계에 반영하고, 실제 Postgres에서 DDL과 업무 규칙을 검증한다. 사용자가 "데이터 모델링", "DB 설계", "테이블 설계", "ERD", "스키마 잡아줘", "정규화", "테이블 정의서", "pgModeler", "DDL 만들어줘", "이 서비스에 DB 어떻게 짜야 해" 등을 말하거나, 앱/서비스 개발 과정에서 데이터 구조를 정해야 하는 단계에 오면 — 명시적으로 '모델링'이라 하지 않아도 — 반드시 이 스킬을 사용한다. 다른 개발 스킬의 하위 단계(데이터 설계 담당)로도 호출된다. data-platform(공공데이터 검색·적재·개인정보 암호화·등급/분류 권한·조회 API)과 함께 설치돼 있으면 공유 meta 사전·pi 스키마·암호화 옵션으로 모델을 만든다.
---

# 데이터 모델링 스킬

이 스킬의 목적은 "돌아가기만 하는 스키마"가 아니라 **사업과 업무를 정확히 표현하고, 데이터 품질이 지켜지며, 요구사항이 바뀌어도 버티는 모델**을 만드는 것이다. 설계자는 18년 차 데이터 아키텍트(DAP·SQLP)의 눈으로 판단한다: 같은 사실은 한 곳에서 관리하고, 필요한 관계는 연결하고, 이름은 사전에서 가져오고, 개인정보는 따로 둔다.

산출물은 **하나의 정본(model.json)에서 모두 생성**한다. DDL·pgModeler·엑셀·DBML이 각자 손으로 만들어지면 반드시 서로 어긋난다. 정본을 먼저 완성하고 exporter로 뽑아야 일관성이 지켜지고, 다른 툴 연동 요청이 와도 exporter 하나만 추가하면 된다.

번들 스크립트(`scripts/`)가 있으면 그것을 쓰고, 없으면(단일 파일 스킬로 설치된 경우) 이 문서의 골격대로 작업 폴더에 직접 작성한다.

---

## 전체 흐름 (확인 게이트 3개)

```
[게이트 1] 시작 전 확인  →  입력 분석(모델링 노트)  →  개념/논리 모델
→ [게이트 2] 논리 모델 승인  →  용어사전 확정  →  PI 분리  →  물리 모델(model.json)
→ 산출물 생성(DDL · .dbm · xlsx)  →  검증(실제 Postgres + 스모크 테스트)
→ [게이트 3] 물리 테이블 생성 여부 확인  →  (승인 시) 생성 실행
```

게이트에서는 AskUserQuestion(없으면 평문)으로 묻고 답을 받은 뒤 진행한다. 사용자가 자리에 없는 것이 분명하면 기본값을 택하고 그 가정을 결과 맨 위에 적는다. 단, **게이트 3의 물리 생성은 명시적 승인 없이는 절대 실행하지 않는다.**

---

## 게이트 1 — 시작 전 확인 (한 번에 묻기)

사용자가 이미 말한 것은 다시 묻지 않는다. 묻지 않은 항목은 아래 기본값으로 진행하고 결과에 가정으로 명시한다.

| 항목 | 질문 | 기본값 |
|---|---|---|
| DB | 대상 DB와 버전 | PostgreSQL 16 |
| 모델링 툴 | 쓰는 모델링 툴과 버전 | pgModeler 1.1 (.dbm) |
| 용어 관리 | 기존 용어/단어 관리 시스템이 있는지, 있으면 접근 방법 | bomiyang-glossary 클론이 있으면 그것(3-1), 없으면 DB 안에 `meta` 스키마로 사전 테이블 생성 |
| 개인정보 | 개인정보 컬럼을 어떻게 다룰지 | `pi_` 접두 테이블로 분리 (암호화·분리보관은 제안만). **data-platform 설치 DB면** `pi` 스키마 + 암호화(4-1) |
| 명명 규칙 | 물리명 언어·표기법 | 영문 snake_case 소문자, 논리명(한글)은 COMMENT·alias에 |
| 범위 | 스키마명/프로젝트명, 이번에 다룰 업무 범위 | 입력에서 추론 |

입력이 **실데이터·공공데이터 파일**이면 먼저 열어서 컬럼·값·분포·결측·중복을 훑고(pandas), 그 관찰을 모델링 근거로 쓴다. 실데이터가 있으면 "있어야 할 것"보다 "실제로 있는 것"이 우선이다.

---

## 1. 입력 분석 → 모델링 노트

사업 소개, 직무 설명, 샘플 데이터 등을 읽고 **모델링 노트**를 먼저 쓴다(작업 폴더에 `01_modeling_notes.md`). 노트 없이 바로 테이블을 그리면 사업을 표현하는 게 아니라 입력 파일의 열을 그대로 옮기게 된다.

노트에 담을 것:
- **관리 대상(엔터티 후보)**: 사업이 다루는 사람·조직·물건·사건·계약·장소·문서. 명사를 뽑되 "이것의 생성·변경·소멸을 누가 관리하는가"로 실체 여부를 가린다.
- **업무 규칙**: "한 주문엔 상품이 여러 개", "회원 탈퇴해도 주문 이력은 보존" 같은 문장들. 이것이 관계·카디널리티·제약조건의 원천이다.
- **같은 사실이 여러 곳에 있을 위험**: 입력 자료에서 반복되는 정보(이름·연락처·주소·가격)를 찾아 "어디를 기준으로 둘지" 결정한다.
- **시간과 변화**: 이력이 필요한 것(가격·상태·소속), 과거 기록으로 보존할 것(주문 당시 배송지)과 최신 기준 정보(현재 주소)를 구분한다.
- **향후 변화 시나리오** 2~3개: "지점이 여러 개가 되면", "B2B 고객이 생기면". 설계에 반영하거나 최소한 막지 않도록 한다.
- **열린 질문**: 추정한 것과 확인이 필요한 것. 게이트 2에서 사용자에게 보여준다.

---

## 2. 개념/논리 모델

엔터티·속성·식별자·관계를 정한다. 판단 기준:

- **정규화는 3NF를 기본**으로 한다. 반정규화는 성능·조회 편의 등 이유가 있을 때만, 그 이유를 노트에 적고 한다. "테이블을 많이 나눌수록 좋다"는 틀렸다 — 같은 사실을 제각각 관리하지 않게 하는 것이 목적이다.
- **식별자**: 기본은 대리키(`bigint GENERATED ALWAYS AS IDENTITY`) + 업무 자연키에 UNIQUE. 외부 노출되거나 분산 환경이면 UUID 고려. 자연키가 안정적이고 짧으면(국가코드, 통화코드) 자연키 PK 허용.
- **관계**: 1:N은 FK, N:M은 교차 엔터티(관계 자체의 속성 — 성적·수량·역할 — 이 거기에 붙는다). 선택/필수 여부를 명시한다. FK의 삭제 규칙을 업무 규칙으로 정한다(이력 보존이면 RESTRICT, 종속이면 CASCADE).
- **코드값은 코드 테이블**로. 자유 텍스트 상태값은 DQ의 적이다. 값이 10개 이내이고 거의 안 바뀌면 CHECK 제약으로 대체 가능.
- **공통 감사 컬럼**: `created_at`, `updated_at`(필수), 필요 시 `created_by`, `updated_by`. 소프트 삭제는 업무상 필요할 때만 `deleted_at`으로.
- **이력**: 변화를 추적해야 하는 속성은 이력 테이블(`*_hist`, `valid_from`/`valid_to`) 또는 이벤트 테이블로. 현재값과 이력을 섞지 않는다.

### DQ(데이터 품질) 체크리스트 — 모든 엔터티에 적용
- 모든 테이블에 PK가 있는가, 업무상 중복 불가 조합에 UNIQUE가 있는가
- 비어서는 안 되는 컬럼은 NOT NULL인가 ("일단 NULL 허용"은 나중에 반드시 쓰레기값이 된다)
- 범위·형식이 정해진 값에 CHECK가 있는가 (수량 ≥ 0, 종료일 ≥ 시작일, 이메일 형식)
- 모든 FK가 선언돼 있고 삭제 규칙이 정해졌는가, FK 컬럼에 인덱스가 있는가
- 같은 사실이 두 테이블에 있다면 어느 쪽이 기준인지 노트에 적혀 있는가
- 금액은 `numeric`, 시각은 `timestamptz`, 날짜는 `date` — `float`·`text`로 때우지 않았는가

### 게이트 2 — 논리 모델 승인
엔터티 목록(한 줄 설명 포함), 관계 요약(A 1—N B, 삭제 규칙), 주요 가정과 열린 질문을 **짧게** 보여주고 승인을 받는다. 여기서 틀리면 뒤의 산출물이 전부 다시 나와야 하므로, 물리 모델로 넘어가기 전에 꼭 거친다. 간단한 ERD는 Mermaid `erDiagram`으로 함께 보여주면 좋다.

---

## 3. 용어/단어 사전 — 이름은 여기서만 나온다

테이블명·컬럼명을 짓기 **전에** 사전을 확정한다. 순서가 중요하다: 이름을 먼저 지으면 같은 뜻이 `cust`/`customer`/`client`로 흩어지고, 사전은 사후 정리용 장식이 된다.

### 명명 규칙 (사전 검사기가 기계적으로 확인한다)
- **테이블명 = 단어의 영문 전체형**을 `_`로 연결: `student`, `contact_subject_code`
- **컬럼명 = 단어의 약어**를 `_`로 연결: `stud_no`, `subject_cd`
- 둘 다 모든 토큰이 사전에 있어야 한다. 코드 테이블 접미어 `_code`, 개인정보 접두어 `pi_` 같은 **구조 단어도 사전에 등록**한다(검사에서 빠지지 않게).
- 분류어(class word)는 끝에 붙는다: `_no`(번호), `_nm`(명), `_cd`(코드), `_dt`(일자), `_at`(시각), `_yn`(여부), `_amt`(금액), `_cnt`(수), `_id`(식별자).
- 같은 단어는 한 약어만 갖는다. 약어는 발음이 아니라 의미가 보이게(`customer→cust`, `registration→reg`).
- 이름을 다 지은 뒤 `scripts/check_dictionary.py model.json`(없으면 같은 검사를 직접 작성)으로 사전 밖 토큰이 0개인지 확인한다. 걸리면 이름을 바꾸거나 단어를 등록한다 — 둘 중 어느 쪽인지 노트에 적는다.

### 기존 용어 관리 시스템이 있을 때
사용자가 알려준 방법(MCP·API·파일)으로 단어·용어·도메인을 읽어 그대로 쓴다. 없는 단어가 필요하면 **추가 후보 목록**을 만들어 사용자에게 보여주고, 승인된 것만 쓴다. 임의로 새 단어를 만들어 쓰지 않는다.

### 3-1. bomiyang-glossary 를 쓸 때 (기본 용어 시스템)
[bomiyang-glossary](https://github.com/sungbeom78/bomiyang-glossary) 클론 경로가 주어지면(또는 data-platform 설정 `glossary.bomiyang_path`) 그 사전을 단어 원천으로 쓴다.
- 단어 매핑: `id` = 영문 전체형(테이블 토큰), `abbreviation.short` 또는 `variants[type=abbreviation].short` = 약어(컬럼 토큰, 없으면 id 그대로), `lang.ko` = 한글명.
- 조회·검사는 `python -m dataplatform glossary check <물리명>` / `glossary split <한글명>` (data-platform 런타임). 런타임이 없으면 `dictionary/words.json`을 직접 읽어 같은 규칙으로 확인한다.
- **등록은 반드시 bomiyang 의 `core/writer.py`(GlossaryWriter) 경유** — JSON 을 손으로 고치지 않는다(저장소 규칙). 런타임의 `glossary add` 가 이 경로를 쓴다. 추가 후보는 먼저 사용자 승인.
- bomiyang 의 `domain`(trading·system…)은 주제 분류다. 데이터 도메인(금액·일자·전화번호)은 여전히 model.json `domains`와 `meta.domain`에서 관리한다.
- model.json 의 `words`에는 bomiyang 에서 가져온 단어를 그대로 복사해 둔다(정본 자기완결 — 검사기와 exporter 가 외부 파일 없이 돈다).

### 없을 때 — DB 안에 `meta` 스키마로 만든다
```sql
CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE meta.word (            -- 단어: 이름을 구성하는 최소 단위
  word_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kor_name     varchar(50)  NOT NULL UNIQUE,   -- 고객
  eng_abbr     varchar(30)  NOT NULL UNIQUE,   -- cust  (컬럼명 토큰)
  eng_full     varchar(60)  NOT NULL,          -- customer (테이블명 토큰)
  description  text,
  is_class     boolean NOT NULL DEFAULT false, -- 분류어 여부
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE meta.domain (          -- 도메인: 자료형 + 규칙의 묶음
  domain_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  domain_name  varchar(50)  NOT NULL UNIQUE,   -- 금액, 일자, 전화번호, 여부, 명칭(중)
  data_type    varchar(50)  NOT NULL,          -- numeric(15,2), date, varchar(20)…
  check_rule   text,                           -- 예: value ~ '^0\d{1,2}-\d{3,4}-\d{4}$'
  example      varchar(100),
  description  text
);
CREATE TABLE meta.term (            -- 용어: 단어의 조합 = 실제 테이블/컬럼 이름
  term_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kor_name     varchar(100) NOT NULL UNIQUE,   -- 고객전화번호
  phys_name    varchar(63)  NOT NULL UNIQUE,   -- cust_tel_no
  word_path    varchar(200) NOT NULL,          -- 고객>전화>번호
  domain_id    bigint REFERENCES meta.domain(domain_id),
  description  text
);
CREATE TABLE meta.table_catalog (
  schema_name  varchar(63) NOT NULL,
  table_name   varchar(63) NOT NULL,
  kor_name     varchar(100) NOT NULL,
  table_kind   varchar(20),                    -- 기준/거래/코드/이력/PI
  description  text,
  is_pi        boolean NOT NULL DEFAULT false,
  PRIMARY KEY (schema_name, table_name)
);
CREATE TABLE meta.column_catalog (
  schema_name  varchar(63) NOT NULL,
  table_name   varchar(63) NOT NULL,
  column_name  varchar(63) NOT NULL,
  ordinal      int NOT NULL,
  term_id      bigint NOT NULL REFERENCES meta.term(term_id),
  is_pi        boolean NOT NULL DEFAULT false,
  PRIMARY KEY (schema_name, table_name, column_name),
  FOREIGN KEY (schema_name, table_name) REFERENCES meta.table_catalog(schema_name, table_name)
);
```
사전의 INSERT문(시드)은 DDL 스크립트 안에 포함시켜, 테이블을 만들면 사전도 같이 채워지게 한다.

---

## 4. 개인정보(PI) 분리

개인을 식별하거나 식별에 결합되는 컬럼을 표시한다: 성명, 주민/여권/면허 번호, 전화, 이메일, 상세주소, 생년월일, 계좌·카드 번호, 사진, 위치, 건강·사상 등 민감정보.

- 별도 언급이 없으면 엔터티당 **`pi_<entity>` 테이블**로 분리한다. 본 테이블의 PK를 PI 테이블의 PK이자 FK로 두어 1:1을 보장한다(`ON DELETE CASCADE`).
- 본 테이블에는 업무 식별에 필요한 최소 정보만 남긴다(회원번호, 가입일, 상태). 이름조차 PI 테이블로 보내되, 화면 표시용이 꼭 필요하면 마스킹된 표시명(`display_nm`)을 본 테이블에 두는 안을 제시한다.
- 연락처처럼 **값 자체가 개인정보인 엔터티**는 분류 속성(주체·유형·비상여부)은 본 테이블에, 실제 값은 `pi_` 테이블에 둔다.
- **단독 사용(기본)**: 암호화·분리 보관을 구현하지 않는다. 대신 결과 보고에 다음을 제안한다: `pi` 전용 스키마 + 별도 권한(ROLE), 컬럼 암호화 대상, 마스킹 뷰, 보존 기간/파기 정책, RLS 적용 후보. 사용자가 이 중 원하는 것을 고르면 다음 작업으로 진행한다 — 4-1 이 그 구현이다.
- `meta.table_catalog.is_pi`, `meta.column_catalog.is_pi`에 표시해 정의서와 사전에서 개인정보가 한눈에 보이게 한다.

### 4-1. data-platform 모드 — pi 스키마 분리 + 암호화 + 권한
사용자가 개인정보 분리 보관·암호화를 원하거나 data-platform 이 설치된 DB(= `sec.account` 존재)에 만들 때. model.json 최상위에 선택 키를 켠다(없으면 v1 과 완전히 같은 산출물):
- `"pi_schema": "pi"` → `pi_*` 테이블이 `pi` 스키마에 생성된다(테이블명 `pi_` 접두는 유지 — 검사 규칙 동일). `pi` 스키마는 **개인정보(PI) 분류를 가진 계정만** 조회된다(data-governance).
- `"meta_mode": "shared"` → 플랫폼이 만든 `meta` 사전을 공유한다(`CREATE TABLE IF NOT EXISTS`, 시드 `ON CONFLICT DO NOTHING`). **플랫폼 DB 에는 반드시 shared** — 아니면 meta 테이블 중복 생성으로 실패한다.
- 컬럼 `"crypto"`: 정보 성격에 따라 고른다. 모두 128비트 키(시스템 설정 파일 `crypto.keys`·`crypto.hmac_key`).

| crypto | 방식 | 언제 | 도메인 자료형 |
|---|---|---|---|
| `aes` | 양방향 AES-128-GCM | 다시 봐야 하는 값: 성명·전화·이메일·주소·계좌·카드 | `bytea` |
| `hmac` | 단방향 HMAC-SHA256 | 일치 검색만: 주민번호·전화 검색키 (`aes`와 짝으로 `<컬럼>_hash`) | `bytea` |
| `argon2` | 단방향 argon2id | 인증용 비밀번호 | `text` |

- `"pi_crypto_required": true` 면 `pi: true` 컬럼에 crypto 가 없을 때 검사기가 오류를 낸다.
- `"access_policies": [{"schema","table","min_grade","category"}]` → 스키마/테이블 접근 등급·분류(예: 성적 테이블 = `SCORE` 분류 + c 이상). 플랫폼이 있으면 DDL 이 `meta.object_policy`에 등록하고, `python -m dataplatform sync`로 DB 롤에 반영한다.
- 값의 암·복호화는 DB 가 아니라 애플리케이션(런타임 `dataplatform.crypto`)에서 한다 — 키가 SQL·DB 로그로 새지 않게. DDL 의 COMMENT 에 `[암호화:…]`가 붙어 키 교체(`rotate-keys`)가 대상을 찾는다.
- 예제: `examples/acad_platform/make_platform_model.py` (학사 예제를 플랫폼 모드로 변환 — 원본 acad 는 그대로).

---

## 5. 물리 모델 정본 — model.json

모든 산출물은 이 파일에서 생성한다. 작업 폴더에 `model.json`으로 저장하고, 다른 스킬이 이어받을 수 있게 결과에 경로를 남긴다. 정본은 손으로 JSON을 쓰기보다 `build_model.py` 같은 생성기에서 단어→테이블 순으로 만들면 사전 검사를 같은 자리에서 돌릴 수 있다(`examples/acad/build_model.py` 참고).

```json
{
  "project": "학사관리", "version": "1.0", "db": "postgresql", "db_version": "16",
  "schema": "acad", "meta_schema": "meta", "modeling_tool": "pgModeler 1.1",
  "assumptions": ["한 학기 기준", "분반 없음"], "open_questions": ["..."],
  "words":   [{"kor":"학생","abbr":"stud","full":"student","is_class":false,"desc":"..."}],
  "domains": [{"name":"번호(10)","type":"varchar(10)","check":null,"example":"S001","desc":"..."}],
  "terms":   [{"kor":"학생번호","phys":"stud_no","word_path":"학생>번호","domain":"번호(10)","desc":null}],
  "tables": [{
    "name":"student","kor":"학생","kind":"기준","is_pi":false,"description":"...",
    "columns":[
      {"name":"stud_id","kor":"학생식별자","domain":"식별자","nullable":false,"pk":true,"identity":true},
      {"name":"stud_no","kor":"학생번호","domain":"번호(10)","nullable":false,"unique":true},
      {"name":"dept_id","kor":"학과식별자","domain":"식별자","nullable":false,
       "fk":{"table":"department","column":"dept_id","on_delete":"RESTRICT"}},
      {"name":"created_at","kor":"생성시각","domain":"시각","nullable":false,"default":"now()"}
    ],
    "seed": [["SELF","본인",1]]
  }],
  "relationships": [{"from":"student","from_col":"dept_id","to":"department","to_col":"dept_id","type":"N:1","optional":false,"on_delete":"RESTRICT","meaning":"..."}],
  "pi_suggestions": ["..."], "dq_notes": ["..."]
}
```
`kind`는 기준/거래/코드/이력/PI 중 하나 — exporter가 .dbm 배치와 정의서 구분에 쓴다. 컬럼 `pi: true`는 개인정보 표시. `seed`는 코드 테이블 초기값(앞 3개 컬럼 순서).

v2 선택 키(모두 생략 가능 — 생략하면 v1 과 바이트 단위로 같은 산출물): 최상위 `pi_schema`·`meta_mode`·`pi_crypto_required`·`access_policies`, 테이블 `schema`(여러 스키마 모델)·`uniques`(복합 UNIQUE)·`checks`(테이블 CHECK)·`seed_cols`(시드 컬럼 지정), 컬럼 `crypto`. 자세한 표는 `references/model_json.md`.

---

## 6. 산출물 생성 — `scripts/export_all.py model.json <출력폴더>`

model.json을 읽어 아래 셋을 한 번에 만든다. 스크립트가 없으면 같은 구조로 작업 폴더에 `export_all.py`를 작성한다(매번 손으로 쓰지 않는다 — 수정 후 재생성이 즉시 되고 산출물끼리 어긋나지 않는다).

### 6-1. DDL 스크립트 `02_ddl_postgresql.sql`
순서: 스키마 → `meta` 사전 테이블 + 시드 INSERT → 코드 테이블(+시드) → 기준 테이블 → 종속 테이블(FK 의존 순서) → `pi_*` → FK(`ALTER TABLE … ADD CONSTRAINT`로 모아서) → FK 인덱스 → `COMMENT ON TABLE/COLUMN`(한글 논리명 + 설명, 반드시). 제약명 규칙: `pk_<table>`, `uk_<table>_<col>`, `fk_<table>_<reftable>_<col>`, `ck_<table>_<col>`, `ix_<table>_<col>`. 전체를 `BEGIN; … COMMIT;`로 감싼다.

### 6-2. pgModeler `03_model.dbm`
pgModeler는 XML을 직접 읽으므로 최소 요소만 정확히 쓰면 열린다. **한글 논리명은 `comment`뿐 아니라 `alias` 속성에 반드시 넣는다** — 테이블·컬럼·관계선 모두. alias가 있어야 pgModeler 캔버스에서 한글로 볼 수 있다(기본은 물리명 표시, Show/설정의 "object aliases" 토글로 전환). 관계선 이름은 `rel_…` 기계명 대신 alias에 `수강성적→학생`처럼 읽히는 이름을 넣는다.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<dbmodel pgmodeler-ver="1.1.0" use-changelog="false" max-obj-count="N"
 last-position="0,0" last-zoom="1" scene-rect="0,0,2600,1600"
 default-schema="public" default-owner="postgres"
 layers="Default layer" active-layers="0" layer-name-colors="#000000" layer-rect-colors="#b4b4b4"
 show-layer-names="false" show-layer-rects="false">
<database name="mydb" is-template="false" allow-conns="true"></database>
<schema name="public" layers="0" fill-color="#e1e1e1" name-color="#000000" sql-disabled="true"></schema>
<schema name="acad" layers="0" rect-visible="true" fill-color="#e1e1e1" name-color="#000000"><role name="postgres"/></schema>
<table name="student" alias="학생" layers="0" collapse-mode="2" max-obj-count="8" z-value="0">
  <schema name="acad"/><role name="postgres"/>
  <comment> <![CDATA[학생 — 재학생]]> </comment>
  <position x="100" y="100"/>
  <column name="stud_id" alias="학생식별자" not-null="true" identity-type="ALWAYS"><type name="bigint" length="0"/><comment> <![CDATA[학생식별자]]> </comment></column>
  <column name="stud_no" alias="학생번호" not-null="true"><type name="varchar" length="10"/><comment> <![CDATA[학생번호]]> </comment></column>
  <constraint name="pk_student" type="pk-constr" table="acad.student"><columns names="stud_id" ref-type="src-columns"/></constraint>
  <constraint name="uk_student_stud_no" type="uq-constr" table="acad.student"><columns names="stud_no" ref-type="src-columns"/></constraint>
  <constraint name="ck_course_credit" type="ck-constr" table="acad.course"><expression> <![CDATA[credit BETWEEN 0 AND 10]]> </expression></constraint>
</table>
<constraint name="fk_student_department_dept_id" type="fk-constr" comparison-type="MATCH SIMPLE"
 upd-action="NO ACTION" del-action="RESTRICT" ref-table="acad.department" table="acad.student">
  <columns names="dept_id" ref-type="src-columns"/>
  <columns names="dept_id" ref-type="dst-columns"/>
</constraint>
<relationship name="rel_student_department" alias="학생→학과" type="relfk" layers="0"
 src-table="acad.student" dst-table="acad.department" src-required="false" dst-required="false"/>
</dbmodel>
```
주의: 모든 `<table>`을 먼저 쓰고, FK `<constraint>`와 `<relationship type="relfk">`는 그 뒤에 모아 쓴다(참조 순서). `<position>`은 종류별 행(코드/기준/거래/PI)에 격자로 배치해 겹치지 않게 하고, 사용자가 pgModeler에서 다시 정렬하면 된다고 안내한다. `pgmodeler-ver`는 사용자의 설치 버전 이하로 맞춘다 — 열 때 버전 오류가 나면 이 속성만 고치면 된다고 결과에 적어 둔다. **.dbm은 XML 정합성까지만 기계 검증이 되고, 실제로 열리는지는 사용자가 pgModeler에서 확인해야 한다** — 결과 보고에 이 한 줄을 고정으로 넣는다.

### 6-3. 엑셀 테이블 정의서 `04_table_spec.xlsx`
(xlsx 스킬이 있으면 그 지침을 따른다. openpyxl로 생성, 헤더 고정·열 너비·필터 적용, PI 행은 연한 빨강 배경.) 시트 구성은 고정:

1. **개요** — 프로젝트, DB, 스키마, 버전/일자, 가정 목록, 열린 질문, 테이블 수/컬럼 수/PI 컬럼 수/관계 수
2. **테이블목록** — 스키마 | 테이블명 | 논리명 | 구분(기준/거래/코드/이력/PI) | 설명 | PI여부 | 컬럼수
3. **컬럼명세** — 테이블명 | 테이블논리명 | 순번 | 컬럼명 | 논리명 | 도메인 | 자료형 | NULL | PK | FK(참조) | UNIQUE | 기본값 | CHECK | PI | 설명 (모든 테이블을 한 시트에, 테이블 경계에 굵은 선)
4. **관계(FK)** — 제약명 | 자식테이블 | 자식컬럼 | 부모테이블 | 부모컬럼 | 관계(N:1/1:1) | 필수 | 삭제규칙 | 갱신규칙 | 업무의미
5. **용어사전** — 단어 영역(한글/약어/영문/분류어/설명) + 용어 영역(한글명/물리명/단어경로/도메인) + 도메인 영역
6. **개인정보** — 테이블 | 컬럼 | 논리명 | 개인정보 유형 | 민감여부 | 현재 처리 | 제안
7. **코드정의** — 코드 테이블별 코드값 | 코드명 | 순서 (+ CHECK로 둔 값 목록)
8. **검토메모** — DQ 체크리스트 결과, 반정규화 결정과 이유, 향후 변화 시나리오별 영향, PI 제안

### 6-4. 요청 시 추가 exporter
DBML(dbdiagram.io), Mermaid `erDiagram`, Graphviz ERD(png/svg), MySQL/Oracle/SQL Server 방언 DDL, DBeaver/DataGrip용 스크립트, 다른 MCP가 요구하는 JSON — 모두 model.json에서 같은 방식으로 만든다. 새 형식은 exporter 함수 하나 추가로 끝나야 하며, 정본을 고치지 않는다.

---

## 7. 검증 — 산출물을 내기 전에 기계적으로 확인

**실제 Postgres에서 돌려본다.** 파서 검사만으로는 FK 순서·타입 불일치·제약 충돌을 못 잡는다. `scripts/validate_pg.sh 02_ddl_postgresql.sql [smoke.sql]`이 임시 인스턴스를 띄워 실행하고 정리한다(없으면 같은 절차를 직접). bash 가 없는 Windows 에서는 같은 일을 하는 `python scripts/validate_pg.py 02_ddl_postgresql.sql [smoke.sql]`(종료코드 0 통과·1 실패·77 Postgres 없음 = 미실행)을 쓴다.

우선순위:
1. 샌드박스에 Postgres가 없으면 `apt-get install -y postgresql`로 설치 가능한 경우가 많다 — 설치 후 `initdb` → `pg_ctl start`(비root, 임시 포트·소켓) → `psql -v ON_ERROR_STOP=1 -f DDL` → 종료·삭제.
2. 연결된 Postgres MCP(예: Supabase)의 **브랜치/개발 프로젝트**가 있으면 거기서 실행 후 롤백·삭제.
3. 둘 다 안 되면 `pglast`(pip)로 구문 파싱만. 어떤 수준으로 검증했는지 결과에 적는다.

**스모크 테스트를 같이 돌린다.** 샘플 데이터를 넣고 **업무 규칙이 제약으로 실제로 막히는지** 확인한다 — 중복 수강 INSERT가 UNIQUE에 걸리는지, 잘못된 코드값이 CHECK에 걸리는지, 자식 있는 기준 행 삭제가 RESTRICT되는지, 본체 삭제 시 PI 행이 CASCADE되는지, "같은 사실을 바꾸면 몇 행이 바뀌는가"가 1인지. 모델링 노트의 업무 규칙 하나하나를 테스트로 바꾸면 설계의 설득력이 생기고, 사용자에게 보여줄 가장 좋은 증거가 된다. 트랜잭션 안에서 SAVEPOINT로 실패 케이스를 감싸고 마지막에 ROLLBACK한다.

**정합성 검사**(`check_dictionary.py` + exporter 내부): 모든 FK의 참조 대상/컬럼/타입 일치, 모든 테이블에 PK, FK 컬럼 인덱스, 모든 물리명이 사전에 존재, PI 표시 컬럼이 `pi_*` 밖에 없음, model.json ↔ DDL ↔ xlsx 테이블/컬럼 수 일치, .dbm XML well-formed·이름 일치.

하나라도 실패하면 model.json을 고치고 **전부 재생성**한다. 산출물 하나만 손으로 고치지 않는다.

---

## 게이트 3 — 완료 후 확인

산출물(노트·DDL·.dbm·xlsx·model.json)을 전달하며 묻는다:

1. **여기서 끝낼지**(파일·정의서만), **물리 테이블까지 만들지**.
2. 만들겠다면 **어디에**: 연결된 DB MCP(Supabase 등 — 마이그레이션으로 남기는 방식 우선), 또는 사용자가 주는 접속 정보로 `psql`. 운영 DB로 보이면 한 번 더 확인한다.
3. 실행은 트랜잭션 한 번으로, 끝나면 생성된 테이블 목록·행 수(0)·사전 시드 건수를 보고한다. 실패하면 롤백하고 원인과 수정안을 보고한다.

이 승인 없이는 어떤 DB에도 DDL을 실행하지 않는다. "바로 만들어줘"라고 미리 말한 경우에도 대상 DB를 확인하는 질문 하나는 거친다 — 잘못된 DB에 스키마를 만드는 사고가 되돌리기 가장 어렵다.

---

## 결과 보고 형식

```
# <프로젝트> 데이터 모델 v<n>
## 한눈에 — 테이블 N개(기준 a · 거래 b · 코드 c · 이력 d · PI e), 관계 M개, 컬럼 K, PI 컬럼 p
## 핵심 설계 결정 (3~6줄: 기준 정보의 위치, 식별자 전략, 이력 방식, 반정규화 여부)
## 가정과 열린 질문
## 개인정보 처리 현황과 제안
## 산출물 — 경로 목록 (model.json 포함)
## 검증 결과 — 어떤 수준(실제 Postgres/MCP 브랜치/파서)인지 + 스모크 테스트 통과 항목
##   · .dbm: XML 정합성 확인됨. 실제 열기는 pgModeler에서 확인 필요. 한글 표시는 'object aliases' 토글.
## 다음 단계 — 게이트 3 질문
```

보고는 짧게. 설계의 '왜'는 모델링 노트와 검토메모 시트에 있고, 보고서는 결정과 확인 요청만 담는다.

---

## 다른 스킬과 함께 쓸 때

### data-platform 묶음 (같은 플러그인)
| 스킬 | 이 스킬과의 연결 |
|---|---|
| **data-search** | 공공데이터 검색 → 링크 제공. "저장해" 하면 data-ingest 로 넘김 |
| **data-ingest** | csv·excel·URL 적재. 새 테이블이 필요하면 **이 스킬의 model.json 규칙·exporter 를 그대로 써서** 테이블을 만든다(용어 검사·pi 분리·암호화 포함) |
| **data-governance** | 계정·등급·분류·역할, 개인정보 role, 접근정책(`access_policies`) 반영 |
| **data-api** | 만든 테이블을 등록 쿼리 API 로 공개 — 사용권한은 관리자 부여 |

플랫폼 공통 스키마(sec·api·ingest·meta 확장) 자체도 이 스킬 규칙으로 설계돼 있다: `runtime/dataplatform/model/build_platform_model.py` → `platform_model.json` → `export_all.py`.

이 스킬은 개발 흐름의 "데이터 설계" 단계만 담당한다. 상위 스킬(서비스 기획·API 설계·화면 설계)이 호출했다면 그 스킬이 넘겨준 요구사항을 입력으로 받고, 결과는 `model.json` + DDL 경로를 돌려준다. 호출한 쪽이 ORM 모델·API 스키마·화면 필드를 만들 때 이 정본을 읽게 하면 전 과정의 이름이 사전 하나로 통일된다.
