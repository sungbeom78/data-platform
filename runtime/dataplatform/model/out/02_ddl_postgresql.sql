-- data-platform 공통 스키마 v2.0 — PostgreSQL 16 DDL (generated 2026-10-10)
-- 생성 순서: 스키마 → meta 사전 → 사전 시드 → 코드 테이블 → 기준/거래/PI 테이블 → FK → 인덱스 → COMMENT
BEGIN;

CREATE SCHEMA IF NOT EXISTS sec;
CREATE SCHEMA IF NOT EXISTS api;
CREATE SCHEMA IF NOT EXISTS ingest;
CREATE SCHEMA IF NOT EXISTS meta;

-- ===== meta: 용어/단어 사전 (공유 모드: 이미 있으면 재사용) =====
CREATE TABLE IF NOT EXISTS meta.word (
  word_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kor_name     varchar(50)  NOT NULL UNIQUE,
  eng_abbr     varchar(30)  NOT NULL UNIQUE,
  eng_full     varchar(60)  NOT NULL,
  description  text,
  is_class     boolean NOT NULL DEFAULT false,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS meta.domain (
  domain_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  domain_name  varchar(50)  NOT NULL UNIQUE,
  data_type    varchar(50)  NOT NULL,
  check_rule   text,
  example      varchar(100),
  description  text
);
CREATE TABLE IF NOT EXISTS meta.term (
  term_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kor_name     varchar(100) NOT NULL UNIQUE,
  phys_name    varchar(63)  NOT NULL UNIQUE,
  word_path    varchar(200) NOT NULL,
  domain_id    bigint REFERENCES meta.domain(domain_id),
  description  text
);
CREATE TABLE IF NOT EXISTS meta.table_catalog (
  schema_name  varchar(63) NOT NULL,
  table_name   varchar(63) NOT NULL,
  kor_name     varchar(100) NOT NULL,
  table_kind   varchar(20),
  description  text,
  is_pi        boolean NOT NULL DEFAULT false,
  PRIMARY KEY (schema_name, table_name)
);
CREATE TABLE IF NOT EXISTS meta.column_catalog (
  schema_name  varchar(63) NOT NULL,
  table_name   varchar(63) NOT NULL,
  column_name  varchar(63) NOT NULL,
  ordinal      int NOT NULL,
  term_id      bigint NOT NULL REFERENCES meta.term(term_id),
  is_pi        boolean NOT NULL DEFAULT false,
  PRIMARY KEY (schema_name, table_name, column_name),
  FOREIGN KEY (schema_name, table_name) REFERENCES meta.table_catalog(schema_name, table_name)
);
COMMENT ON TABLE meta.word IS '단어 사전: 이름을 구성하는 최소 단위';
COMMENT ON TABLE meta.domain IS '도메인: 자료형과 검증 규칙의 묶음';
COMMENT ON TABLE meta.term IS '용어 사전: 단어 조합 = 실제 테이블/컬럼 물리명';
COMMENT ON TABLE meta.table_catalog IS '테이블 목록(논리명·구분·개인정보 여부)';
COMMENT ON TABLE meta.column_catalog IS '컬럼 목록(용어 참조·개인정보 여부)';

-- ----- 사전 시드 -----
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('계정', 'acct', 'account', '플랫폼 사용 주체(개인·팀·시스템)', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('등급', 'grade', 'grade', '접근 등급 s>a>b>c>d>e', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('분류', 'ctgr', 'category', '데이터 분류(개인정보·매출·성적·인사·총무·시스템…)', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('역할', 'role', 'role', '분류·API 권한 묶음', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('멤버', 'member', 'member', '역할 구성원', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('키', 'key', 'key', '인증 키', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('접두', 'prefix', 'prefix', '식별용 앞부분', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('만료', 'expire', 'expire', '효력 종료', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('감사', 'audit', 'audit', '변경 추적', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('로그', 'log', 'log', '기록', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('행위', 'act', 'action', '수행 동작', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('대상', 'target', 'target', '작업 대상', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('상세', 'dtl', 'detail', '세부 내용', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('객체', 'obj', 'object', 'DB 객체', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('정책', 'plcy', 'policy', '규칙 묶음', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('최소', 'min', 'minimum', '하한', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('최대', 'max', 'maximum', '상한', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('스키마', 'schema', 'schema', 'DB 스키마', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('테이블', 'table', 'table', 'DB 테이블', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('API', 'api', 'api', '조회용 API', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('정의', 'def', 'definition', '정의 내용', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('SQL', 'sql', 'sql', 'SQL 문', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('파라미터', 'param', 'parameter', '호출 인자', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('행', 'row', 'row', '레코드', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('제한시간', 'timeout', 'timeout', '실행 시간 상한', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('부여', 'grant', 'grant', '권한 부여', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('호출', 'call', 'call', 'API 호출', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('결과', 'result', 'result', '처리 결과', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('경과', 'elapsed', 'elapsed', '소요', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('소유', 'owner', 'owner', '소유자', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('원천', 'src', 'source', '데이터 출처', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('제공', 'provider', 'provider', '제공 기관', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('라이선스', 'license', 'license', '이용 허락 조건', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('URL', 'url', 'url', '위치 주소', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('작업', 'job', 'job', '적재 작업', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('상태', 'status', 'status', '진행 상태', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('메시지', 'msg', 'message', '안내·오류 문구', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('시작', 'start', 'start', '시작', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('종료', 'end', 'end', '종료', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('바이트', 'byte', 'byte', '크기 단위', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('데이터셋', 'dataset', 'dataset', '레이크 저장 데이터 묶음', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('경로', 'path', 'path', '파일 경로', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('파티션', 'partition', 'partition', '분할 기준', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('컬럼', 'col', 'column', 'DB 컬럼', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('파일', 'file', 'file', '파일', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('형식', 'fmt', 'format', '파일 형식', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('저장', 'store', 'store', '저장 방식', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('프로파일', 'profile', 'profile', '데이터 프로파일링 결과', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('레이크', 'lake', 'lake', '디스크 기반 대용량 저장소', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('비밀번호', 'pwd', 'password', '로그인 비밀번호', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('관리자', 'admin', 'admin', '관리 권한', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('로그인', 'login', 'login', '인증', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('순위', 'rank', 'rank', '높을수록 상위', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('설명', 'desc', 'description', '설명 문구(단독 사용 금지 — 예약어)', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('생성', 'created', 'created', '행 생성', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('수정', 'updated', 'updated', '행 최종 수정', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('사용', 'use', 'use', '사용 중 여부', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('순서', 'sort', 'sort', '표시 순서', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('값', 'val', 'value', '실제 내용 값', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('유형', 'type', 'type', '분류 유형', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('승인', 'aprv', 'approval', '사용자 승인 근거(인용·승인자·대상)', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('코드', 'cd', 'code', '분류어: 코드값', true) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('번호', 'no', 'number', '분류어: 업무 식별 번호', true) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('명', 'nm', 'name', '분류어: 명칭', true) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('식별자', 'id', 'identifier', '분류어: 시스템 대리키', true) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('여부', 'yn', 'yes_no', '분류어: 참/거짓', true) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('시각', 'at', 'timestamp', '분류어: 일시', true) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('수', 'cnt', 'count', '분류어: 건수', true) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('해시', 'hash', 'hash', '분류어: 단방향 해시값', true) ON CONFLICT DO NOTHING;
INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES ('밀리초', 'ms', 'millisecond', '분류어: 시간(ms)', true) ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('식별자', 'bigint', NULL, '1001', '시스템 대리키') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('코드(10)', 'varchar(10)', NULL, 'SYS', '짧은 코드값') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('코드(30)', 'varchar(30)', NULL, 'DATA_ANALYST', '긴 코드값') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('명칭(100)', 'varchar(100)', NULL, '데이터분석팀', '명칭') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('명칭(200)', 'varchar(200)', NULL, '전국 어린이집 표준데이터', '긴 명칭') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('물리명', 'varchar(63)', NULL, 'student', 'PostgreSQL 식별자(63자)') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('API명', 'varchar(63)', '~ ''^[a-z][a-z0-9_]{1,62}$''', 'sales_daily', 'API 경로명(소문자·숫자·_)') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('로그인ID', 'varchar(50)', '~ ''^[a-z][a-z0-9_.-]{2,49}$''', 'team_bi', '로그인 아이디') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('계정유형', 'varchar(10)', 'IN (''USER'',''TEAM'',''SYSTEM'')', 'TEAM', '개인·팀·시스템 계정') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('원천유형', 'varchar(10)', 'IN (''FILE'',''URL'',''API'',''PUBLIC'')', 'PUBLIC', '데이터 출처 유형') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('저장유형', 'varchar(10)', 'IN (''DB'',''LAKE'')', 'DB', 'DB 테이블 / 디스크(Parquet) 저장') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('작업상태', 'varchar(10)', 'IN (''READY'',''RUNNING'',''DONE'',''FAIL'')', 'DONE', '적재 작업 상태') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('등급순위', 'smallint', 'BETWEEN 0 AND 1000', '90', '등급 순위(클수록 상위)') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('여부', 'boolean', NULL, 'true', '참/거짓') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('순서', 'integer', NULL, '1', '표시 순서') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('건수', 'bigint', '>= 0', '10000', '0 이상 건수·크기') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('밀리초', 'integer', 'BETWEEN 100 AND 600000', '15000', '실행 제한시간(ms)') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('경과밀리초', 'integer', '>= 0', '35', '소요 시간(ms)') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('시각', 'timestamptz', NULL, '2026-10-05 21:00+09', '일시(시간대 포함)') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('설명', 'text', NULL, '…', '자유 설명') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('SQL문', 'text', NULL, 'SELECT …', '등록 SQL (SELECT 단일문)') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('JSON', 'jsonb', NULL, '[]', '구조화 값') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('URL', 'text', NULL, 'https://www.data.go.kr/…', '주소·경로') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('해시문', 'text', NULL, '$argon2id$…', 'argon2id 해시 문자열(단방향)') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('해시값', 'bytea', NULL, '\x…', 'HMAC-SHA256 32바이트(단방향)') ON CONFLICT DO NOTHING;
INSERT INTO meta.domain (domain_name, data_type, check_rule, example, description) VALUES ('키접두', 'varchar(12)', NULL, 'dpk_ab12cd', 'API 키 앞부분(식별용·비밀 아님)') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('등급', 'grade', '등급', NULL, '접근 등급. rank 가 클수록 상위(s=100). 계정은 등급 하나') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('등급코드', 'grade_cd', '등급>코드', (SELECT domain_id FROM meta.domain WHERE domain_name = '코드(10)'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('등급명', 'grade_nm', '등급>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '명칭(100)'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('등급순위', 'grade_rank', '등급>순위', (SELECT domain_id FROM meta.domain WHERE domain_name = '등급순위'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('사용여부', 'use_yn', '사용>여부', (SELECT domain_id FROM meta.domain WHERE domain_name = '여부'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('생성시각', 'created_at', '생성>시각', (SELECT domain_id FROM meta.domain WHERE domain_name = '시각'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('수정시각', 'updated_at', '수정>시각', (SELECT domain_id FROM meta.domain WHERE domain_name = '시각'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('분류', 'category', '분류', NULL, '데이터 분류. 계정은 여러 분류 권한을 가질 수 있음') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('분류코드', 'ctgr_cd', '분류>코드', (SELECT domain_id FROM meta.domain WHERE domain_name = '코드(10)'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('분류명', 'ctgr_nm', '분류>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '명칭(100)'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('순서번호', 'sort_no', '순서>번호', (SELECT domain_id FROM meta.domain WHERE domain_name = '순서'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('계정', 'account', '계정', NULL, '개인·팀·시스템 계정. 등급 1개 + 관리자 여부. 비밀번호는 argon2id 단방향') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('계정식별자', 'acct_id', '계정>식별자', (SELECT domain_id FROM meta.domain WHERE domain_name = '식별자'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('로그인식별자', 'login_id', '로그인>식별자', (SELECT domain_id FROM meta.domain WHERE domain_name = '로그인ID'), '업무 자연키') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('계정명', 'acct_nm', '계정>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '명칭(100)'), '표시명(팀명·시스템명). 개인 성명은 저장하지 않음') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('계정유형코드', 'acct_type_cd', '계정>유형>코드', (SELECT domain_id FROM meta.domain WHERE domain_name = '계정유형'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('관리자여부', 'admin_yn', '관리자>여부', (SELECT domain_id FROM meta.domain WHERE domain_name = '여부'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('비밀번호해시', 'pwd_hash', '비밀번호>해시', (SELECT domain_id FROM meta.domain WHERE domain_name = '해시문'), 'API 키만 쓰는 시스템 계정은 NULL') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('계정분류권한', 'account_category', '계정>분류', NULL, '계정이 보유한 분류 권한(N:M)') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('계정키', 'account_key', '계정>키', NULL, '팀·시스템 계정용 API 키. 키 원문은 저장하지 않고 HMAC 해시만 보관') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('키식별자', 'key_id', '키>식별자', (SELECT domain_id FROM meta.domain WHERE domain_name = '식별자'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('키접두', 'key_prefix', '키>접두', (SELECT domain_id FROM meta.domain WHERE domain_name = '키접두'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('키해시', 'key_hash', '키>해시', (SELECT domain_id FROM meta.domain WHERE domain_name = '해시값'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('만료시각', 'expire_at', '만료>시각', (SELECT domain_id FROM meta.domain WHERE domain_name = '시각'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('역할', 'role', '역할', NULL, '분류 권한·API 사용권한 묶음. 계정에 역할을 주면 묶음 전체가 부여됨') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('역할코드', 'role_cd', '역할>코드', (SELECT domain_id FROM meta.domain WHERE domain_name = '코드(30)'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('역할명', 'role_nm', '역할>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '명칭(100)'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('역할설명', 'role_desc', '역할>설명', (SELECT domain_id FROM meta.domain WHERE domain_name = '설명'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('역할분류권한', 'role_category', '역할>분류', NULL, '역할이 가진 분류 권한') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('역할멤버', 'role_member', '역할>멤버', NULL, '역할을 부여받은 계정') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('감사로그', 'audit_log', '감사>로그', NULL, '계정·권한·정책·API 변경 기록') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('로그식별자', 'log_id', '로그>식별자', (SELECT domain_id FROM meta.domain WHERE domain_name = '식별자'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('행위코드', 'act_cd', '행위>코드', (SELECT domain_id FROM meta.domain WHERE domain_name = '코드(30)'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('대상값', 'target_val', '대상>값', (SELECT domain_id FROM meta.domain WHERE domain_name = '설명'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('상세값', 'dtl_val', '상세>값', (SELECT domain_id FROM meta.domain WHERE domain_name = 'JSON'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('객체정책', 'object_policy', '객체>정책', NULL, '스키마/테이블별 최소 등급·분류. 정책이 없으면 전체 허용. table_nm=''*'' 는 스키마 전체, 테이블 정책이 우선') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('정책식별자', 'plcy_id', '정책>식별자', (SELECT domain_id FROM meta.domain WHERE domain_name = '식별자'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('스키마명', 'schema_nm', '스키마>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '물리명'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('테이블명', 'table_nm', '테이블>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '물리명'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('최소등급코드', 'min_grade_cd', '최소>등급>코드', (SELECT domain_id FROM meta.domain WHERE domain_name = '코드(10)'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('API정의', 'api_definition', 'API>정의', NULL, '등록 쿼리 기반 조회 API. SELECT 단일문만 허용, 호출자 DB 권한으로 실행') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('API식별자', 'api_id', 'API>식별자', (SELECT domain_id FROM meta.domain WHERE domain_name = '식별자'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('API명', 'api_nm', 'API>명', (SELECT domain_id FROM meta.domain WHERE domain_name = 'API명'), '호출 경로 /q/{api_nm}') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('API설명', 'api_desc', 'API>설명', (SELECT domain_id FROM meta.domain WHERE domain_name = '설명'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('SQL값', 'sql_val', 'SQL>값', (SELECT domain_id FROM meta.domain WHERE domain_name = 'SQL문'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('파라미터값', 'param_val', '파라미터>값', (SELECT domain_id FROM meta.domain WHERE domain_name = 'JSON'), '[{name,type,required,default}]') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('최대행수', 'max_row_cnt', '최대>행>수', (SELECT domain_id FROM meta.domain WHERE domain_name = '건수'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('제한시간밀리초', 'timeout_ms', '제한시간>밀리초', (SELECT domain_id FROM meta.domain WHERE domain_name = '밀리초'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('소유계정식별자', 'owner_acct_id', '소유>계정>식별자', (SELECT domain_id FROM meta.domain WHERE domain_name = '식별자'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('API사용권한', 'api_grant', 'API>부여', NULL, 'API 사용권한 — 계정 또는 역할 단위로 관리자만 부여') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('부여식별자', 'grant_id', '부여>식별자', (SELECT domain_id FROM meta.domain WHERE domain_name = '식별자'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('부여계정식별자', 'grant_acct_id', '부여>계정>식별자', (SELECT domain_id FROM meta.domain WHERE domain_name = '식별자'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('행위정책', 'action_policy', '행위>정책', NULL, '플랫폼 행위별 최소 등급·관리자 필요 여부(로그인=목록 조회 이상)') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('행위명', 'act_nm', '행위>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '명칭(100)'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('호출로그', 'call_log', '호출>로그', NULL, 'API 호출 기록. 파라미터 원문 대신 HMAC 해시') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('파라미터해시', 'param_hash', '파라미터>해시', (SELECT domain_id FROM meta.domain WHERE domain_name = '해시값'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('행수', 'row_cnt', '행>수', (SELECT domain_id FROM meta.domain WHERE domain_name = '건수'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('경과밀리초', 'elapsed_ms', '경과>밀리초', (SELECT domain_id FROM meta.domain WHERE domain_name = '경과밀리초'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('결과코드', 'result_cd', '결과>코드', (SELECT domain_id FROM meta.domain WHERE domain_name = '코드(30)'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('메시지값', 'msg_val', '메시지>값', (SELECT domain_id FROM meta.domain WHERE domain_name = '설명'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('원천', 'source', '원천', NULL, '데이터 출처(파일·URL·API·공공데이터)') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('원천식별자', 'src_id', '원천>식별자', (SELECT domain_id FROM meta.domain WHERE domain_name = '식별자'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('원천명', 'src_nm', '원천>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '명칭(200)'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('원천유형코드', 'src_type_cd', '원천>유형>코드', (SELECT domain_id FROM meta.domain WHERE domain_name = '원천유형'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('원천URL', 'src_url', '원천>URL', (SELECT domain_id FROM meta.domain WHERE domain_name = 'URL'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('제공명', 'provider_nm', '제공>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '명칭(100)'), '제공 기관') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('라이선스명', 'license_nm', '라이선스>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '명칭(100)'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('원천설명', 'src_desc', '원천>설명', (SELECT domain_id FROM meta.domain WHERE domain_name = '설명'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('작업', 'job', '작업', NULL, '적재 작업 1건 = 원천 1개 → 대상 테이블/데이터셋 1개') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('작업식별자', 'job_id', '작업>식별자', (SELECT domain_id FROM meta.domain WHERE domain_name = '식별자'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('대상스키마명', 'target_schema_nm', '대상>스키마>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '물리명'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('대상테이블명', 'target_table_nm', '대상>테이블>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '물리명'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('저장유형코드', 'store_type_cd', '저장>유형>코드', (SELECT domain_id FROM meta.domain WHERE domain_name = '저장유형'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('상태코드', 'status_cd', '상태>코드', (SELECT domain_id FROM meta.domain WHERE domain_name = '작업상태'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('바이트수', 'byte_cnt', '바이트>수', (SELECT domain_id FROM meta.domain WHERE domain_name = '건수'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('프로파일값', 'profile_val', '프로파일>값', (SELECT domain_id FROM meta.domain WHERE domain_name = 'JSON'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('승인값', 'aprv_val', '승인>값', (SELECT domain_id FROM meta.domain WHERE domain_name = 'JSON'), '{by, quote, physical_quote, at, plan_sha256, …} — 사용자 답 인용') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('시작시각', 'start_at', '시작>시각', (SELECT domain_id FROM meta.domain WHERE domain_name = '시각'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('종료시각', 'end_at', '종료>시각', (SELECT domain_id FROM meta.domain WHERE domain_name = '시각'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('레이크데이터셋', 'lake_dataset', '레이크>데이터셋', NULL, '디스크(Parquet) 기반 대용량·로그성 데이터 카탈로그. 조회는 DuckDB') ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('데이터셋식별자', 'dataset_id', '데이터셋>식별자', (SELECT domain_id FROM meta.domain WHERE domain_name = '식별자'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('데이터셋명', 'dataset_nm', '데이터셋>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '물리명'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('경로값', 'path_val', '경로>값', (SELECT domain_id FROM meta.domain WHERE domain_name = 'URL'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('파티션컬럼명', 'partition_col_nm', '파티션>컬럼>명', (SELECT domain_id FROM meta.domain WHERE domain_name = '물리명'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('파일형식코드', 'file_fmt_cd', '파일>형식>코드', (SELECT domain_id FROM meta.domain WHERE domain_name = '코드(10)'), NULL) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('sec', 'grade', '등급', '코드', '접근 등급. rank 가 클수록 상위(s=100). 계정은 등급 하나', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'grade', 'grade_cd', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'grade_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'grade', 'grade_nm', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'grade_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'grade', 'grade_rank', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'grade_rank'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'grade', 'use_yn', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'use_yn'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'grade', 'created_at', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'grade', 'updated_at', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('sec', 'category', '분류', '코드', '데이터 분류. 계정은 여러 분류 권한을 가질 수 있음', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'category', 'ctgr_cd', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'ctgr_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'category', 'ctgr_nm', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'ctgr_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'category', 'sort_no', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'sort_no'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'category', 'use_yn', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'use_yn'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'category', 'created_at', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'category', 'updated_at', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('sec', 'account', '계정', '기준', '개인·팀·시스템 계정. 등급 1개 + 관리자 여부. 비밀번호는 argon2id 단방향', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account', 'acct_id', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'acct_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account', 'login_id', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'login_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account', 'acct_nm', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'acct_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account', 'acct_type_cd', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'acct_type_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account', 'grade_cd', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'grade_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account', 'admin_yn', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'admin_yn'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account', 'pwd_hash', 7, (SELECT term_id FROM meta.term WHERE phys_name = 'pwd_hash'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account', 'use_yn', 8, (SELECT term_id FROM meta.term WHERE phys_name = 'use_yn'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account', 'created_at', 9, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account', 'updated_at', 10, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('sec', 'account_category', '계정분류권한', '거래', '계정이 보유한 분류 권한(N:M)', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account_category', 'acct_id', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'acct_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account_category', 'ctgr_cd', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'ctgr_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account_category', 'created_at', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account_category', 'updated_at', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('sec', 'account_key', '계정키', '기준', '팀·시스템 계정용 API 키. 키 원문은 저장하지 않고 HMAC 해시만 보관', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account_key', 'key_id', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'key_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account_key', 'acct_id', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'acct_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account_key', 'key_prefix', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'key_prefix'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account_key', 'key_hash', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'key_hash'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account_key', 'expire_at', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'expire_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account_key', 'use_yn', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'use_yn'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account_key', 'created_at', 7, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'account_key', 'updated_at', 8, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('sec', 'role', '역할', '기준', '분류 권한·API 사용권한 묶음. 계정에 역할을 주면 묶음 전체가 부여됨', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role', 'role_cd', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'role_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role', 'role_nm', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'role_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role', 'role_desc', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'role_desc'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role', 'use_yn', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'use_yn'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role', 'created_at', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role', 'updated_at', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('sec', 'role_category', '역할분류권한', '거래', '역할이 가진 분류 권한', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role_category', 'role_cd', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'role_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role_category', 'ctgr_cd', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'ctgr_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role_category', 'created_at', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role_category', 'updated_at', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('sec', 'role_member', '역할멤버', '거래', '역할을 부여받은 계정', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role_member', 'role_cd', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'role_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role_member', 'acct_id', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'acct_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role_member', 'created_at', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'role_member', 'updated_at', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('sec', 'audit_log', '감사로그', '이력', '계정·권한·정책·API 변경 기록', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'audit_log', 'log_id', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'log_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'audit_log', 'acct_id', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'acct_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'audit_log', 'act_cd', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'act_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'audit_log', 'target_val', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'target_val'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'audit_log', 'dtl_val', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'dtl_val'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'audit_log', 'created_at', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('sec', 'audit_log', 'updated_at', 7, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('meta', 'object_policy', '객체정책', '기준', '스키마/테이블별 최소 등급·분류. 정책이 없으면 전체 허용. table_nm=''*'' 는 스키마 전체, 테이블 정책이 우선', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('meta', 'object_policy', 'plcy_id', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'plcy_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('meta', 'object_policy', 'schema_nm', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'schema_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('meta', 'object_policy', 'table_nm', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'table_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('meta', 'object_policy', 'min_grade_cd', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'min_grade_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('meta', 'object_policy', 'ctgr_cd', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'ctgr_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('meta', 'object_policy', 'use_yn', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'use_yn'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('meta', 'object_policy', 'created_at', 7, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('meta', 'object_policy', 'updated_at', 8, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('api', 'api_definition', 'API정의', '기준', '등록 쿼리 기반 조회 API. SELECT 단일문만 허용, 호출자 DB 권한으로 실행', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_definition', 'api_id', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'api_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_definition', 'api_nm', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'api_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_definition', 'api_desc', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'api_desc'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_definition', 'sql_val', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'sql_val'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_definition', 'param_val', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'param_val'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_definition', 'max_row_cnt', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'max_row_cnt'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_definition', 'timeout_ms', 7, (SELECT term_id FROM meta.term WHERE phys_name = 'timeout_ms'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_definition', 'owner_acct_id', 8, (SELECT term_id FROM meta.term WHERE phys_name = 'owner_acct_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_definition', 'use_yn', 9, (SELECT term_id FROM meta.term WHERE phys_name = 'use_yn'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_definition', 'created_at', 10, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_definition', 'updated_at', 11, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('api', 'api_grant', 'API사용권한', '거래', 'API 사용권한 — 계정 또는 역할 단위로 관리자만 부여', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_grant', 'grant_id', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'grant_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_grant', 'api_id', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'api_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_grant', 'acct_id', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'acct_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_grant', 'role_cd', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'role_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_grant', 'grant_acct_id', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'grant_acct_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_grant', 'created_at', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'api_grant', 'updated_at', 7, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('api', 'action_policy', '행위정책', '코드', '플랫폼 행위별 최소 등급·관리자 필요 여부(로그인=목록 조회 이상)', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'action_policy', 'act_cd', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'act_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'action_policy', 'act_nm', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'act_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'action_policy', 'min_grade_cd', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'min_grade_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'action_policy', 'admin_yn', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'admin_yn'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'action_policy', 'use_yn', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'use_yn'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'action_policy', 'created_at', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'action_policy', 'updated_at', 7, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('api', 'call_log', '호출로그', '이력', 'API 호출 기록. 파라미터 원문 대신 HMAC 해시', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'call_log', 'log_id', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'log_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'call_log', 'api_id', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'api_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'call_log', 'acct_id', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'acct_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'call_log', 'param_hash', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'param_hash'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'call_log', 'row_cnt', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'row_cnt'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'call_log', 'elapsed_ms', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'elapsed_ms'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'call_log', 'result_cd', 7, (SELECT term_id FROM meta.term WHERE phys_name = 'result_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'call_log', 'msg_val', 8, (SELECT term_id FROM meta.term WHERE phys_name = 'msg_val'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'call_log', 'created_at', 9, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('api', 'call_log', 'updated_at', 10, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('ingest', 'source', '원천', '기준', '데이터 출처(파일·URL·API·공공데이터)', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'source', 'src_id', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'src_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'source', 'src_nm', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'src_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'source', 'src_type_cd', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'src_type_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'source', 'src_url', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'src_url'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'source', 'provider_nm', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'provider_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'source', 'license_nm', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'license_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'source', 'src_desc', 7, (SELECT term_id FROM meta.term WHERE phys_name = 'src_desc'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'source', 'use_yn', 8, (SELECT term_id FROM meta.term WHERE phys_name = 'use_yn'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'source', 'created_at', 9, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'source', 'updated_at', 10, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('ingest', 'job', '작업', '거래', '적재 작업 1건 = 원천 1개 → 대상 테이블/데이터셋 1개', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'job_id', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'job_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'src_id', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'src_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'target_schema_nm', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'target_schema_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'target_table_nm', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'target_table_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'store_type_cd', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'store_type_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'status_cd', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'status_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'row_cnt', 7, (SELECT term_id FROM meta.term WHERE phys_name = 'row_cnt'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'byte_cnt', 8, (SELECT term_id FROM meta.term WHERE phys_name = 'byte_cnt'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'profile_val', 9, (SELECT term_id FROM meta.term WHERE phys_name = 'profile_val'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'msg_val', 10, (SELECT term_id FROM meta.term WHERE phys_name = 'msg_val'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'aprv_val', 11, (SELECT term_id FROM meta.term WHERE phys_name = 'aprv_val'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'start_at', 12, (SELECT term_id FROM meta.term WHERE phys_name = 'start_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'end_at', 13, (SELECT term_id FROM meta.term WHERE phys_name = 'end_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'acct_id', 14, (SELECT term_id FROM meta.term WHERE phys_name = 'acct_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'created_at', 15, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'job', 'updated_at', 16, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.table_catalog (schema_name, table_name, kor_name, table_kind, description, is_pi) VALUES ('ingest', 'lake_dataset', '레이크데이터셋', '기준', '디스크(Parquet) 기반 대용량·로그성 데이터 카탈로그. 조회는 DuckDB', false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'lake_dataset', 'dataset_id', 1, (SELECT term_id FROM meta.term WHERE phys_name = 'dataset_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'lake_dataset', 'dataset_nm', 2, (SELECT term_id FROM meta.term WHERE phys_name = 'dataset_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'lake_dataset', 'path_val', 3, (SELECT term_id FROM meta.term WHERE phys_name = 'path_val'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'lake_dataset', 'partition_col_nm', 4, (SELECT term_id FROM meta.term WHERE phys_name = 'partition_col_nm'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'lake_dataset', 'file_fmt_cd', 5, (SELECT term_id FROM meta.term WHERE phys_name = 'file_fmt_cd'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'lake_dataset', 'row_cnt', 6, (SELECT term_id FROM meta.term WHERE phys_name = 'row_cnt'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'lake_dataset', 'byte_cnt', 7, (SELECT term_id FROM meta.term WHERE phys_name = 'byte_cnt'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'lake_dataset', 'src_id', 8, (SELECT term_id FROM meta.term WHERE phys_name = 'src_id'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'lake_dataset', 'use_yn', 9, (SELECT term_id FROM meta.term WHERE phys_name = 'use_yn'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'lake_dataset', 'created_at', 10, (SELECT term_id FROM meta.term WHERE phys_name = 'created_at'), false) ON CONFLICT DO NOTHING;
INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) VALUES ('ingest', 'lake_dataset', 'updated_at', 11, (SELECT term_id FROM meta.term WHERE phys_name = 'updated_at'), false) ON CONFLICT DO NOTHING;

-- ===== sec, api, ingest: 업무 테이블 =====
-- 등급 (코드)
CREATE TABLE sec.grade (
  grade_cd       varchar(10) NOT NULL,
  grade_nm       varchar(100) NOT NULL,
  grade_rank     smallint NOT NULL,
  use_yn         boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_grade PRIMARY KEY (grade_cd),
  CONSTRAINT uk_grade_grade_rank UNIQUE (grade_rank),
  CONSTRAINT ck_grade_grade_rank CHECK (grade_rank BETWEEN 0 AND 1000)
);
INSERT INTO sec.grade (grade_cd, grade_nm, grade_rank) VALUES ('s', 'S등급', 100);
INSERT INTO sec.grade (grade_cd, grade_nm, grade_rank) VALUES ('a', 'A등급', 90);
INSERT INTO sec.grade (grade_cd, grade_nm, grade_rank) VALUES ('b', 'B등급', 80);
INSERT INTO sec.grade (grade_cd, grade_nm, grade_rank) VALUES ('c', 'C등급', 70);
INSERT INTO sec.grade (grade_cd, grade_nm, grade_rank) VALUES ('d', 'D등급', 60);
INSERT INTO sec.grade (grade_cd, grade_nm, grade_rank) VALUES ('e', 'E등급', 50);

-- 분류 (코드)
CREATE TABLE sec.category (
  ctgr_cd        varchar(10) NOT NULL,
  ctgr_nm        varchar(100) NOT NULL,
  sort_no        integer NOT NULL DEFAULT 0,
  use_yn         boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_category PRIMARY KEY (ctgr_cd)
);
INSERT INTO sec.category (ctgr_cd, ctgr_nm, sort_no) VALUES ('PI', '개인정보', 1);
INSERT INTO sec.category (ctgr_cd, ctgr_nm, sort_no) VALUES ('SALES', '매출', 2);
INSERT INTO sec.category (ctgr_cd, ctgr_nm, sort_no) VALUES ('SCORE', '성적', 3);
INSERT INTO sec.category (ctgr_cd, ctgr_nm, sort_no) VALUES ('HR', '인사', 4);
INSERT INTO sec.category (ctgr_cd, ctgr_nm, sort_no) VALUES ('GA', '총무', 5);
INSERT INTO sec.category (ctgr_cd, ctgr_nm, sort_no) VALUES ('SYS', '시스템', 6);

-- 계정 (기준)
CREATE TABLE sec.account (
  acct_id        bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  login_id       varchar(50) NOT NULL,
  acct_nm        varchar(100) NOT NULL,
  acct_type_cd   varchar(10) NOT NULL DEFAULT 'USER',
  grade_cd       varchar(10) NOT NULL,
  admin_yn       boolean NOT NULL DEFAULT false,
  pwd_hash       text,
  use_yn         boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_account PRIMARY KEY (acct_id),
  CONSTRAINT uk_account_login_id UNIQUE (login_id),
  CONSTRAINT ck_account_login_id CHECK (login_id ~ '^[a-z][a-z0-9_.-]{2,49}$'),
  CONSTRAINT ck_account_acct_type_cd CHECK (acct_type_cd IN ('USER','TEAM','SYSTEM'))
);

-- 계정분류권한 (거래)
CREATE TABLE sec.account_category (
  acct_id        bigint NOT NULL,
  ctgr_cd        varchar(10) NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_account_category PRIMARY KEY (acct_id, ctgr_cd)
);

-- 계정키 (기준)
CREATE TABLE sec.account_key (
  key_id         bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  acct_id        bigint NOT NULL,
  key_prefix     varchar(12) NOT NULL,
  key_hash       bytea NOT NULL,
  expire_at      timestamptz,
  use_yn         boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_account_key PRIMARY KEY (key_id),
  CONSTRAINT uk_account_key_key_prefix UNIQUE (key_prefix)
);

-- 역할 (기준)
CREATE TABLE sec.role (
  role_cd        varchar(30) NOT NULL,
  role_nm        varchar(100) NOT NULL,
  role_desc      text,
  use_yn         boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_role PRIMARY KEY (role_cd)
);

-- 역할분류권한 (거래)
CREATE TABLE sec.role_category (
  role_cd        varchar(30) NOT NULL,
  ctgr_cd        varchar(10) NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_role_category PRIMARY KEY (role_cd, ctgr_cd)
);

-- 역할멤버 (거래)
CREATE TABLE sec.role_member (
  role_cd        varchar(30) NOT NULL,
  acct_id        bigint NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_role_member PRIMARY KEY (role_cd, acct_id)
);

-- 감사로그 (이력)
CREATE TABLE sec.audit_log (
  log_id         bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  acct_id        bigint,
  act_cd         varchar(30) NOT NULL,
  target_val     text,
  dtl_val        jsonb,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_audit_log PRIMARY KEY (log_id)
);

-- 객체정책 (기준)
CREATE TABLE meta.object_policy (
  plcy_id        bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  schema_nm      varchar(63) NOT NULL,
  table_nm       varchar(63) NOT NULL DEFAULT '*',
  min_grade_cd   varchar(10),
  ctgr_cd        varchar(10),
  use_yn         boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_object_policy PRIMARY KEY (plcy_id),
  CONSTRAINT uk_object_policy_schema_nm_table_nm UNIQUE (schema_nm, table_nm)
);

-- API정의 (기준)
CREATE TABLE api.api_definition (
  api_id         bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  api_nm         varchar(63) NOT NULL,
  api_desc       text,
  sql_val        text NOT NULL,
  param_val      jsonb NOT NULL DEFAULT '[]'::jsonb,
  max_row_cnt    bigint NOT NULL DEFAULT 10000,
  timeout_ms     integer NOT NULL DEFAULT 15000,
  owner_acct_id  bigint,
  use_yn         boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_api_definition PRIMARY KEY (api_id),
  CONSTRAINT uk_api_definition_api_nm UNIQUE (api_nm),
  CONSTRAINT ck_api_definition_api_nm CHECK (api_nm ~ '^[a-z][a-z0-9_]{1,62}$'),
  CONSTRAINT ck_api_definition_max_row_cnt CHECK (max_row_cnt >= 0),
  CONSTRAINT ck_api_definition_timeout_ms CHECK (timeout_ms BETWEEN 100 AND 600000)
);

-- API사용권한 (거래)
CREATE TABLE api.api_grant (
  grant_id       bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  api_id         bigint NOT NULL,
  acct_id        bigint,
  role_cd        varchar(30),
  grant_acct_id  bigint,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_api_grant PRIMARY KEY (grant_id),
  CONSTRAINT uk_api_grant_api_id_acct_id UNIQUE (api_id, acct_id),
  CONSTRAINT uk_api_grant_api_id_role_cd UNIQUE (api_id, role_cd),
  CONSTRAINT ck_api_grant_target CHECK ((acct_id IS NOT NULL) <> (role_cd IS NOT NULL))
);

-- 행위정책 (코드)
CREATE TABLE api.action_policy (
  act_cd         varchar(30) NOT NULL,
  act_nm         varchar(100) NOT NULL,
  min_grade_cd   varchar(10) NOT NULL,
  admin_yn       boolean NOT NULL DEFAULT false,
  use_yn         boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_action_policy PRIMARY KEY (act_cd)
);
INSERT INTO api.action_policy (act_cd, act_nm, min_grade_cd, admin_yn) VALUES ('LOGIN', '로그인', 'b', False);
INSERT INTO api.action_policy (act_cd, act_nm, min_grade_cd, admin_yn) VALUES ('LIST', 'API 목록 조회', 'b', False);
INSERT INTO api.action_policy (act_cd, act_nm, min_grade_cd, admin_yn) VALUES ('MODIFY', 'API 생성·변경·삭제', 'a', True);
INSERT INTO api.action_policy (act_cd, act_nm, min_grade_cd, admin_yn) VALUES ('GRANT', 'API 사용권한 부여·회수', 'a', True);
INSERT INTO api.action_policy (act_cd, act_nm, min_grade_cd, admin_yn) VALUES ('CALL', 'API 호출(사용권한 별도 필요)', 'e', False);
INSERT INTO api.action_policy (act_cd, act_nm, min_grade_cd, admin_yn) VALUES ('ACCOUNT', '계정·등급·분류·정책 관리', 'a', True);
INSERT INTO api.action_policy (act_cd, act_nm, min_grade_cd, admin_yn) VALUES ('INGEST', '데이터 적재 실행(승인 인용 필수)', 'a', False);

-- 호출로그 (이력)
CREATE TABLE api.call_log (
  log_id         bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  api_id         bigint,
  acct_id        bigint,
  param_hash     bytea,
  row_cnt        bigint,
  elapsed_ms     integer,
  result_cd      varchar(30) NOT NULL,
  msg_val        text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_call_log PRIMARY KEY (log_id),
  CONSTRAINT ck_call_log_row_cnt CHECK (row_cnt >= 0),
  CONSTRAINT ck_call_log_elapsed_ms CHECK (elapsed_ms >= 0)
);

-- 원천 (기준)
CREATE TABLE ingest.source (
  src_id         bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  src_nm         varchar(200) NOT NULL,
  src_type_cd    varchar(10) NOT NULL,
  src_url        text,
  provider_nm    varchar(100),
  license_nm     varchar(100),
  src_desc       text,
  use_yn         boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_source PRIMARY KEY (src_id),
  CONSTRAINT ck_source_src_type_cd CHECK (src_type_cd IN ('FILE','URL','API','PUBLIC'))
);

-- 작업 (거래)
CREATE TABLE ingest.job (
  job_id         bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  src_id         bigint NOT NULL,
  target_schema_nm varchar(63),
  target_table_nm varchar(63),
  store_type_cd  varchar(10) NOT NULL DEFAULT 'DB',
  status_cd      varchar(10) NOT NULL DEFAULT 'READY',
  row_cnt        bigint,
  byte_cnt       bigint,
  profile_val    jsonb,
  msg_val        text,
  aprv_val       jsonb,
  start_at       timestamptz,
  end_at         timestamptz,
  acct_id        bigint,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_job PRIMARY KEY (job_id),
  CONSTRAINT ck_job_store_type_cd CHECK (store_type_cd IN ('DB','LAKE')),
  CONSTRAINT ck_job_status_cd CHECK (status_cd IN ('READY','RUNNING','DONE','FAIL')),
  CONSTRAINT ck_job_row_cnt CHECK (row_cnt >= 0),
  CONSTRAINT ck_job_byte_cnt CHECK (byte_cnt >= 0)
);

-- 레이크데이터셋 (기준)
CREATE TABLE ingest.lake_dataset (
  dataset_id     bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  dataset_nm     varchar(63) NOT NULL,
  path_val       text NOT NULL,
  partition_col_nm varchar(63),
  file_fmt_cd    varchar(10) NOT NULL DEFAULT 'PARQUET',
  row_cnt        bigint,
  byte_cnt       bigint,
  src_id         bigint,
  use_yn         boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_lake_dataset PRIMARY KEY (dataset_id),
  CONSTRAINT uk_lake_dataset_dataset_nm UNIQUE (dataset_nm),
  CONSTRAINT ck_lake_dataset_row_cnt CHECK (row_cnt >= 0),
  CONSTRAINT ck_lake_dataset_byte_cnt CHECK (byte_cnt >= 0)
);

-- ===== 외래키 =====
ALTER TABLE sec.account ADD CONSTRAINT fk_account_grade_grade_cd FOREIGN KEY (grade_cd) REFERENCES sec.grade (grade_cd) ON DELETE RESTRICT ON UPDATE NO ACTION;
ALTER TABLE sec.account_category ADD CONSTRAINT fk_account_category_account_acct_id FOREIGN KEY (acct_id) REFERENCES sec.account (acct_id) ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE sec.account_category ADD CONSTRAINT fk_account_category_category_ctgr_cd FOREIGN KEY (ctgr_cd) REFERENCES sec.category (ctgr_cd) ON DELETE RESTRICT ON UPDATE NO ACTION;
ALTER TABLE sec.account_key ADD CONSTRAINT fk_account_key_account_acct_id FOREIGN KEY (acct_id) REFERENCES sec.account (acct_id) ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE sec.role_category ADD CONSTRAINT fk_role_category_role_role_cd FOREIGN KEY (role_cd) REFERENCES sec.role (role_cd) ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE sec.role_category ADD CONSTRAINT fk_role_category_category_ctgr_cd FOREIGN KEY (ctgr_cd) REFERENCES sec.category (ctgr_cd) ON DELETE RESTRICT ON UPDATE NO ACTION;
ALTER TABLE sec.role_member ADD CONSTRAINT fk_role_member_role_role_cd FOREIGN KEY (role_cd) REFERENCES sec.role (role_cd) ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE sec.role_member ADD CONSTRAINT fk_role_member_account_acct_id FOREIGN KEY (acct_id) REFERENCES sec.account (acct_id) ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE sec.audit_log ADD CONSTRAINT fk_audit_log_account_acct_id FOREIGN KEY (acct_id) REFERENCES sec.account (acct_id) ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE meta.object_policy ADD CONSTRAINT fk_object_policy_grade_min_grade_cd FOREIGN KEY (min_grade_cd) REFERENCES sec.grade (grade_cd) ON DELETE RESTRICT ON UPDATE NO ACTION;
ALTER TABLE meta.object_policy ADD CONSTRAINT fk_object_policy_category_ctgr_cd FOREIGN KEY (ctgr_cd) REFERENCES sec.category (ctgr_cd) ON DELETE RESTRICT ON UPDATE NO ACTION;
ALTER TABLE api.api_definition ADD CONSTRAINT fk_api_definition_account_owner_acct_id FOREIGN KEY (owner_acct_id) REFERENCES sec.account (acct_id) ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE api.api_grant ADD CONSTRAINT fk_api_grant_api_definition_api_id FOREIGN KEY (api_id) REFERENCES api.api_definition (api_id) ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE api.api_grant ADD CONSTRAINT fk_api_grant_account_acct_id FOREIGN KEY (acct_id) REFERENCES sec.account (acct_id) ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE api.api_grant ADD CONSTRAINT fk_api_grant_role_role_cd FOREIGN KEY (role_cd) REFERENCES sec.role (role_cd) ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE api.api_grant ADD CONSTRAINT fk_api_grant_account_grant_acct_id FOREIGN KEY (grant_acct_id) REFERENCES sec.account (acct_id) ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE api.action_policy ADD CONSTRAINT fk_action_policy_grade_min_grade_cd FOREIGN KEY (min_grade_cd) REFERENCES sec.grade (grade_cd) ON DELETE RESTRICT ON UPDATE NO ACTION;
ALTER TABLE api.call_log ADD CONSTRAINT fk_call_log_api_definition_api_id FOREIGN KEY (api_id) REFERENCES api.api_definition (api_id) ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE api.call_log ADD CONSTRAINT fk_call_log_account_acct_id FOREIGN KEY (acct_id) REFERENCES sec.account (acct_id) ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE ingest.job ADD CONSTRAINT fk_job_source_src_id FOREIGN KEY (src_id) REFERENCES ingest.source (src_id) ON DELETE RESTRICT ON UPDATE NO ACTION;
ALTER TABLE ingest.job ADD CONSTRAINT fk_job_account_acct_id FOREIGN KEY (acct_id) REFERENCES sec.account (acct_id) ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE ingest.lake_dataset ADD CONSTRAINT fk_lake_dataset_source_src_id FOREIGN KEY (src_id) REFERENCES ingest.source (src_id) ON DELETE SET NULL ON UPDATE NO ACTION;

-- ===== FK 인덱스 =====
CREATE INDEX ix_account_grade_cd ON sec.account (grade_cd);
CREATE INDEX ix_account_category_acct_id ON sec.account_category (acct_id);
CREATE INDEX ix_account_category_ctgr_cd ON sec.account_category (ctgr_cd);
CREATE INDEX ix_account_key_acct_id ON sec.account_key (acct_id);
CREATE INDEX ix_role_category_role_cd ON sec.role_category (role_cd);
CREATE INDEX ix_role_category_ctgr_cd ON sec.role_category (ctgr_cd);
CREATE INDEX ix_role_member_role_cd ON sec.role_member (role_cd);
CREATE INDEX ix_role_member_acct_id ON sec.role_member (acct_id);
CREATE INDEX ix_audit_log_acct_id ON sec.audit_log (acct_id);
CREATE INDEX ix_object_policy_min_grade_cd ON meta.object_policy (min_grade_cd);
CREATE INDEX ix_object_policy_ctgr_cd ON meta.object_policy (ctgr_cd);
CREATE INDEX ix_api_definition_owner_acct_id ON api.api_definition (owner_acct_id);
CREATE INDEX ix_api_grant_api_id ON api.api_grant (api_id);
CREATE INDEX ix_api_grant_acct_id ON api.api_grant (acct_id);
CREATE INDEX ix_api_grant_role_cd ON api.api_grant (role_cd);
CREATE INDEX ix_api_grant_grant_acct_id ON api.api_grant (grant_acct_id);
CREATE INDEX ix_action_policy_min_grade_cd ON api.action_policy (min_grade_cd);
CREATE INDEX ix_call_log_api_id ON api.call_log (api_id);
CREATE INDEX ix_call_log_acct_id ON api.call_log (acct_id);
CREATE INDEX ix_job_src_id ON ingest.job (src_id);
CREATE INDEX ix_job_acct_id ON ingest.job (acct_id);
CREATE INDEX ix_lake_dataset_src_id ON ingest.lake_dataset (src_id);

-- ===== COMMENT (한글 논리명) =====
COMMENT ON TABLE sec.grade IS '등급 — 접근 등급. rank 가 클수록 상위(s=100). 계정은 등급 하나';
COMMENT ON COLUMN sec.grade.grade_cd IS '등급코드';
COMMENT ON COLUMN sec.grade.grade_nm IS '등급명';
COMMENT ON COLUMN sec.grade.grade_rank IS '등급순위';
COMMENT ON COLUMN sec.grade.use_yn IS '사용여부';
COMMENT ON COLUMN sec.grade.created_at IS '생성시각';
COMMENT ON COLUMN sec.grade.updated_at IS '수정시각';
COMMENT ON TABLE sec.category IS '분류 — 데이터 분류. 계정은 여러 분류 권한을 가질 수 있음';
COMMENT ON COLUMN sec.category.ctgr_cd IS '분류코드';
COMMENT ON COLUMN sec.category.ctgr_nm IS '분류명';
COMMENT ON COLUMN sec.category.sort_no IS '순서번호';
COMMENT ON COLUMN sec.category.use_yn IS '사용여부';
COMMENT ON COLUMN sec.category.created_at IS '생성시각';
COMMENT ON COLUMN sec.category.updated_at IS '수정시각';
COMMENT ON TABLE sec.account IS '계정 — 개인·팀·시스템 계정. 등급 1개 + 관리자 여부. 비밀번호는 argon2id 단방향';
COMMENT ON COLUMN sec.account.acct_id IS '계정식별자';
COMMENT ON COLUMN sec.account.login_id IS '로그인식별자 — 업무 자연키';
COMMENT ON COLUMN sec.account.acct_nm IS '계정명 — 표시명(팀명·시스템명). 개인 성명은 저장하지 않음';
COMMENT ON COLUMN sec.account.acct_type_cd IS '계정유형코드';
COMMENT ON COLUMN sec.account.grade_cd IS '등급코드';
COMMENT ON COLUMN sec.account.admin_yn IS '관리자여부';
COMMENT ON COLUMN sec.account.pwd_hash IS '비밀번호해시 — API 키만 쓰는 시스템 계정은 NULL [암호화:argon2id 단방향(인증)]';
COMMENT ON COLUMN sec.account.use_yn IS '사용여부';
COMMENT ON COLUMN sec.account.created_at IS '생성시각';
COMMENT ON COLUMN sec.account.updated_at IS '수정시각';
COMMENT ON TABLE sec.account_category IS '계정분류권한 — 계정이 보유한 분류 권한(N:M)';
COMMENT ON COLUMN sec.account_category.acct_id IS '계정식별자';
COMMENT ON COLUMN sec.account_category.ctgr_cd IS '분류코드';
COMMENT ON COLUMN sec.account_category.created_at IS '생성시각';
COMMENT ON COLUMN sec.account_category.updated_at IS '수정시각';
COMMENT ON TABLE sec.account_key IS '계정키 — 팀·시스템 계정용 API 키. 키 원문은 저장하지 않고 HMAC 해시만 보관';
COMMENT ON COLUMN sec.account_key.key_id IS '키식별자';
COMMENT ON COLUMN sec.account_key.acct_id IS '계정식별자';
COMMENT ON COLUMN sec.account_key.key_prefix IS '키접두';
COMMENT ON COLUMN sec.account_key.key_hash IS '키해시 [암호화:HMAC-SHA256 단방향(검색)]';
COMMENT ON COLUMN sec.account_key.expire_at IS '만료시각';
COMMENT ON COLUMN sec.account_key.use_yn IS '사용여부';
COMMENT ON COLUMN sec.account_key.created_at IS '생성시각';
COMMENT ON COLUMN sec.account_key.updated_at IS '수정시각';
COMMENT ON TABLE sec.role IS '역할 — 분류 권한·API 사용권한 묶음. 계정에 역할을 주면 묶음 전체가 부여됨';
COMMENT ON COLUMN sec.role.role_cd IS '역할코드';
COMMENT ON COLUMN sec.role.role_nm IS '역할명';
COMMENT ON COLUMN sec.role.role_desc IS '역할설명';
COMMENT ON COLUMN sec.role.use_yn IS '사용여부';
COMMENT ON COLUMN sec.role.created_at IS '생성시각';
COMMENT ON COLUMN sec.role.updated_at IS '수정시각';
COMMENT ON TABLE sec.role_category IS '역할분류권한 — 역할이 가진 분류 권한';
COMMENT ON COLUMN sec.role_category.role_cd IS '역할코드';
COMMENT ON COLUMN sec.role_category.ctgr_cd IS '분류코드';
COMMENT ON COLUMN sec.role_category.created_at IS '생성시각';
COMMENT ON COLUMN sec.role_category.updated_at IS '수정시각';
COMMENT ON TABLE sec.role_member IS '역할멤버 — 역할을 부여받은 계정';
COMMENT ON COLUMN sec.role_member.role_cd IS '역할코드';
COMMENT ON COLUMN sec.role_member.acct_id IS '계정식별자';
COMMENT ON COLUMN sec.role_member.created_at IS '생성시각';
COMMENT ON COLUMN sec.role_member.updated_at IS '수정시각';
COMMENT ON TABLE sec.audit_log IS '감사로그 — 계정·권한·정책·API 변경 기록';
COMMENT ON COLUMN sec.audit_log.log_id IS '로그식별자';
COMMENT ON COLUMN sec.audit_log.acct_id IS '계정식별자 — 수행 계정';
COMMENT ON COLUMN sec.audit_log.act_cd IS '행위코드';
COMMENT ON COLUMN sec.audit_log.target_val IS '대상값';
COMMENT ON COLUMN sec.audit_log.dtl_val IS '상세값';
COMMENT ON COLUMN sec.audit_log.created_at IS '생성시각';
COMMENT ON COLUMN sec.audit_log.updated_at IS '수정시각';
COMMENT ON TABLE meta.object_policy IS '객체정책 — 스키마/테이블별 최소 등급·분류. 정책이 없으면 전체 허용. table_nm=''*'' 는 스키마 전체, 테이블 정책이 우선';
COMMENT ON COLUMN meta.object_policy.plcy_id IS '정책식별자';
COMMENT ON COLUMN meta.object_policy.schema_nm IS '스키마명';
COMMENT ON COLUMN meta.object_policy.table_nm IS '테이블명';
COMMENT ON COLUMN meta.object_policy.min_grade_cd IS '최소등급코드';
COMMENT ON COLUMN meta.object_policy.ctgr_cd IS '분류코드';
COMMENT ON COLUMN meta.object_policy.use_yn IS '사용여부';
COMMENT ON COLUMN meta.object_policy.created_at IS '생성시각';
COMMENT ON COLUMN meta.object_policy.updated_at IS '수정시각';
COMMENT ON TABLE api.api_definition IS 'API정의 — 등록 쿼리 기반 조회 API. SELECT 단일문만 허용, 호출자 DB 권한으로 실행';
COMMENT ON COLUMN api.api_definition.api_id IS 'API식별자';
COMMENT ON COLUMN api.api_definition.api_nm IS 'API명 — 호출 경로 /q/{api_nm}';
COMMENT ON COLUMN api.api_definition.api_desc IS 'API설명';
COMMENT ON COLUMN api.api_definition.sql_val IS 'SQL값';
COMMENT ON COLUMN api.api_definition.param_val IS '파라미터값 — [{name,type,required,default}]';
COMMENT ON COLUMN api.api_definition.max_row_cnt IS '최대행수';
COMMENT ON COLUMN api.api_definition.timeout_ms IS '제한시간밀리초';
COMMENT ON COLUMN api.api_definition.owner_acct_id IS '소유계정식별자';
COMMENT ON COLUMN api.api_definition.use_yn IS '사용여부';
COMMENT ON COLUMN api.api_definition.created_at IS '생성시각';
COMMENT ON COLUMN api.api_definition.updated_at IS '수정시각';
COMMENT ON TABLE api.api_grant IS 'API사용권한 — API 사용권한 — 계정 또는 역할 단위로 관리자만 부여';
COMMENT ON COLUMN api.api_grant.grant_id IS '부여식별자';
COMMENT ON COLUMN api.api_grant.api_id IS 'API식별자';
COMMENT ON COLUMN api.api_grant.acct_id IS '계정식별자';
COMMENT ON COLUMN api.api_grant.role_cd IS '역할코드';
COMMENT ON COLUMN api.api_grant.grant_acct_id IS '부여계정식별자';
COMMENT ON COLUMN api.api_grant.created_at IS '생성시각';
COMMENT ON COLUMN api.api_grant.updated_at IS '수정시각';
COMMENT ON TABLE api.action_policy IS '행위정책 — 플랫폼 행위별 최소 등급·관리자 필요 여부(로그인=목록 조회 이상)';
COMMENT ON COLUMN api.action_policy.act_cd IS '행위코드';
COMMENT ON COLUMN api.action_policy.act_nm IS '행위명';
COMMENT ON COLUMN api.action_policy.min_grade_cd IS '최소등급코드';
COMMENT ON COLUMN api.action_policy.admin_yn IS '관리자여부';
COMMENT ON COLUMN api.action_policy.use_yn IS '사용여부';
COMMENT ON COLUMN api.action_policy.created_at IS '생성시각';
COMMENT ON COLUMN api.action_policy.updated_at IS '수정시각';
COMMENT ON TABLE api.call_log IS '호출로그 — API 호출 기록. 파라미터 원문 대신 HMAC 해시';
COMMENT ON COLUMN api.call_log.log_id IS '로그식별자';
COMMENT ON COLUMN api.call_log.api_id IS 'API식별자';
COMMENT ON COLUMN api.call_log.acct_id IS '계정식별자';
COMMENT ON COLUMN api.call_log.param_hash IS '파라미터해시 [암호화:HMAC-SHA256 단방향(검색)]';
COMMENT ON COLUMN api.call_log.row_cnt IS '행수';
COMMENT ON COLUMN api.call_log.elapsed_ms IS '경과밀리초';
COMMENT ON COLUMN api.call_log.result_cd IS '결과코드';
COMMENT ON COLUMN api.call_log.msg_val IS '메시지값';
COMMENT ON COLUMN api.call_log.created_at IS '생성시각';
COMMENT ON COLUMN api.call_log.updated_at IS '수정시각';
COMMENT ON TABLE ingest.source IS '원천 — 데이터 출처(파일·URL·API·공공데이터)';
COMMENT ON COLUMN ingest.source.src_id IS '원천식별자';
COMMENT ON COLUMN ingest.source.src_nm IS '원천명';
COMMENT ON COLUMN ingest.source.src_type_cd IS '원천유형코드';
COMMENT ON COLUMN ingest.source.src_url IS '원천URL';
COMMENT ON COLUMN ingest.source.provider_nm IS '제공명 — 제공 기관';
COMMENT ON COLUMN ingest.source.license_nm IS '라이선스명';
COMMENT ON COLUMN ingest.source.src_desc IS '원천설명';
COMMENT ON COLUMN ingest.source.use_yn IS '사용여부';
COMMENT ON COLUMN ingest.source.created_at IS '생성시각';
COMMENT ON COLUMN ingest.source.updated_at IS '수정시각';
COMMENT ON TABLE ingest.job IS '작업 — 적재 작업 1건 = 원천 1개 → 대상 테이블/데이터셋 1개';
COMMENT ON COLUMN ingest.job.job_id IS '작업식별자';
COMMENT ON COLUMN ingest.job.src_id IS '원천식별자';
COMMENT ON COLUMN ingest.job.target_schema_nm IS '대상스키마명';
COMMENT ON COLUMN ingest.job.target_table_nm IS '대상테이블명';
COMMENT ON COLUMN ingest.job.store_type_cd IS '저장유형코드';
COMMENT ON COLUMN ingest.job.status_cd IS '상태코드';
COMMENT ON COLUMN ingest.job.row_cnt IS '행수';
COMMENT ON COLUMN ingest.job.byte_cnt IS '바이트수';
COMMENT ON COLUMN ingest.job.profile_val IS '프로파일값';
COMMENT ON COLUMN ingest.job.msg_val IS '메시지값';
COMMENT ON COLUMN ingest.job.aprv_val IS '승인값 — {by, quote, physical_quote, at, plan_sha256, …} — 사용자 답 인용';
COMMENT ON COLUMN ingest.job.start_at IS '시작시각';
COMMENT ON COLUMN ingest.job.end_at IS '종료시각';
COMMENT ON COLUMN ingest.job.acct_id IS '계정식별자';
COMMENT ON COLUMN ingest.job.created_at IS '생성시각';
COMMENT ON COLUMN ingest.job.updated_at IS '수정시각';
COMMENT ON TABLE ingest.lake_dataset IS '레이크데이터셋 — 디스크(Parquet) 기반 대용량·로그성 데이터 카탈로그. 조회는 DuckDB';
COMMENT ON COLUMN ingest.lake_dataset.dataset_id IS '데이터셋식별자';
COMMENT ON COLUMN ingest.lake_dataset.dataset_nm IS '데이터셋명';
COMMENT ON COLUMN ingest.lake_dataset.path_val IS '경로값';
COMMENT ON COLUMN ingest.lake_dataset.partition_col_nm IS '파티션컬럼명';
COMMENT ON COLUMN ingest.lake_dataset.file_fmt_cd IS '파일형식코드';
COMMENT ON COLUMN ingest.lake_dataset.row_cnt IS '행수';
COMMENT ON COLUMN ingest.lake_dataset.byte_cnt IS '바이트수';
COMMENT ON COLUMN ingest.lake_dataset.src_id IS '원천식별자';
COMMENT ON COLUMN ingest.lake_dataset.use_yn IS '사용여부';
COMMENT ON COLUMN ingest.lake_dataset.created_at IS '생성시각';
COMMENT ON COLUMN ingest.lake_dataset.updated_at IS '수정시각';

-- ===== 접근 정책 (data-platform 설치 시 meta.object_policy 에 등록) =====
DO $$ BEGIN
  IF to_regclass('meta.object_policy') IS NOT NULL THEN
    INSERT INTO meta.object_policy (schema_nm, table_nm, min_grade_cd, ctgr_cd) VALUES ('sec', '*', 'a', 'SYS') ON CONFLICT (schema_nm, table_nm) DO UPDATE SET min_grade_cd = EXCLUDED.min_grade_cd, ctgr_cd = EXCLUDED.ctgr_cd, updated_at = now();
    INSERT INTO meta.object_policy (schema_nm, table_nm, min_grade_cd, ctgr_cd) VALUES ('api', '*', 'a', 'SYS') ON CONFLICT (schema_nm, table_nm) DO UPDATE SET min_grade_cd = EXCLUDED.min_grade_cd, ctgr_cd = EXCLUDED.ctgr_cd, updated_at = now();
    INSERT INTO meta.object_policy (schema_nm, table_nm, min_grade_cd, ctgr_cd) VALUES ('ingest', '*', 'b', 'SYS') ON CONFLICT (schema_nm, table_nm) DO UPDATE SET min_grade_cd = EXCLUDED.min_grade_cd, ctgr_cd = EXCLUDED.ctgr_cd, updated_at = now();
    INSERT INTO meta.object_policy (schema_nm, table_nm, min_grade_cd, ctgr_cd) VALUES ('pi', '*', NULL, 'PI') ON CONFLICT (schema_nm, table_nm) DO UPDATE SET min_grade_cd = EXCLUDED.min_grade_cd, ctgr_cd = EXCLUDED.ctgr_cd, updated_at = now();
  END IF;
END $$;

COMMIT;