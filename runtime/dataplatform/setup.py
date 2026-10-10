"""플랫폼 설치(init)·키 생성·키 교체."""
from __future__ import annotations
import os, re
import yaml
from .crypto import Crypto, new_key_hex
from . import access, accounts
from .db import audit

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM_DDL = os.path.join(HERE, "model", "platform_ddl.sql")
PLUGIN_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DM_SCRIPTS = os.path.join(PLUGIN_ROOT, "skills", "data-modeling", "scripts")


def keygen(path: str | None, write: bool = False) -> dict:
    """128비트 키를 임의 생성. write=True 면 설정 파일의 빈 키만 채운다(기존 키는 절대 덮어쓰지 않음)."""
    data = {}
    if path and os.path.exists(path):
        data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    c = data.setdefault("crypto", {})
    keys = {int(k): v for k, v in (c.get("keys") or {}).items()}
    made = {}
    act = int(c.get("active_key", 1))
    if not keys.get(act):
        keys[act] = made[f"keys.{act}"] = new_key_hex()
    if not c.get("hmac_key"):
        c["hmac_key"] = made["hmac_key"] = new_key_hex()
    c["keys"] = keys; c["active_key"] = act
    a = data.setdefault("api", {})
    if not a.get("jwt_secret"):
        a["jwt_secret"] = made["api.jwt_secret"] = new_key_hex() + new_key_hex()
    if write and path:
        if not os.path.exists(path):
            ex = os.path.join(PLUGIN_ROOT, "runtime", "config", "system.example.yaml")
            base = yaml.safe_load(open(ex, encoding="utf-8"))
            base.update({k: v for k, v in data.items() if k not in ("crypto", "api")})
            base["crypto"] = data["crypto"]; base.setdefault("api", {}).update(data["api"])
            data = base
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return made


def init(conn, cfg, admin_login="admin", admin_password=None, admin_name="플랫폼 관리자") -> dict:
    """공통 스키마(meta·sec·api·ingest·pi) 생성 + 기본 관리자 + 접근 동기화. 이미 설치돼 있으면 건너뛴다(멱등)."""
    rep = {}
    installed = conn.execute("SELECT to_regclass('sec.account') IS NOT NULL AS ok").fetchone()["ok"]
    if not installed:
        if conn.execute("SELECT to_regclass('meta.word') IS NOT NULL AS ok").fetchone()["ok"]:
            rep["meta"] = "기존 meta 사전 재사용(공유 모드)"
        conn.execute(open(PLATFORM_DDL, encoding="utf-8").read())
        rep["ddl"] = "created"
    else:
        rep["ddl"] = "already installed"
        rep["upgrade"] = upgrade(conn)
    conn.execute("CREATE SCHEMA IF NOT EXISTS pi")
    conn.execute("REVOKE ALL ON SCHEMA pi FROM PUBLIC")
    conn.execute("INSERT INTO api.api_definition (api_nm, api_desc, sql_val, param_val) VALUES "
                 "('sys_table_read', '내장: /data/{schema}/{table} 단순 조회(호출자 DB 권한으로 실행)', '-- builtin', '[]') "
                 "ON CONFLICT (api_nm) DO NOTHING")
    has_admin = conn.execute("SELECT count(*) n FROM sec.account WHERE admin_yn").fetchone()["n"]
    if not has_admin:
        if not admin_password:
            raise ValueError("최초 설치에는 관리자 비밀번호가 필요합니다 (--admin-password)")
        cats = [r["ctgr_cd"] for r in conn.execute("SELECT ctgr_cd FROM sec.category")]
        accounts.create_account(conn, Crypto(cfg["crypto"]), admin_login, admin_name, "s", "USER", True, admin_password, cats)
        rep["admin"] = admin_login
    conn.commit()
    rep["sync"] = access.sync(conn, cfg)
    return rep


# 이미 설치된 DB 를 새 버전 공통 스키마에 맞추는 단계(멱등). 정본(platform_model.json)과 같은 내용을 ALTER 로 반영한다.
UPGRADES = [
    ("2.1-ingest-approval", [
        "ALTER TABLE ingest.job ADD COLUMN IF NOT EXISTS aprv_val jsonb",
        "COMMENT ON COLUMN ingest.job.aprv_val IS '승인값 — {by, quote, physical_quote, at, plan_sha256, …} — 사용자 답 인용'",
        "INSERT INTO meta.word (kor_name, eng_abbr, eng_full, description, is_class) VALUES "
        "('승인', 'aprv', 'approval', '사용자 승인 근거(인용·승인자·대상)', false) ON CONFLICT DO NOTHING",
        "INSERT INTO meta.term (kor_name, phys_name, word_path, domain_id, description) VALUES ('승인값', 'aprv_val', '승인>값', "
        "(SELECT domain_id FROM meta.domain WHERE domain_name = 'JSON'), '{by, quote, physical_quote, at, plan_sha256, …} — 사용자 답 인용') ON CONFLICT DO NOTHING",
        "INSERT INTO meta.column_catalog (schema_name, table_name, column_name, ordinal, term_id, is_pi) "
        "SELECT 'ingest', 'job', 'aprv_val', 99, term_id, false FROM meta.term WHERE phys_name = 'aprv_val' ON CONFLICT DO NOTHING",
        "INSERT INTO api.action_policy (act_cd, act_nm, min_grade_cd, admin_yn) VALUES "
        "('INGEST', '데이터 적재 실행(승인 인용 필수)', 'a', false) ON CONFLICT (act_cd) DO NOTHING",
    ]),
]


def upgrade(conn) -> list[str]:
    done = []
    for name, stmts in UPGRADES:
        for q in stmts:
            conn.execute(q)
        done.append(name)
    conn.commit()
    return done


def rotate_keys(conn, cfg) -> dict:
    """active_key 가 아닌 키로 암호화된 AES 값을 active_key 로 재암호화.
    대상 컬럼은 COMMENT 의 [암호화:AES-128 …] 표시로 찾는다(export_all.py 가 붙임)."""
    cr = Crypto(cfg["crypto"])
    cols = conn.execute(
        "SELECT n.nspname s, c.relname t, a.attname col FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_description d ON d.objoid=c.oid AND d.objsubid=a.attnum "
        "WHERE d.description LIKE '%%[암호화:AES-128%%' AND c.relkind='r'").fetchall()
    rep = {}
    from psycopg import sql
    for r in cols:
        pk = conn.execute("SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum = ANY(i.indkey) "
                          "WHERE i.indrelid = (%s)::regclass AND i.indisprimary", (f'{r["s"]}.{r["t"]}',)).fetchall()
        pkc = [x["attname"] for x in pk]
        tid = sql.SQL("{}.{}").format(sql.Identifier(r["s"]), sql.Identifier(r["t"]))
        rows = conn.execute(sql.SQL("SELECT {}, {} v FROM {} WHERE {} IS NOT NULL AND get_byte({}, 0) <> %s").format(
            sql.SQL(", ").join(map(sql.Identifier, pkc)), sql.Identifier(r["col"]), tid, sql.Identifier(r["col"]),
            sql.Identifier(r["col"])), (cr.active,)).fetchall()
        for row in rows:
            new = cr.encrypt(cr.decrypt(row["v"]))
            conn.execute(sql.SQL("UPDATE {} SET {} = %s WHERE ").format(tid, sql.Identifier(r["col"])) +
                         sql.SQL(" AND ").join(sql.SQL("{} = %s").format(sql.Identifier(c)) for c in pkc),
                         (new, *[row[c] for c in pkc]))
        rep[f'{r["s"]}.{r["t"]}.{r["col"]}'] = len(rows)
    audit(conn, None, "KEY_ROTATE", None, rep)
    conn.commit()
    return rep
