# 데이터 플랫폼 공통 스키마(sec·api·ingest·meta 확장)의 정본 model.json 생성기.
# data-modeling 스킬과 같은 규칙(이름은 사전에서만)으로 만들고, 같은 exporter 로 DDL·.dbm·xlsx 를 뽑는다.
#   python build_platform_model.py            → platform_model.json
#   python ../../../skills/data-modeling/scripts/export_all.py platform_model.json ./out
import json, datetime, os

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = lambda: [
    {"name": "created_at", "kor": "생성시각", "domain": "시각", "nullable": False, "default": "now()"},
    {"name": "updated_at", "kor": "수정시각", "domain": "시각", "nullable": False, "default": "now()"},
]

# ---------- 1. 단어 ----------
WORDS = [
    # 업무 단어
    ("계정", "acct", "account", False, "플랫폼 사용 주체(개인·팀·시스템)"),
    ("등급", "grade", "grade", False, "접근 등급 s>a>b>c>d>e"),
    ("분류", "ctgr", "category", False, "데이터 분류(개인정보·매출·성적·인사·총무·시스템…)"),
    ("역할", "role", "role", False, "분류·API 권한 묶음"),
    ("멤버", "member", "member", False, "역할 구성원"),
    ("키", "key", "key", False, "인증 키"),
    ("접두", "prefix", "prefix", False, "식별용 앞부분"),
    ("만료", "expire", "expire", False, "효력 종료"),
    ("감사", "audit", "audit", False, "변경 추적"),
    ("로그", "log", "log", False, "기록"),
    ("행위", "act", "action", False, "수행 동작"),
    ("대상", "target", "target", False, "작업 대상"),
    ("상세", "dtl", "detail", False, "세부 내용"),
    ("객체", "obj", "object", False, "DB 객체"),
    ("정책", "plcy", "policy", False, "규칙 묶음"),
    ("최소", "min", "minimum", False, "하한"),
    ("최대", "max", "maximum", False, "상한"),
    ("스키마", "schema", "schema", False, "DB 스키마"),
    ("테이블", "table", "table", False, "DB 테이블"),
    ("API", "api", "api", False, "조회용 API"),
    ("정의", "def", "definition", False, "정의 내용"),
    ("SQL", "sql", "sql", False, "SQL 문"),
    ("파라미터", "param", "parameter", False, "호출 인자"),
    ("행", "row", "row", False, "레코드"),
    ("제한시간", "timeout", "timeout", False, "실행 시간 상한"),
    ("부여", "grant", "grant", False, "권한 부여"),
    ("호출", "call", "call", False, "API 호출"),
    ("결과", "result", "result", False, "처리 결과"),
    ("경과", "elapsed", "elapsed", False, "소요"),
    ("소유", "owner", "owner", False, "소유자"),
    ("원천", "src", "source", False, "데이터 출처"),
    ("제공", "provider", "provider", False, "제공 기관"),
    ("라이선스", "license", "license", False, "이용 허락 조건"),
    ("URL", "url", "url", False, "위치 주소"),
    ("작업", "job", "job", False, "적재 작업"),
    ("상태", "status", "status", False, "진행 상태"),
    ("메시지", "msg", "message", False, "안내·오류 문구"),
    ("시작", "start", "start", False, "시작"),
    ("종료", "end", "end", False, "종료"),
    ("바이트", "byte", "byte", False, "크기 단위"),
    ("데이터셋", "dataset", "dataset", False, "레이크 저장 데이터 묶음"),
    ("경로", "path", "path", False, "파일 경로"),
    ("파티션", "partition", "partition", False, "분할 기준"),
    ("컬럼", "col", "column", False, "DB 컬럼"),
    ("파일", "file", "file", False, "파일"),
    ("형식", "fmt", "format", False, "파일 형식"),
    ("저장", "store", "store", False, "저장 방식"),
    ("프로파일", "profile", "profile", False, "데이터 프로파일링 결과"),
    ("레이크", "lake", "lake", False, "디스크 기반 대용량 저장소"),
    ("비밀번호", "pwd", "password", False, "로그인 비밀번호"),
    ("관리자", "admin", "admin", False, "관리 권한"),
    ("로그인", "login", "login", False, "인증"),
    ("순위", "rank", "rank", False, "높을수록 상위"),
    ("설명", "desc", "description", False, "설명 문구(단독 사용 금지 — 예약어)"),
    ("생성", "created", "created", False, "행 생성"),
    ("수정", "updated", "updated", False, "행 최종 수정"),
    ("사용", "use", "use", False, "사용 중 여부"),
    ("순서", "sort", "sort", False, "표시 순서"),
    ("값", "val", "value", False, "실제 내용 값"),
    ("유형", "type", "type", False, "분류 유형"),
    ("승인", "aprv", "approval", False, "사용자 승인 근거(인용·승인자·대상)"),
    # 분류어
    ("코드", "cd", "code", True, "분류어: 코드값"),
    ("번호", "no", "number", True, "분류어: 업무 식별 번호"),
    ("명", "nm", "name", True, "분류어: 명칭"),
    ("식별자", "id", "identifier", True, "분류어: 시스템 대리키"),
    ("여부", "yn", "yes_no", True, "분류어: 참/거짓"),
    ("시각", "at", "timestamp", True, "분류어: 일시"),
    ("수", "cnt", "count", True, "분류어: 건수"),
    ("해시", "hash", "hash", True, "분류어: 단방향 해시값"),
    ("밀리초", "ms", "millisecond", True, "분류어: 시간(ms)"),
]

# ---------- 2. 도메인 ----------
DOMAINS = {
    "식별자":     {"type": "bigint",       "check": None, "example": "1001", "desc": "시스템 대리키"},
    "코드(10)":   {"type": "varchar(10)",  "check": None, "example": "SYS", "desc": "짧은 코드값"},
    "코드(30)":   {"type": "varchar(30)",  "check": None, "example": "DATA_ANALYST", "desc": "긴 코드값"},
    "명칭(100)":  {"type": "varchar(100)", "check": None, "example": "데이터분석팀", "desc": "명칭"},
    "명칭(200)":  {"type": "varchar(200)", "check": None, "example": "전국 어린이집 표준데이터", "desc": "긴 명칭"},
    "물리명":     {"type": "varchar(63)",  "check": None, "example": "student", "desc": "PostgreSQL 식별자(63자)"},
    "API명":      {"type": "varchar(63)",  "check": "~ '^[a-z][a-z0-9_]{1,62}$'", "example": "sales_daily", "desc": "API 경로명(소문자·숫자·_)"},
    "로그인ID":   {"type": "varchar(50)",  "check": "~ '^[a-z][a-z0-9_.-]{2,49}$'", "example": "team_bi", "desc": "로그인 아이디"},
    "계정유형":   {"type": "varchar(10)",  "check": "IN ('USER','TEAM','SYSTEM')", "example": "TEAM", "desc": "개인·팀·시스템 계정"},
    "원천유형":   {"type": "varchar(10)",  "check": "IN ('FILE','URL','API','PUBLIC')", "example": "PUBLIC", "desc": "데이터 출처 유형"},
    "저장유형":   {"type": "varchar(10)",  "check": "IN ('DB','LAKE')", "example": "DB", "desc": "DB 테이블 / 디스크(Parquet) 저장"},
    "작업상태":   {"type": "varchar(10)",  "check": "IN ('READY','RUNNING','DONE','FAIL')", "example": "DONE", "desc": "적재 작업 상태"},
    "등급순위":   {"type": "smallint",     "check": "BETWEEN 0 AND 1000", "example": "90", "desc": "등급 순위(클수록 상위)"},
    "여부":       {"type": "boolean",      "check": None, "example": "true", "desc": "참/거짓"},
    "순서":       {"type": "integer",      "check": None, "example": "1", "desc": "표시 순서"},
    "건수":       {"type": "bigint",       "check": ">= 0", "example": "10000", "desc": "0 이상 건수·크기"},
    "밀리초":     {"type": "integer",      "check": "BETWEEN 100 AND 600000", "example": "15000", "desc": "실행 제한시간(ms)"},
    "경과밀리초": {"type": "integer",      "check": ">= 0", "example": "35", "desc": "소요 시간(ms)"},
    "시각":       {"type": "timestamptz",  "check": None, "example": "2026-10-05 21:00+09", "desc": "일시(시간대 포함)"},
    "설명":       {"type": "text",         "check": None, "example": "…", "desc": "자유 설명"},
    "SQL문":      {"type": "text",         "check": None, "example": "SELECT …", "desc": "등록 SQL (SELECT 단일문)"},
    "JSON":       {"type": "jsonb",        "check": None, "example": "[]", "desc": "구조화 값"},
    "URL":        {"type": "text",         "check": None, "example": "https://www.data.go.kr/…", "desc": "주소·경로"},
    "해시문":     {"type": "text",         "check": None, "example": "$argon2id$…", "desc": "argon2id 해시 문자열(단방향)"},
    "해시값":     {"type": "bytea",        "check": None, "example": "\\x…", "desc": "HMAC-SHA256 32바이트(단방향)"},
    "키접두":     {"type": "varchar(12)",  "check": None, "example": "dpk_ab12cd", "desc": "API 키 앞부분(식별용·비밀 아님)"},
}

def col(name, kor, domain, nullable=True, pk=False, unique=False, identity=False, default=None, fk=None, pi=False, crypto=None, desc=None):
    c = {"name": name, "kor": kor, "domain": domain, "nullable": nullable}
    if pk: c["pk"] = True
    if unique: c["unique"] = True
    if identity: c["identity"] = True
    if default is not None: c["default"] = default
    if fk: c["fk"] = fk
    if pi: c["pi"] = True
    if crypto: c["crypto"] = crypto
    if desc: c["description"] = desc
    return c
FK = lambda t, c, od="RESTRICT": {"table": t, "column": c, "on_delete": od}
USE = lambda: col("use_yn", "사용여부", "여부", False, default="true")

TABLES = [
    # ---------------- sec: 계정·권한 ----------------
    {"name": "grade", "schema": "sec", "kor": "등급", "kind": "코드", "is_pi": False,
     "description": "접근 등급. rank 가 클수록 상위(s=100). 계정은 등급 하나",
     "columns": [col("grade_cd", "등급코드", "코드(10)", False, pk=True), col("grade_nm", "등급명", "명칭(100)", False),
                 col("grade_rank", "등급순위", "등급순위", False, unique=True), USE()] + AUD(),
     "seed": [["s", "S등급", 100], ["a", "A등급", 90], ["b", "B등급", 80], ["c", "C등급", 70], ["d", "D등급", 60], ["e", "E등급", 50]]},
    {"name": "category", "schema": "sec", "kor": "분류", "kind": "코드", "is_pi": False,
     "description": "데이터 분류. 계정은 여러 분류 권한을 가질 수 있음",
     "columns": [col("ctgr_cd", "분류코드", "코드(10)", False, pk=True), col("ctgr_nm", "분류명", "명칭(100)", False),
                 col("sort_no", "순서번호", "순서", False, default="0"), USE()] + AUD(),
     "seed": [["PI", "개인정보", 1], ["SALES", "매출", 2], ["SCORE", "성적", 3], ["HR", "인사", 4], ["GA", "총무", 5], ["SYS", "시스템", 6]]},
    {"name": "account", "schema": "sec", "kor": "계정", "kind": "기준", "is_pi": False,
     "description": "개인·팀·시스템 계정. 등급 1개 + 관리자 여부. 비밀번호는 argon2id 단방향",
     "columns": [col("acct_id", "계정식별자", "식별자", False, pk=True, identity=True),
                 col("login_id", "로그인식별자", "로그인ID", False, unique=True, desc="업무 자연키"),
                 col("acct_nm", "계정명", "명칭(100)", False, desc="표시명(팀명·시스템명). 개인 성명은 저장하지 않음"),
                 col("acct_type_cd", "계정유형코드", "계정유형", False, default="'USER'"),
                 col("grade_cd", "등급코드", "코드(10)", False, fk=FK("grade", "grade_cd")),
                 col("admin_yn", "관리자여부", "여부", False, default="false"),
                 col("pwd_hash", "비밀번호해시", "해시문", True, crypto="argon2", desc="API 키만 쓰는 시스템 계정은 NULL"),
                 USE()] + AUD()},
    {"name": "account_category", "schema": "sec", "kor": "계정분류권한", "kind": "거래", "is_pi": False,
     "description": "계정이 보유한 분류 권한(N:M)",
     "columns": [col("acct_id", "계정식별자", "식별자", False, pk=True, fk=FK("account", "acct_id", "CASCADE")),
                 col("ctgr_cd", "분류코드", "코드(10)", False, pk=True, fk=FK("category", "ctgr_cd"))] + AUD()},
    {"name": "account_key", "schema": "sec", "kor": "계정키", "kind": "기준", "is_pi": False,
     "description": "팀·시스템 계정용 API 키. 키 원문은 저장하지 않고 HMAC 해시만 보관",
     "columns": [col("key_id", "키식별자", "식별자", False, pk=True, identity=True),
                 col("acct_id", "계정식별자", "식별자", False, fk=FK("account", "acct_id", "CASCADE")),
                 col("key_prefix", "키접두", "키접두", False, unique=True),
                 col("key_hash", "키해시", "해시값", False, crypto="hmac"),
                 col("expire_at", "만료시각", "시각", True), USE()] + AUD()},
    {"name": "role", "schema": "sec", "kor": "역할", "kind": "기준", "is_pi": False,
     "description": "분류 권한·API 사용권한 묶음. 계정에 역할을 주면 묶음 전체가 부여됨",
     "columns": [col("role_cd", "역할코드", "코드(30)", False, pk=True), col("role_nm", "역할명", "명칭(100)", False),
                 col("role_desc", "역할설명", "설명", True), USE()] + AUD()},
    {"name": "role_category", "schema": "sec", "kor": "역할분류권한", "kind": "거래", "is_pi": False,
     "description": "역할이 가진 분류 권한",
     "columns": [col("role_cd", "역할코드", "코드(30)", False, pk=True, fk=FK("role", "role_cd", "CASCADE")),
                 col("ctgr_cd", "분류코드", "코드(10)", False, pk=True, fk=FK("category", "ctgr_cd"))] + AUD()},
    {"name": "role_member", "schema": "sec", "kor": "역할멤버", "kind": "거래", "is_pi": False,
     "description": "역할을 부여받은 계정",
     "columns": [col("role_cd", "역할코드", "코드(30)", False, pk=True, fk=FK("role", "role_cd", "CASCADE")),
                 col("acct_id", "계정식별자", "식별자", False, pk=True, fk=FK("account", "acct_id", "CASCADE"))] + AUD()},
    {"name": "audit_log", "schema": "sec", "kor": "감사로그", "kind": "이력", "is_pi": False,
     "description": "계정·권한·정책·API 변경 기록",
     "columns": [col("log_id", "로그식별자", "식별자", False, pk=True, identity=True),
                 col("acct_id", "계정식별자", "식별자", True, fk=FK("account", "acct_id", "SET NULL"), desc="수행 계정"),
                 col("act_cd", "행위코드", "코드(30)", False), col("target_val", "대상값", "설명", True),
                 col("dtl_val", "상세값", "JSON", True)] + AUD()},
    # ---------------- meta: 객체 접근 정책 ----------------
    {"name": "object_policy", "schema": "meta", "kor": "객체정책", "kind": "기준", "is_pi": False,
     "description": "스키마/테이블별 최소 등급·분류. 정책이 없으면 전체 허용. table_nm='*' 는 스키마 전체, 테이블 정책이 우선",
     "columns": [col("plcy_id", "정책식별자", "식별자", False, pk=True, identity=True),
                 col("schema_nm", "스키마명", "물리명", False), col("table_nm", "테이블명", "물리명", False, default="'*'"),
                 col("min_grade_cd", "최소등급코드", "코드(10)", True, fk=FK("grade", "grade_cd")),
                 col("ctgr_cd", "분류코드", "코드(10)", True, fk=FK("category", "ctgr_cd")), USE()] + AUD(),
     "uniques": [["schema_nm", "table_nm"]]},
    # ---------------- api: 조회 API ----------------
    {"name": "api_definition", "schema": "api", "kor": "API정의", "kind": "기준", "is_pi": False,
     "description": "등록 쿼리 기반 조회 API. SELECT 단일문만 허용, 호출자 DB 권한으로 실행",
     "columns": [col("api_id", "API식별자", "식별자", False, pk=True, identity=True),
                 col("api_nm", "API명", "API명", False, unique=True, desc="호출 경로 /q/{api_nm}"),
                 col("api_desc", "API설명", "설명", True), col("sql_val", "SQL값", "SQL문", False),
                 col("param_val", "파라미터값", "JSON", False, default="'[]'::jsonb", desc="[{name,type,required,default}]"),
                 col("max_row_cnt", "최대행수", "건수", False, default="10000"),
                 col("timeout_ms", "제한시간밀리초", "밀리초", False, default="15000"),
                 col("owner_acct_id", "소유계정식별자", "식별자", True, fk=FK("account", "acct_id", "SET NULL")), USE()] + AUD()},
    {"name": "api_grant", "schema": "api", "kor": "API사용권한", "kind": "거래", "is_pi": False,
     "description": "API 사용권한 — 계정 또는 역할 단위로 관리자만 부여",
     "columns": [col("grant_id", "부여식별자", "식별자", False, pk=True, identity=True),
                 col("api_id", "API식별자", "식별자", False, fk=FK("api_definition", "api_id", "CASCADE")),
                 col("acct_id", "계정식별자", "식별자", True, fk=FK("account", "acct_id", "CASCADE")),
                 col("role_cd", "역할코드", "코드(30)", True, fk=FK("role", "role_cd", "CASCADE")),
                 col("grant_acct_id", "부여계정식별자", "식별자", True, fk=FK("account", "acct_id", "SET NULL"))] + AUD(),
     "uniques": [["api_id", "acct_id"], ["api_id", "role_cd"]],
     "checks": [{"name": "target", "expr": "(acct_id IS NOT NULL) <> (role_cd IS NOT NULL)"}]},
    {"name": "action_policy", "schema": "api", "kor": "행위정책", "kind": "코드", "is_pi": False,
     "description": "플랫폼 행위별 최소 등급·관리자 필요 여부(로그인=목록 조회 이상)",
     "columns": [col("act_cd", "행위코드", "코드(30)", False, pk=True), col("act_nm", "행위명", "명칭(100)", False),
                 col("min_grade_cd", "최소등급코드", "코드(10)", False, fk=FK("grade", "grade_cd")),
                 col("admin_yn", "관리자여부", "여부", False, default="false"), USE()] + AUD(),
     "seed_cols": ["act_cd", "act_nm", "min_grade_cd", "admin_yn"],
     "seed": [["LOGIN", "로그인", "b", False], ["LIST", "API 목록 조회", "b", False],
              ["MODIFY", "API 생성·변경·삭제", "a", True], ["GRANT", "API 사용권한 부여·회수", "a", True],
              ["CALL", "API 호출(사용권한 별도 필요)", "e", False], ["ACCOUNT", "계정·등급·분류·정책 관리", "a", True],
              ["INGEST", "데이터 적재 실행(승인 인용 필수)", "a", False]]},
    {"name": "call_log", "schema": "api", "kor": "호출로그", "kind": "이력", "is_pi": False,
     "description": "API 호출 기록. 파라미터 원문 대신 HMAC 해시",
     "columns": [col("log_id", "로그식별자", "식별자", False, pk=True, identity=True),
                 col("api_id", "API식별자", "식별자", True, fk=FK("api_definition", "api_id", "SET NULL")),
                 col("acct_id", "계정식별자", "식별자", True, fk=FK("account", "acct_id", "SET NULL")),
                 col("param_hash", "파라미터해시", "해시값", True, crypto="hmac"),
                 col("row_cnt", "행수", "건수", True), col("elapsed_ms", "경과밀리초", "경과밀리초", True),
                 col("result_cd", "결과코드", "코드(30)", False), col("msg_val", "메시지값", "설명", True)] + AUD()},
    # ---------------- ingest: 수집·적재 ----------------
    {"name": "source", "schema": "ingest", "kor": "원천", "kind": "기준", "is_pi": False,
     "description": "데이터 출처(파일·URL·API·공공데이터)",
     "columns": [col("src_id", "원천식별자", "식별자", False, pk=True, identity=True),
                 col("src_nm", "원천명", "명칭(200)", False), col("src_type_cd", "원천유형코드", "원천유형", False),
                 col("src_url", "원천URL", "URL", True), col("provider_nm", "제공명", "명칭(100)", True, desc="제공 기관"),
                 col("license_nm", "라이선스명", "명칭(100)", True), col("src_desc", "원천설명", "설명", True), USE()] + AUD()},
    {"name": "job", "schema": "ingest", "kor": "작업", "kind": "거래", "is_pi": False,
     "description": "적재 작업 1건 = 원천 1개 → 대상 테이블/데이터셋 1개",
     "columns": [col("job_id", "작업식별자", "식별자", False, pk=True, identity=True),
                 col("src_id", "원천식별자", "식별자", False, fk=FK("source", "src_id")),
                 col("target_schema_nm", "대상스키마명", "물리명", True), col("target_table_nm", "대상테이블명", "물리명", True),
                 col("store_type_cd", "저장유형코드", "저장유형", False, default="'DB'"),
                 col("status_cd", "상태코드", "작업상태", False, default="'READY'"),
                 col("row_cnt", "행수", "건수", True), col("byte_cnt", "바이트수", "건수", True),
                 col("profile_val", "프로파일값", "JSON", True), col("msg_val", "메시지값", "설명", True),
                 col("aprv_val", "승인값", "JSON", True, desc="{by, quote, physical_quote, at, plan_sha256, …} — 사용자 답 인용"),
                 col("start_at", "시작시각", "시각", True), col("end_at", "종료시각", "시각", True),
                 col("acct_id", "계정식별자", "식별자", True, fk=FK("account", "acct_id", "SET NULL"))] + AUD()},
    {"name": "lake_dataset", "schema": "ingest", "kor": "레이크데이터셋", "kind": "기준", "is_pi": False,
     "description": "디스크(Parquet) 기반 대용량·로그성 데이터 카탈로그. 조회는 DuckDB",
     "columns": [col("dataset_id", "데이터셋식별자", "식별자", False, pk=True, identity=True),
                 col("dataset_nm", "데이터셋명", "물리명", False, unique=True), col("path_val", "경로값", "URL", False),
                 col("partition_col_nm", "파티션컬럼명", "물리명", True),
                 col("file_fmt_cd", "파일형식코드", "코드(10)", False, default="'PARQUET'"),
                 col("row_cnt", "행수", "건수", True), col("byte_cnt", "바이트수", "건수", True),
                 col("src_id", "원천식별자", "식별자", True, fk=FK("source", "src_id", "SET NULL")), USE()] + AUD()},
]

ACCESS = [
    {"schema": "sec", "table": "*", "min_grade": "a", "category": "SYS", "meaning": "계정·권한 — 시스템 분류 + A 이상"},
    {"schema": "api", "table": "*", "min_grade": "a", "category": "SYS", "meaning": "API 정의·로그 — 시스템 분류 + A 이상"},
    {"schema": "ingest", "table": "*", "min_grade": "b", "category": "SYS", "meaning": "적재 이력 — 시스템 분류 + B 이상"},
    {"schema": "pi", "table": "*", "min_grade": None, "category": "PI", "meaning": "개인정보 스키마 — 개인정보 분류 보유자만"},
]

tok2kor = {}
for w in WORDS:
    tok2kor[w[1]] = w[0]; tok2kor[w[2]] = w[0]
def word_path(phys):
    bad = [t for t in phys.split("_") if t not in tok2kor]
    if bad: raise SystemExit(f"사전에 없는 단어: {bad} in {phys}")
    return ">".join(tok2kor[t] for t in phys.split("_"))

terms = {}
for t in TABLES:
    terms.setdefault(t["name"], {"kor": t["kor"], "phys": t["name"], "word_path": word_path(t["name"]), "domain": None, "desc": t["description"]})
    for c in t["columns"]:
        terms.setdefault(c["name"], {"kor": c["kor"], "phys": c["name"], "word_path": word_path(c["name"]), "domain": c["domain"], "desc": c.get("description")})

rels = []
for t in TABLES:
    for c in t["columns"]:
        if c.get("fk"):
            one = c.get("pk") and len([x for x in t["columns"] if x.get("pk")]) == 1
            rels.append({"from": t["name"], "from_col": c["name"], "to": c["fk"]["table"], "to_col": c["fk"]["column"],
                         "type": "1:1" if one else "N:1", "optional": c["nullable"], "on_delete": c["fk"]["on_delete"],
                         "meaning": f"{t['kor']}.{c['kor']} → {c['fk']['table']}"})

model = {
    "project": "data-platform 공통 스키마", "version": "2.0", "generated_at": datetime.date.today().isoformat(),
    "db": "postgresql", "db_version": "16", "schema": "sec", "meta_schema": "meta", "meta_mode": "shared",
    "pi_schema": "pi", "modeling_tool": "pgModeler 1.1",
    "assumptions": ["정책 없는 객체는 전체 허용", "계정은 등급 1개·분류 N개", "API 사용은 명시적 부여 필요",
                    "API 실행은 호출 계정의 DB 롤로(SET ROLE) — DB 가 최종 권한 판정"],
    "open_questions": ["등급 추가 시 rank 간격(10) 유지 여부"],
    "words": [{"kor": w[0], "abbr": w[1], "full": w[2], "is_class": w[3], "desc": w[4]} for w in WORDS],
    "domains": [{"name": k, **v} for k, v in DOMAINS.items()],
    "terms": list(terms.values()), "tables": TABLES, "relationships": rels,
    "access_policies": ACCESS,
    "pi_suggestions": ["비밀번호 argon2id, API 키·호출 파라미터는 HMAC-SHA256(128bit 키) — 원문 미보관"],
    "dq_notes": ["모든 테이블 PK·감사 컬럼", "코드성 값은 코드 테이블 또는 CHECK", "API 사용권한은 계정/역할 중 하나만(CHECK)"],
}
if __name__ == "__main__":
    out = os.path.join(HERE, "platform_model.json")
    json.dump(model, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("platform_model.json  tables:", len(TABLES), "terms:", len(terms), "words:", len(WORDS), "rels:", len(rels))
