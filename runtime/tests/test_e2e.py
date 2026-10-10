"""data-platform 종단 테스트 — 실제 PostgreSQL 필요.

실행:  DP_TEST_DSN=postgresql://postgres:pw@localhost:5432/postgres  python -m pytest -q runtime/tests
       (DSN 의 DB 에 접속해 임시 DB dp_e2e_xxxx 를 만들고 끝나면 지운다. superuser 권장)
"""
from __future__ import annotations
import json, os, random, string, sys, csv
import pytest
import psycopg

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
from dataplatform.config import load as load_cfg            # noqa: E402
from dataplatform.db import connect                          # noqa: E402
from dataplatform.crypto import Crypto, new_key_hex, mask     # noqa: E402
from dataplatform import access, accounts, setup             # noqa: E402
from dataplatform.glossary import open_glossary, MetaGlossary, BomiyangGlossary  # noqa: E402
from dataplatform.ingest.plan import make_plan               # noqa: E402
from dataplatform.ingest.load import apply, PlanError        # noqa: E402
from dataplatform.api.sqlguard import check, SqlRejected     # noqa: E402

BASE = os.environ.get("DP_TEST_DSN")
pytestmark = pytest.mark.skipif(not BASE, reason="DP_TEST_DSN 미설정")
PW = "Test!234"


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("dp")
    name = "dp_e2e_" + "".join(random.choices(string.ascii_lowercase, k=6))
    with psycopg.connect(BASE, autocommit=True) as c:
        c.execute(f"CREATE DATABASE {name}")
    dsn = BASE.rsplit("/", 1)[0] + "/" + name
    cfgp = tmp / "system.yaml"
    setup.keygen(str(cfgp), write=True)
    import yaml
    d = yaml.safe_load(open(cfgp, encoding="utf-8"))
    d["database"] = {"dsn": dsn}
    d["glossary"] = {"mode": "auto", "bomiyang_path": str(tmp / "none")}
    d["ingest"].update({"work_dir": str(tmp / "work"), "lake_dir": str(tmp / "lake"), "large_rows": 5000})
    yaml.safe_dump(d, open(cfgp, "w", encoding="utf-8"), allow_unicode=True)
    cfg = load_cfg(str(cfgp))
    conn = connect(cfg)
    rep = setup.init(conn, cfg, "admin", PW)
    assert rep["ddl"] == "created"
    yield {"cfg": cfg, "conn": conn, "tmp": tmp, "cr": Crypto(cfg["crypto"])}
    conn.close()
    roles = None
    with psycopg.connect(BASE, autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
        # 테스트가 만든 롤 정리 (dpu_/dpt_ 는 클러스터 전역)
        for (r,) in c.execute("SELECT rolname FROM pg_roles WHERE rolname LIKE 'dpu\\_%' OR rolname LIKE 'dpt\\_%'").fetchall():
            try:
                c.execute(f'DROP ROLE "{r}"')
            except psycopg.Error:
                pass


# ---------------- 1. 암호화 ----------------
def test_crypto_roundtrip(env):
    cr = env["cr"]
    blob = cr.encrypt("010-1234-5678")
    assert blob[0] == 1 and len(blob) > 28 and b"010" not in blob
    assert cr.decrypt(blob) == "010-1234-5678"
    assert cr.hmac("010-1234-5678") == cr.hmac("01012345678")      # 정규화 후 같은 해시
    assert len(cr.hmac("x")) == 32
    h = cr.hash_password("pw"); assert cr.verify_password(h, "pw") and not cr.verify_password(h, "no")
    assert mask("김민준") == "김*준" and mask("010-9999-2222") == "010-****-2222"


def test_key_must_be_128bit():
    from dataplatform.crypto import CryptoError
    with pytest.raises(CryptoError):
        Crypto({"active_key": 1, "keys": {1: "abcd"}, "hmac_key": new_key_hex()}).encrypt("x")


def test_key_rotation(env):
    cfg, conn = env["cfg"], env["conn"]
    conn.execute("CREATE SCHEMA IF NOT EXISTS rot; CREATE TABLE rot.t (id int PRIMARY KEY, v bytea); "
                 "COMMENT ON COLUMN rot.t.v IS '값 [개인정보] [암호화:AES-128 양방향]'")
    conn.execute("INSERT INTO rot.t VALUES (1, %s)", (env["cr"].encrypt("홍길동"),)); conn.commit()
    cfg2 = json.loads(json.dumps(cfg)); cfg2["crypto"]["keys"] = {1: cfg["crypto"]["keys"][1], 2: new_key_hex()}; cfg2["crypto"]["active_key"] = 2
    rep = setup.rotate_keys(conn, cfg2)
    assert rep["rot.t.v"] == 1
    v = conn.execute("SELECT v FROM rot.t").fetchone()["v"]
    assert bytes(v)[0] == 2 and Crypto(cfg2["crypto"]).decrypt(v) == "홍길동"
    conn.execute("DROP SCHEMA rot CASCADE"); conn.commit()


def test_upgrade_existing_install(env):
    """이전 버전으로 설치된 DB(승인 컬럼·INGEST 정책 없음)에 init 을 다시 돌리면 멱등 업그레이드된다"""
    conn, cfg = env["conn"], env["cfg"]
    conn.execute("ALTER TABLE ingest.job DROP COLUMN aprv_val"); conn.execute("DELETE FROM api.action_policy WHERE act_cd='INGEST'"); conn.commit()
    rep = setup.init(conn, cfg)
    assert "2.1-ingest-approval" in rep["upgrade"]
    assert conn.execute("SELECT count(*) n FROM information_schema.columns WHERE table_schema='ingest' AND table_name='job' AND column_name='aprv_val'").fetchone()["n"] == 1
    assert conn.execute("SELECT min_grade_cd FROM api.action_policy WHERE act_cd='INGEST'").fetchone()["min_grade_cd"] == "a"
    assert "2.1-ingest-approval" in setup.init(conn, cfg)["upgrade"]           # 두 번 돌려도 오류 없음


def test_utf8_subprocess_and_cli_on_cp949_console(env, tmp_path):
    """Windows(cp949 콘솔·파이프)에서도 한글 출력이 깨지거나 죽지 않는다"""
    import subprocess
    from dataplatform.compat import run_py, posix_path
    r = run_py(["-c", "import sys; print('한글 → 출력', sys.stdout.encoding)"])
    assert r.returncode == 0 and r.stdout.startswith("한글 → 출력") and "utf" in r.stdout.lower()
    cfgp = tmp_path / "s.yaml"
    import yaml; yaml.safe_dump(json.loads(json.dumps(env["cfg"])), open(cfgp, "w", encoding="utf-8"), allow_unicode=True)
    rt = os.path.abspath(os.path.join(HERE, ".."))
    out = subprocess.run([sys.executable, "-m", "dataplatform", "--config", str(cfgp), "glossary", "split", "계정명", "😀이모지"],
                         capture_output=True, env=dict(os.environ, PYTHONPATH=rt, PYTHONIOENCODING="cp949", PYTHONUTF8="0"))
    assert out.returncode == 0, out.stderr.decode("cp949", "replace")
    assert "acct" in out.stdout.decode("cp949")                                   # cp949 로 읽어도 정상
    assert posix_path("C:\\a\\b'c").endswith("b''c") and "\\" not in posix_path("C:\\a\\b")


# ---------------- 2. 계정·등급·분류·DB 롤 ----------------
def test_accounts_and_sync(env):
    conn, cr, cfg = env["conn"], env["cr"], env["cfg"]
    accounts.create_account(conn, cr, "team_bi", "BI팀", "b", "TEAM", False, PW, ["SALES"])
    accounts.create_account(conn, cr, "user_c", "C등급 사용자", "c", "USER", False, PW)
    accounts.create_account(conn, cr, "analyst_a", "분석관리자", "a", "USER", True, PW, ["SYS"])
    accounts.create_account(conn, cr, "boss_s", "S등급(분류 없음)", "s", "USER", False, PW)
    accounts.create_account(conn, cr, "pi_mgr", "개인정보관리", "b", "USER", False, PW, ["PI"])
    accounts.create_role(conn, "SCORE_VIEW", "성적 조회", ["SCORE"])
    accounts.role_members(conn, "SCORE_VIEW", add=["user_c"])
    conn.execute("CREATE SCHEMA biz; CREATE TABLE biz.sales (sales_id int PRIMARY KEY, amt numeric); CREATE TABLE biz.notice (id int PRIMARY KEY, t text);"
                 "INSERT INTO biz.sales VALUES (1, 100); INSERT INTO biz.notice VALUES (1,'공지')")
    accounts.set_policy(conn, "biz", "sales", "b", "SALES")
    conn.commit()
    rep = access.sync(conn, cfg)
    assert rep["protected"] >= 1
    A = lambda l: access.load_account(conn, login_id=l)
    pol = access.load_policies(conn)
    P = lambda s, t: access.effective_policy(pol, s, t)
    assert access.allowed(A("team_bi"), P("biz", "sales"))           # b + SALES
    assert not access.allowed(A("user_c"), P("biz", "sales"))         # 등급 부족
    assert not access.allowed(A("boss_s"), P("biz", "sales"))         # S 라도 분류 없으면 거부
    assert access.allowed(A("user_c"), P("biz", "notice"))            # 정책 없음 = 전체 허용
    assert not access.allowed(A("team_bi"), P("sec", "account"))      # sec = SYS + a
    assert access.allowed(A("analyst_a"), P("sec", "account"))
    assert "SCORE" in A("user_c").categories                          # 역할로 받은 분류
    # DB 네이티브 강제 확인 — SET ROLE 로 실제 조회
    def can(login, q):
        try:
            with conn.transaction():
                conn.execute(f'SET LOCAL ROLE "{access.account_role_name(login)}"')
                conn.execute(q).fetchall()
            return True
        except psycopg.errors.InsufficientPrivilege:
            return False
    assert can("team_bi", "SELECT * FROM biz.sales")
    assert not can("user_c", "SELECT * FROM biz.sales")
    assert can("user_c", "SELECT * FROM biz.notice")
    assert not can("team_bi", "SELECT * FROM sec.account")
    conn.commit()


def test_sync_leaves_other_apps_alone(env):
    """관리 대상이 아닌 스키마(다른 앱)는 sync 가 권한을 바꾸지 않고, API·판정도 거부한다"""
    conn, cfg = env["conn"], env["cfg"]
    conn.execute("CREATE SCHEMA otherapp; CREATE TABLE otherapp.orders (id int PRIMARY KEY); CREATE ROLE otherapp_reader NOLOGIN;"
                 "GRANT USAGE ON SCHEMA otherapp TO PUBLIC; GRANT SELECT ON otherapp.orders TO PUBLIC, otherapp_reader")
    conn.commit()
    rep = access.sync(conn, cfg)
    assert "otherapp" not in rep["managed_schemas"]
    privs = lambda: {(r["grantee"], r["privilege_type"]) for r in conn.execute(
        "SELECT grantee, privilege_type FROM information_schema.role_table_grants WHERE table_schema='otherapp'")}
    assert ("PUBLIC", "SELECT") in privs() and ("otherapp_reader", "SELECT") in privs()     # 그대로
    assert not any(g == access.OPEN_ROLE for g, _ in privs())
    a = access.load_account(conn, login_id="boss_s")
    assert not access.check_table(conn, a, "otherapp", "orders", cfg)
    assert all(x["schema"] != "otherapp" for x in access.explain(conn, a, cfg))
    # 명시적으로 관리 대상에 넣으면 그때부터 관리
    cfg2 = json.loads(json.dumps(cfg)); cfg2["access"]["managed_schemas"] = ["otherapp"]
    access.sync(conn, cfg2)
    assert ("PUBLIC", "SELECT") not in privs() and (access.OPEN_ROLE, "SELECT") in privs()
    conn.execute("DROP SCHEMA otherapp CASCADE; DROP ROLE otherapp_reader"); conn.commit()
    access.sync(conn, cfg)


def test_action_policy(env):
    conn = env["conn"]
    A = lambda l: access.load_account(conn, login_id=l)
    assert access.authorize_action(conn, A("team_bi"), "LOGIN")[0]
    assert not access.authorize_action(conn, A("user_c"), "LOGIN")[0]       # c 는 로그인 불가(목록 조회 b 이상)
    assert access.authorize_action(conn, A("analyst_a"), "MODIFY")[0]       # a + admin
    assert not access.authorize_action(conn, A("boss_s"), "MODIFY")[0]      # s 라도 admin 아님
    assert not access.authorize_action(conn, A("team_bi"), "MODIFY")[0]


# ---------------- 3. 용어 ----------------
def test_glossary_meta_fallback(env):
    gl = open_glossary(env["cfg"], env["conn"])
    assert isinstance(gl, MetaGlossary)                                    # bomiyang 경로 없음 → meta
    assert gl.check_identifier("acct_id") == [] and gl.check_identifier("foo_bar") == ["foo", "bar"]
    ws, rest = gl.compose_kor("계정명"); assert [w.abbr for w in ws] == ["acct", "nm"] and rest == ""


@pytest.mark.skipif(not os.environ.get("DP_TEST_BOMIYANG"), reason="DP_TEST_BOMIYANG(bomiyang-glossary 클론 경로) 미설정")
def test_glossary_bomiyang(env):
    import shutil
    from dataplatform.glossary import Word
    dst = env["tmp"] / "bomiyang"
    shutil.copytree(os.environ["DP_TEST_BOMIYANG"], dst, ignore=shutil.ignore_patterns(".git"))
    cfg = json.loads(json.dumps(env["cfg"])); cfg["glossary"]["bomiyang_path"] = str(dst)
    gl = open_glossary(cfg, env["conn"])
    assert isinstance(gl, BomiyangGlossary) and gl.loaded > 100
    assert gl.lookup("amount") and gl.lookup("amount").abbr == "amt"
    assert gl.lookup("acct")                                              # meta 의 조직 단어도 함께 인식
    done = gl.register([Word("가맹점", "frch", "franchise", False, "가맹 사업장")])  # GlossaryWriter 경유 등록
    assert done
    gl2 = open_glossary(cfg, env["conn"])
    assert gl2.lookup("franchise") and gl2.lookup("frch").kor == "가맹점"
    cfg["glossary"]["mode"] = "meta"
    assert isinstance(open_glossary(cfg, env["conn"]), MetaGlossary)


# ---------------- 4. 적재 (csv cp949, 개인정보 자동 분리·암호화) ----------------
def _csv(path, n=30):
    with open(path, "w", encoding="cp949", newline="") as f:
        w = csv.writer(f)
        w.writerow(["사업장명", "대표자성명", "휴대전화", "개업일자", "직원수", "매출액", "사용여부"])
        for i in range(n):
            w.writerow([f"가게{i}", "김민준" if i % 2 else "이서윤", f"010-1234-{i:04d}", f"2024{(i % 12) + 1:02d}15", i, f"{i * 1000.5:.1f}", "Y"])


def test_ingest_csv_with_pi(env):
    conn, cfg, cr = env["conn"], env["cfg"], env["cr"]
    p = env["tmp"] / "가게.csv"; _csv(p)
    gl = open_glossary(cfg, conn)
    plan = make_plan(cfg, gl, conn, str(p), schema="pub", src_name="가게")
    by = {c["src"]: c for c in plan["columns"]}
    assert by["휴대전화"]["pi"]["crypto"] == "aes+hmac" and by["대표자성명"]["pi"]["pi_type"] == "성명"
    assert by["사업장명"]["pi"] is None                                   # 사업장명은 개인정보 아님
    assert by["개업일자"]["type"] == "date" and by["직원수"]["type"] == "integer"
    assert plan["store"] == "DB"
    with pytest.raises(PlanError):
        apply(conn, cfg, gl, plan)                                           # 승인 전
    # Claude/사용자가 채우는 부분
    words = {"사업장": ("biz", "business_place"), "대표자": ("rep", "representative"), "성명": ("psn", "person"),
             "휴대전화": ("mobile", "mobile"), "개업": ("open", "open"), "직원": ("emp", "employee"),
             "매출액": ("sales", "sales"), "가게": ("shop", "shop")}
    plan["words_to_register"] = [{"kor": k, "abbr": v[0], "full": v[1], "desc": ""} for k, v in words.items()]
    names = {"사업장명": "biz_nm", "대표자성명": "rep_psn_nm", "휴대전화": "mobile_no", "개업일자": "open_dt",
             "직원수": "emp_cnt", "매출액": "sales_amt", "사용여부": "use_yn"}
    for c in plan["columns"]:
        c["name"] = names[c["src"]]
    plan["target"]["table"] = "shop"; plan["target"]["kor"] = "가게"
    plan["target"]["policy"] = {"min_grade": "b", "category": "SALES"}
    plan["approved"] = True
    # 승인 증거: 인용 없음 / 권한 없는 계정 / 새 테이블인데 물리 생성 승인 없음 → 모두 DB 변경 전에 거부
    with pytest.raises(PlanError, match="승인 근거"):
        apply(conn, cfg, gl, plan, approval={"by": "admin", "quote": ""})
    with pytest.raises(PlanError, match="적재 권한"):
        apply(conn, cfg, gl, plan, approval={"by": "team_bi", "quote": "네 적재해 주세요"})
    with pytest.raises(PlanError, match="물리 생성 승인"):
        apply(conn, cfg, gl, plan, approval={"by": "admin", "quote": "네 적재해 주세요"})
    assert conn.execute("SELECT count(*) n FROM ingest.job").fetchone()["n"] == 0
    assert conn.execute("SELECT to_regclass('pub.shop') IS NULL ok").fetchone()["ok"]
    rep = apply(conn, cfg, gl, plan, workdir=str(env["tmp"] / "m_shop"),
                approval={"by": "admin", "quote": "네, 가게 데이터를 pub.shop 으로 적재해 주세요",
                          "physical_quote": "pub.shop 테이블 생성 승인합니다"})
    ev = conn.execute("SELECT aprv_val FROM ingest.job ORDER BY job_id DESC LIMIT 1").fetchone()["aprv_val"]
    assert ev["by"] == "admin" and ev["quote"].startswith("네, 가게") and ev["creates_table"] and ev["physical_quote"]
    assert ev["plan_sha256"] == rep["approval"]["plan_sha256"] and "휴대전화" in ev["pi_columns"]
    au = conn.execute("SELECT dtl_val FROM sec.audit_log WHERE act_cd='INGEST_APPLY' ORDER BY log_id DESC LIMIT 1").fetchone()["dtl_val"]
    assert au["job_id"] and au["quote"] == ev["quote"]
    assert rep["rows"] == 30 and rep["pi_rows"] == 30 and not rep["bad_values"]
    assert os.path.exists(env["tmp"] / "m_shop" / "03_model.dbm")
    cols = {r["column_name"] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='pub' AND table_name='shop'")}
    assert "mobile_no" not in cols and "rep_psn_nm" not in cols             # 본 테이블엔 개인정보 없음
    r = conn.execute("SELECT s.biz_nm, p.mobile_no_enc, p.mobile_no_hash, p.rep_psn_nm_enc FROM pub.shop s JOIN pi.pi_shop p USING (shop_id) "
                     "WHERE s.biz_nm='가게7'").fetchone()
    assert cr.decrypt(r["mobile_no_enc"]) == "010-1234-0007" and cr.decrypt(r["rep_psn_nm_enc"]) == "김민준"
    hit = conn.execute("SELECT count(*) n FROM pi.pi_shop WHERE mobile_no_hash=%s", (cr.hmac("01012340007"),)).fetchone()["n"]
    assert hit == 1                                                          # 해시로 일치 검색
    pol = access.load_policies(conn)
    assert not access.allowed(access.load_account(conn, login_id="team_bi"), access.effective_policy(pol, "pi", "pi_shop"))
    assert access.allowed(access.load_account(conn, login_id="pi_mgr"), access.effective_policy(pol, "pi", "pi_shop"))
    assert access.allowed(access.load_account(conn, login_id="team_bi"), access.effective_policy(pol, "pub", "shop"))
    assert conn.execute("SELECT status_cd FROM ingest.job ORDER BY job_id DESC LIMIT 1").fetchone()["status_cd"] == "DONE"
    # 같은 파일 재적재 → 기존 테이블 매칭(append)
    plan2 = make_plan(cfg, open_glossary(cfg, conn), conn, str(p), schema="pub", src_name="가게")
    assert plan2["target"]["mode"] == "append" and plan2["target"]["table"] == "shop"
    plan2["approved"] = True
    for c in plan2["columns"]:
        c["name"] = names[c["src"]]
    ap2 = {"by": "admin", "quote": "같은 파일 한 번 더 추가해 주세요"}         # 기존 테이블 추가는 물리 생성 승인 불필요
    assert apply(conn, cfg, open_glossary(cfg, conn), plan2, approval=ap2)["rows"] == 30
    assert conn.execute("SELECT count(*) n FROM pi.pi_shop").fetchone()["n"] == 60


def test_ingest_large_goes_to_lake(env):
    conn, cfg = env["conn"], env["cfg"]
    p = env["tmp"] / "access_log.csv"
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["log_at", "user_email", "path", "status"])
        for i in range(6000):
            w.writerow([f"2026-0{(i % 3) + 7}-01 10:00:{i % 60:02d}", f"u{i % 50}@ex.com", f"/p/{i % 7}", 200])
    gl = open_glossary(cfg, conn)
    plan = make_plan(cfg, gl, conn, str(p), schema="logs")
    assert plan["store"] == "LAKE" and plan["store_reasons"]
    gl.register([__import__("dataplatform.glossary", fromlist=["Word"]).Word(k, a, f) for k, a, f in
                 [("이메일", "email", "email"), ("경로", "path", "path"), ("접근", "access", "access")]])
    for c in plan["columns"]:
        c["name"] = {"log_at": "log_at", "user_email": "email", "path": "path", "status": "status_cd"}[c["src"]]
    plan["target"]["table"] = "access_log"; plan["approved"] = True
    rep = apply(conn, cfg, open_glossary(cfg, conn), plan, approval={"by": "admin", "quote": "레이크로 저장해 주세요"})
    assert rep["rows"] == 6000 and rep["dataset"] == "logs__access_log"
    from dataplatform.ingest.lake import query
    df = query(conn, cfg, "SELECT ym, count(*) n FROM logs__access_log GROUP BY 1 ORDER BY 1")
    assert list(df["ym"]) == ["202607", "202608", "202609"] and int(df["n"].sum()) == 6000
    cols = query(conn, cfg, "SELECT * FROM logs__access_log", 1).columns
    assert "email_hash" in cols and "email" not in cols                    # 개인정보 원문은 레이크에 없음


# ---------------- 5. SQL 검사 ----------------
@pytest.mark.parametrize("q", ["DELETE FROM biz.sales", "SELECT 1; SELECT 2", "SELECT pg_sleep(10)",
                               "WITH x AS (DELETE FROM biz.sales RETURNING *) SELECT * FROM x",
                               "SELECT * INTO biz.copy FROM biz.sales", "SELECT * FROM biz.sales FOR UPDATE"])
def test_sqlguard_rejects(q):
    with pytest.raises(SqlRejected):
        check(q)


def test_sqlguard_ok():
    info = check("SELECT s.biz_nm, s.sales_amt::numeric FROM pub.shop s WHERE s.open_dt >= :from_dt AND s.biz_nm LIKE '%가게%'")
    assert info["params"] == ["from_dt"] and ("pub", "shop") in info["tables"]


# ---------------- 6. 조회 API ----------------
def test_api_flow(env):
    from fastapi.testclient import TestClient
    from dataplatform.api.app import create_app
    conn, cfg, cr = env["conn"], env["cfg"], env["cr"]
    c = TestClient(create_app(cfg))
    tok = lambda l: c.post("/auth/token", json={"login_id": l, "password": PW})
    assert tok("user_c").status_code == 403                                  # c 등급 로그인 불가
    assert tok("team_bi").status_code == 200
    H = lambda l: {"Authorization": "Bearer " + tok(l).json()["access_token"]}
    assert c.get("/apis", headers=H("team_bi")).status_code == 200            # b: 목록 조회 가능
    body = {"api_nm": "shop_by_month", "sql": "SELECT biz_nm, emp_cnt, sales_amt FROM pub.shop WHERE to_char(open_dt,'YYYYMM') = :ym ORDER BY biz_nm",
            "params": [{"name": "ym", "type": "text"}], "max_rows": 5}
    assert c.post("/apis", json=body, headers=H("team_bi")).status_code == 403    # b 는 생성 불가
    assert c.post("/apis", json=body, headers=H("boss_s")).status_code == 403     # s 라도 admin 아님
    # analyst_a(a+admin) 는 SALES 분류가 없어 pub.shop(b/SALES) 을 참조하는 API 를 못 만든다
    assert c.post("/apis", json=body, headers=H("analyst_a")).status_code == 403
    accounts.set_categories(conn, "analyst_a", add=["SALES"]); conn.commit(); access.sync(conn, cfg)
    r = c.post("/apis", json=body, headers=H("analyst_a")); assert r.status_code == 200, r.text
    assert c.get("/q/shop_by_month?ym=202403", headers=H("team_bi")).status_code == 403   # 사용권한 없음
    assert c.post("/apis/shop_by_month/grants", json={"login_id": "team_bi"}, headers=H("team_bi")).status_code == 403
    assert c.post("/apis/shop_by_month/grants", json={"login_id": "team_bi"}, headers=H("analyst_a")).status_code == 200
    r = c.get("/q/shop_by_month?ym=202403", headers=H("team_bi")); assert r.status_code == 200, r.text
    j = r.json(); assert j["row_count"] >= 1 and j["columns"] == ["biz_nm", "emp_cnt", "sales_amt"]
    # 팀 계정 API 키
    key = accounts.issue_key(conn, cr, "team_bi"); conn.commit()
    assert c.get("/q/shop_by_month", params={"ym": "202403"}, headers={"X-API-Key": key}).status_code == 200
    assert c.get("/q/shop_by_month", params={"ym": "202403"}, headers={"X-API-Key": key + "x"}).status_code == 401
    # 사용권한은 있지만 DB 정책이 막는 경우: 정책을 올리면 실행 시 403
    accounts.set_policy(conn, "pub", "shop", "a", "SALES"); conn.commit(); access.sync(conn, cfg)
    assert c.get("/q/shop_by_month?ym=202403", headers=H("team_bi")).status_code == 403
    accounts.set_policy(conn, "pub", "shop", "b", "SALES"); conn.commit(); access.sync(conn, cfg)
    # 등록 SQL 검사
    bad = dict(body, api_nm="bad_api", sql="DELETE FROM pub.shop")
    assert c.post("/apis", json=bad, headers=H("analyst_a")).status_code == 400
    # 역할 단위 부여 + 내장 테이블 조회
    accounts.create_role(conn, "SALES_TEAM", "매출팀", ["SALES"]); accounts.create_account(conn, cr, "sales_b", "매출B", "b", "USER", False, PW)
    accounts.role_members(conn, "SALES_TEAM", add=["sales_b"]); conn.commit(); access.sync(conn, cfg)
    assert c.post("/apis/sys_table_read/grants", json={"role_cd": "SALES_TEAM"}, headers=H("analyst_a")).status_code == 200
    r = c.get("/data/pub/shop?biz_nm=가게3", headers=H("sales_b")); assert r.status_code == 200 and r.json()["row_count"] == 2
    assert c.get("/data/pi/pi_shop", headers=H("sales_b")).status_code == 403          # 개인정보 분류 없음
    n = conn.execute("SELECT count(*) n FROM api.call_log").fetchone()["n"]; assert n >= 4
    assert conn.execute("SELECT count(*) n FROM sec.audit_log WHERE act_cd='API_GRANT'").fetchone()["n"] >= 2
