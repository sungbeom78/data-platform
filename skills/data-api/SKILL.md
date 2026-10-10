---
name: data-api
description: data-platform 의 데이터 조회 API 를 만들고 운영한다 — SELECT 쿼리를 등록해 /q/{이름} REST API 로 공개, 관리자 계정만 생성·변경, 등급별 행위 권한(a 이상 변경·b 이상 목록/로그인), API 별 사용권한을 계정·팀·역할에 부여, 팀/시스템 계정 API 키, 호출 로그. "조회 API 만들어", "쿼리 API 등록", "API 권한 부여", "팀에 API 열어줘", "데이터 API 서버", "API 키" 등에 사용.
---

# 조회 API (data-api)

`dp …` = `PYTHONPATH=$RT python -m dataplatform --config $CFG …`

## 권한 구조 (api.action_policy — 표 값만 바꾸면 조정됨)
| 행위 | 기본 조건 |
|---|---|
| LOGIN (토큰 발급·API 접속) | 등급 ≥ b (= 목록 조회 이상만 로그인 가능) |
| LIST (API 목록 조회) | 등급 ≥ b |
| MODIFY (API 생성·변경·삭제) | 등급 ≥ a **그리고** 관리자 |
| GRANT (API 사용권한 부여·회수) | 등급 ≥ a **그리고** 관리자 |
| CALL (API 호출) | 등급 ≥ e **그리고 그 API 의 사용권한**(계정·역할 단위, 관리자가 부여) |

조정 예: `UPDATE api.action_policy SET min_grade_cd='a' WHERE act_cd='LIST';`

추가 안전장치:
- 등록 SQL 은 **SELECT 한 문장만**(INSERT/UPDATE/DELETE·CTE 안 DML·SELECT INTO·FOR UPDATE·`pg_sleep` 등 위험 함수 거부, pglast 파서로 검사).
- 등록하는 관리자가 접근할 수 없는 테이블을 참조하면 등록 거부(정책 우회 방지).
- 실행은 읽기 전용 트랜잭션 + `statement_timeout` + 행 제한 + **`SET ROLE <호출 계정 롤>`** → 사용권한이 있어도 등급/분류 정책상 못 보는 테이블이면 403.
- 호출 로그 `api.call_log`(파라미터는 HMAC 해시만), 변경 이력 `sec.audit_log`.

## 만들기
1. 질문 정리: 무엇을·누가(팀/역할)·파라미터·최대 행 수.
2. SQL 작성 — 파라미터는 `:이름`. 이름은 소문자·숫자·`_`.
3. 등록(관리자):
   ```bash
   dp api create sales_by_month --by kim \
     --sql "SELECT biz_nm, sales_amt FROM pub.shop WHERE to_char(open_dt,'YYYYMM') = :ym ORDER BY sales_amt DESC" \
     --params '[{"name":"ym","type":"text","required":true}]' --max-rows 1000 --timeout-ms 10000 --desc "월별 매출"
   dp api grant sales_by_month --login team_bi --by kim       # 계정/팀에게
   dp api grant sales_by_month --role SALES_TEAM --by kim     # 역할에게
   dp api list
   ```
   파라미터 type: text·int·number·bool·date. 선언 안 한 `:파라미터`는 필수 text 로 자동 등록.
4. 서버 실행: `dp serve` (설정 `api.host`/`api.port`, 기본 8800). 문서: `http://<host>:8800/docs`.

## 호출 (사용자에게 안내할 예)
```bash
# 개인 계정: 토큰
curl -X POST :8800/auth/token -H 'Content-Type: application/json' -d '{"login_id":"kim","password":"…"}'
curl ':8800/q/sales_by_month?ym=202609' -H "Authorization: Bearer <token>"
# 팀/시스템 계정: API 키
curl ':8800/q/sales_by_month?ym=202609' -H "X-API-Key: dpk_…"
# 내장 단순 조회(사용권한 'sys_table_read' 필요): 컬럼=값 필터, limit
curl ':8800/data/pub/shop?biz_nm=가게3&limit=50' -H "X-API-Key: dpk_…"
```
응답: `{"api","columns","rows","row_count","truncated","elapsed_ms"}`. 오류: 401 인증, 403 행위/사용권한/데이터 정책, 400 파라미터·SQL, 504 시간 초과.

REST 로도 관리 가능(관리자 토큰): `POST /apis`, `PUT/DELETE /apis/{이름}`, `POST/DELETE/GET /apis/{이름}/grants` (body `{"login_id": …}` 또는 `{"role_cd": …}`), `GET /me`.

## 보고 형식
```
## API sales_by_month
- GET /q/sales_by_month?ym=YYYYMM  · 최대 1,000행 · 10초
- 참조: pub.shop (정책 b/SALES) · 사용권한: team_bi, 역할 SALES_TEAM
- 호출 예(curl) …
```
