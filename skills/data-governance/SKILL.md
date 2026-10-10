---
name: data-governance
description: data-platform 설치·운영 — 시스템 설정 파일과 128비트 암호화 키, 공통 스키마 설치, 계정(개인·팀·시스템)·등급(s>a>b…)·분류(개인정보·매출·성적·인사·총무·시스템…)·역할 관리, 스키마/테이블 접근정책과 PostgreSQL 롤 동기화, 개인정보(pi 스키마) 관리 롤과 양방향/단방향 암호화·키 교체, 용어 시스템(bomiyang-glossary 또는 meta) 설정. "권한 관리", "계정 만들어", "등급 설정", "개인정보 암호화", "접근 권한", "팀 계정", "API 키 발급", "암호화 키", "데이터 플랫폼 설치" 등에 사용.
---

# 개인정보·권한·접근 관리 (data-governance)

`dp …` = `PYTHONPATH=$RT python -m dataplatform --config $CFG …` (`$RT` = 플러그인 루트 `runtime/`, `$CFG` = system.yaml)

## 1. 설치 (처음 한 번)
```bash
pip install -r $RT/requirements.txt
cp $RT/config/system.example.yaml config/system.yaml      # DB 접속(dsn), 용어 경로 등 수정
dp keygen --write                                          # 빈 키만 128비트 임의 생성(기존 키는 절대 덮어쓰지 않음)
dp init --admin-password '<관리자 비밀번호>'                # meta 확장·sec·api·ingest·pi 스키마 + admin(s, 관리자, 전 분류) + 동기화
```
- 설정 파일 `crypto.keys.<번호>`(AES)·`crypto.hmac_key`(HMAC)는 **16진수 32자리 = 128비트**. 사용자가 직접 정한 값을 넣어도 된다(길이 검사함). 파일 권한 600, 저장소에 올리지 않게 안내.
- DB 서비스 계정은 superuser 또는 CREATEROLE 권한 필요(계정별 DB 롤 생성·SET ROLE).
- 운영 DB 에 init 하기 전 대상 DB 를 반드시 확인한다.
- 이미 설치된 DB 에 새 버전을 올릴 때도 `dp init` 을 다시 실행한다 — 공통 스키마 변경분을 멱등 업그레이드로 반영한다(예: 2.1 적재 승인 컬럼·INGEST 행위 정책).

## 2. 등급 × 분류 모델
- **등급**: s(100) > a(90) > b(80) > c(70) > d(60) > e(50). 계정은 등급 **하나**. 추가: `dp grade add f --name F등급 --rank 40`.
- **분류**: PI(개인정보)·SALES(매출)·SCORE(성적)·HR(인사)·GA(총무)·SYS(시스템). 계정은 분류 **여러 개**. 추가: `dp category add FIN --name 재무`.
- **접근 판정**: 정책 없는 스키마/테이블 = 전체 허용. 정책이 있으면 `등급 ≥ 최소등급` **그리고** `(분류 없음 또는 계정이 그 분류 보유)`. 테이블 정책이 스키마 정책(`--table '*'`)보다 우선.
- **역할(role)**: 분류 묶음(+ API 사용권한 대상). 역할의 분류는 멤버 계정에 합쳐진다.
- 기본 정책: `sec`·`api` = a + SYS, `ingest` = b + SYS, `pi` = PI 분류만(등급 무관).

## 3. 자주 쓰는 명령
```bash
dp account add team_bi --name "BI팀" --grade b --type TEAM --category SALES        # 팀 계정 (시스템 간 연동용)
dp key issue team_bi --days 365                       # API 키(원문은 한 번만 표시, DB 엔 HMAC 만)
dp account add kim --name "김OO" --grade a --admin --password '…' --category SYS  # API 관리자
dp account update kim --add-category SALES --grade s
dp role add SCORE_VIEW --name "성적 조회" --category SCORE ; dp role members SCORE_VIEW --add user1
dp policy set acad --table enrollment --min-grade c --category SCORE              # 테이블 정책
dp policy set hr --min-grade a --category HR                                       # 스키마 전체
dp account explain team_bi                            # 이 계정이 볼 수 있는/없는 테이블
dp sync                                               # 정책·계정 → DB 롤/GRANT 반영(멱등)
```
변경 명령은 자동으로 sync 하고 `sec.audit_log`에 남긴다. 테이블을 새로 만든 뒤(직접 DDL 실행 시)에는 `dp sync`를 꼭 실행한다 — 그 전까지 새 테이블은 아무도(소유자 제외) 못 본다.

### 동기화 범위 — 다른 앱의 테이블은 건드리지 않는다
`sync` 가 GRANT/REVOKE 하는 스키마는 **관리 대상**뿐이다: 플랫폼 스키마(meta·sec·api·ingest·pi) + 플랫폼으로 만든 스키마(`meta.table_catalog` 등록분 — data-modeling·적재로 만든 것) + 접근정책을 건 스키마 + 설정 `access.managed_schemas`. 같은 DB 를 쓰는 다른 앱의 스키마는 권한을 바꾸지 않고, API 조회·등록에서도 거부한다. 기존 스키마를 플랫폼 관리로 넣으려면 `managed_schemas: [그 스키마]` 를 적고 `dp sync` — 그 순간 PUBLIC 권한이 회수되니 그 앱 담당자와 먼저 확인한다. 플랫폼 전용 DB 면 `"*"`.

### DB 에서는 어떻게 강제되나
- 계정마다 롤 `dpu_<login>`, 보호 테이블마다 롤 `dpt_<schema>__<table>`, 공개 테이블은 `dp_open`.
- 판정을 통과한 계정 롤에만 테이블 롤을 GRANT → API 는 `SET ROLE dpu_<login>` 으로 실행하므로 **DB 가 최종 판정**한다.
- 팀이 DB 에 직접 붙어야 하면: `ALTER ROLE dpu_<login> LOGIN PASSWORD '…'` (관리자 판단).

## 4. 개인정보
- 저장 위치: `pi` 스키마 `pi_<본테이블>`(1:1, 본체 삭제 시 CASCADE). 본 테이블엔 개인정보 없음.
- 관리 롤: **PI 분류를 가진 계정**만 `pi` 스키마를 조회한다(예: `dp account add pi_mgr --grade b --category PI`).
- 암호화 방식(성격별):

| 방식 | 대상 | 저장 |
|---|---|---|
| 양방향 AES-128-GCM | 성명·전화·이메일·주소·계좌·카드 등 다시 볼 값 | `<컬럼>_enc` bytea (맨 앞 1바이트 = 키 번호) |
| 단방향 HMAC-SHA256(128비트 키) | 주민번호·전화 등 **일치 검색**만 필요한 값, API 키, 호출 파라미터 | `<컬럼>_hash` bytea |
| 단방향 argon2id | 비밀번호 | text |

- 복호화·마스킹은 런타임에서: `from dataplatform.crypto import Crypto, mask` → `Crypto(cfg["crypto"]).decrypt(v)`, `mask("010-1234-5678")` → `010-****-5678`.
- **키 교체**: 설정에 새 번호 키 추가 → `active_key` 변경 → `dp rotate-keys`(COMMENT `[암호화:AES-128…]` 컬럼 재암호화). 옛 키는 재암호화 완료 확인 후에만 지운다.
- 비밀번호 기준(일방향)·고유식별정보/계좌/카드 등(양방향) 구분은 개인정보 안전성 확보조치 기준의 일반적 구분을 따른 것이다 — 실제 적용 범위는 운영 기관의 기준으로 최종 확인하라고 안내한다.

## 5. 용어 시스템
- 기본 bomiyang-glossary: `glossary.bomiyang_path`에 클론(`git clone https://github.com/sungbeom78/bomiyang-glossary`). 등록은 GlossaryWriter 경유.
- 없으면 자동으로 `meta.word`(공통 스키마) 사용. 강제하려면 `glossary.mode: meta`.
- 확인: `dp glossary info`, `dp glossary check stud_no`, `dp glossary split 사업장명`, 등록: `dp glossary add --kor 가맹점 --abbr frch --full franchise`.

## 6. 점검
- `python -m pytest -q $RT/tests` (`DP_TEST_DSN`=관리자 DSN, 선택 `DP_TEST_BOMIYANG`=클론 경로) — 임시 DB 에서 암호화·권한·적재·API 전 과정을 검증하고 지운다.
