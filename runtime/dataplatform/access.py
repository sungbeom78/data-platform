"""권한·접근 관리 — 등급(s>a>b…) × 분류(개인정보·매출·성적…).

판정:  허용 = (정책 없음) OR ( 계정등급.rank ≥ 정책.min_grade.rank  AND  (정책.분류 없음 OR 계정이 그 분류 보유) )
  - 테이블 정책(table_nm=테이블)이 스키마 정책(table_nm='*')보다 우선
  - 계정 분류 = 계정에 직접 준 분류 ∪ 계정이 속한 역할의 분류
강제(2중):
  1) DB 네이티브: 정책을 PostgreSQL ROLE/GRANT 로 동기화(sync) — 계정별 롤 dpu_<login>, 보호 테이블별 롤 dpt_<…>
  2) API 계층: 같은 판정으로 사전 차단 + 실행은 SET ROLE dpu_<login> 으로 DB 가 최종 확인
"""
from __future__ import annotations
import hashlib, re
from dataclasses import dataclass, field
from psycopg import sql

OPEN_ROLE = "dp_open"


@dataclass
class Account:
    acct_id: int
    login_id: str
    acct_nm: str
    acct_type_cd: str
    grade_cd: str
    grade_rank: int
    admin_yn: bool
    use_yn: bool
    categories: set = field(default_factory=set)
    roles: set = field(default_factory=set)

    @property
    def db_role(self) -> str:
        return account_role_name(self.login_id)


def account_role_name(login_id: str) -> str:
    return "dpu_" + re.sub(r"[^a-z0-9_]", "_", login_id.lower())[:58]


def table_role_name(schema: str, table: str) -> str:
    base = f"dpt_{schema}__{table}"
    if len(base) <= 63:
        return base
    return base[:55] + "_" + hashlib.md5(base.encode()).hexdigest()[:7]


def load_accounts(conn, only_active: bool = False) -> dict[int, Account]:
    rows = conn.execute(
        "SELECT a.acct_id, a.login_id, a.acct_nm, a.acct_type_cd, a.grade_cd, g.grade_rank, a.admin_yn, a.use_yn "
        "FROM sec.account a JOIN sec.grade g ON g.grade_cd = a.grade_cd" + (" WHERE a.use_yn" if only_active else "")).fetchall()
    accts = {r["acct_id"]: Account(**r) for r in rows}
    for r in conn.execute("SELECT acct_id, ctgr_cd FROM sec.account_category"):
        if r["acct_id"] in accts:
            accts[r["acct_id"]].categories.add(r["ctgr_cd"])
    for r in conn.execute("SELECT m.acct_id, m.role_cd, rc.ctgr_cd FROM sec.role_member m JOIN sec.role r ON r.role_cd=m.role_cd AND r.use_yn "
                          "LEFT JOIN sec.role_category rc ON rc.role_cd = m.role_cd"):
        a = accts.get(r["acct_id"])
        if a:
            a.roles.add(r["role_cd"])
            if r["ctgr_cd"]:
                a.categories.add(r["ctgr_cd"])
    return accts


def load_account(conn, login_id: str = None, acct_id: int = None) -> Account | None:
    for a in load_accounts(conn).values():
        if (login_id and a.login_id == login_id) or (acct_id and a.acct_id == acct_id):
            return a
    return None


def load_policies(conn) -> dict[tuple, dict]:
    rows = conn.execute(
        "SELECT p.schema_nm, p.table_nm, p.min_grade_cd, g.grade_rank AS min_rank, p.ctgr_cd "
        "FROM meta.object_policy p LEFT JOIN sec.grade g ON g.grade_cd = p.min_grade_cd WHERE p.use_yn").fetchall()
    return {(r["schema_nm"], r["table_nm"]): r for r in rows}


def effective_policy(policies: dict, schema: str, table: str) -> dict | None:
    return policies.get((schema, table)) or policies.get((schema, "*"))


def allowed(acct: Account, policy: dict | None) -> bool:
    if not acct.use_yn:
        return False
    if policy is None:
        return True
    if policy["min_rank"] is not None and acct.grade_rank < policy["min_rank"]:
        return False
    if policy["ctgr_cd"] and policy["ctgr_cd"] not in acct.categories:
        return False
    return True


def check_table(conn, acct: Account, schema: str, table: str, cfg=None) -> bool:
    """플랫폼이 관리하지 않는 스키마의 테이블은 항상 거부(다른 앱의 데이터)"""
    if cfg is not None and not is_managed(conn, cfg, schema):
        return False
    return allowed(acct, effective_policy(load_policies(conn), schema, table))


def authorize_action(conn, acct: Account, act_cd: str) -> tuple[bool, str]:
    """api.action_policy 기반 행위 권한 (LOGIN/LIST/MODIFY/GRANT/CALL/ACCOUNT)"""
    r = conn.execute("SELECT p.act_nm, p.admin_yn, g.grade_rank, g.grade_cd FROM api.action_policy p "
                     "JOIN sec.grade g ON g.grade_cd = p.min_grade_cd WHERE p.act_cd=%s AND p.use_yn", (act_cd,)).fetchone()
    if not acct or not acct.use_yn:
        return False, "비활성 계정"
    if r is None:
        return False, f"행위 정책 {act_cd} 없음"
    if acct.grade_rank < r["grade_rank"]:
        return False, f"{r['act_nm']}: {r['grade_cd']} 등급 이상 필요(현재 {acct.grade_cd})"
    if r["admin_yn"] and not acct.admin_yn:
        return False, f"{r['act_nm']}: 관리자 권한 필요"
    return True, "ok"


# ---------------- DB 롤 동기화 ----------------
def _role_exists(conn, name):
    return conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (name,)).fetchone() is not None


def _ensure_role(conn, name):
    if not _role_exists(conn, name):
        conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(name)))


def _is_member(conn, member, group):
    return conn.execute("SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid JOIN pg_roles u ON u.oid=m.member "
                        "WHERE r.rolname=%s AND u.rolname=%s", (group, member)).fetchone() is not None


def _set_member(conn, member, group, want: bool):
    has = _is_member(conn, member, group)
    if want and not has:
        conn.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(group), sql.Identifier(member)))
        return 1
    if not want and has:
        conn.execute(sql.SQL("REVOKE {} FROM {}").format(sql.Identifier(group), sql.Identifier(member)))
        return 1
    return 0


PLATFORM_SCHEMAS = ("meta", "sec", "api", "ingest", "pi")


def managed_schemas(conn, cfg) -> set[str] | None:
    """권한 동기화가 손대는 스키마 = 플랫폼 스키마 + 설정 access.managed_schemas
    + 플랫폼이 만든 스키마(meta.table_catalog 에 등록된 것) + 접근정책이 걸린 스키마.
    다른 앱의 스키마는 여기 없으면 GRANT/REVOKE 를 전혀 하지 않는다.
    설정이 "*" 이면 v2.0 동작(시스템 스키마 외 전부) — 전용 DB 일 때만 쓴다. None 반환 = 전부."""
    conf = (cfg.get("access") or {}).get("managed_schemas")
    if conf == "*" or conf == ["*"]:
        return None
    out = set(PLATFORM_SCHEMAS) | set(conf or [])
    for q in ("SELECT DISTINCT schema_name s FROM meta.table_catalog",
              "SELECT DISTINCT schema_nm s FROM meta.object_policy WHERE use_yn"):
        try:
            with conn.transaction():
                out |= {r["s"] for r in conn.execute(q)}
        except Exception:  # 설치 전 등 테이블이 없으면 무시
            pass
    return out


def is_managed(conn, cfg, schema: str) -> bool:
    m = managed_schemas(conn, cfg)
    return m is None or schema in m


def list_tables(conn, exclude: list[str], only: set[str] | None = None) -> list[tuple[str, str]]:
    rows = conn.execute("SELECT table_schema s, table_name t FROM information_schema.tables "
                        "WHERE table_schema <> ALL(%s) AND table_schema NOT LIKE 'pg\\_%%' ORDER BY 1,2", (exclude,)).fetchall()
    return [(r["s"], r["t"]) for r in rows if only is None or r["s"] in only]


def sync(conn, cfg, verbose: bool = False) -> dict:
    """정책 → PostgreSQL 롤/권한 동기화 (멱등). 테이블을 새로 만든 뒤·정책/계정 변경 뒤 실행"""
    exclude = cfg["access"]["exclude_schemas"]
    scope = managed_schemas(conn, cfg)
    me = conn.execute("SELECT current_user u, rolsuper s FROM pg_roles WHERE rolname=current_user").fetchone()
    _ensure_role(conn, OPEN_ROLE)
    policies = load_policies(conn)
    accts = load_accounts(conn)
    tables = list_tables(conn, exclude, scope)
    rep = {"tables": len(tables), "open": 0, "protected": 0, "accounts": len(accts), "membership_changes": 0,
           "managed_schemas": "*" if scope is None else sorted(scope)}
    open_schemas, prot_roles = set(), {}
    for s, t in tables:
        tid = sql.SQL("{}.{}").format(sql.Identifier(s), sql.Identifier(t))
        conn.execute(sql.SQL("REVOKE ALL ON {} FROM PUBLIC").format(tid))
        pol = effective_policy(policies, s, t)
        tr = table_role_name(s, t)
        if pol is None:
            conn.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(tid, sql.Identifier(OPEN_ROLE)))
            open_schemas.add(s); rep["open"] += 1
            if _role_exists(conn, tr):  # 보호 해제된 테이블의 롤 정리
                conn.execute(sql.SQL("REVOKE SELECT ON {} FROM {}").format(tid, sql.Identifier(tr)))
        else:
            conn.execute(sql.SQL("REVOKE SELECT ON {} FROM {}").format(tid, sql.Identifier(OPEN_ROLE)))
            _ensure_role(conn, tr)
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(s), sql.Identifier(tr)))
            conn.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(tid, sql.Identifier(tr)))
            prot_roles[tr] = pol; rep["protected"] += 1
    for s in {s for s, _ in tables}:
        q = sql.SQL("GRANT USAGE ON SCHEMA {} TO {}") if s in open_schemas else sql.SQL("REVOKE USAGE ON SCHEMA {} FROM {}")
        conn.execute(q.format(sql.Identifier(s), sql.Identifier(OPEN_ROLE)))
    conn.execute("REVOKE ALL ON SCHEMA pi FROM PUBLIC") if conn.execute("SELECT to_regnamespace('pi') IS NOT NULL AS ok").fetchone()["ok"] else None
    for a in accts.values():
        ur = a.db_role
        _ensure_role(conn, ur)
        if not me["s"]:
            _set_member(conn, me["u"], ur, True)  # 서비스 계정이 SET ROLE 할 수 있도록
        rep["membership_changes"] += _set_member(conn, ur, OPEN_ROLE, a.use_yn)
        for tr, pol in prot_roles.items():
            rep["membership_changes"] += _set_member(conn, ur, tr, allowed(a, pol))
    from .db import audit
    audit(conn, None, "ACCESS_SYNC", None, rep)
    conn.commit()
    return rep


def explain(conn, acct: Account, cfg) -> list[dict]:
    """계정이 볼 수 있는/없는 테이블 목록(점검용)"""
    pols = load_policies(conn)
    out = []
    for s, t in list_tables(conn, cfg["access"]["exclude_schemas"], managed_schemas(conn, cfg)):
        p = effective_policy(pols, s, t)
        out.append({"schema": s, "table": t, "allowed": allowed(acct, p),
                    "policy": None if p is None else f"{p['min_grade_cd'] or '-'}/{p['ctgr_cd'] or '-'}"})
    return out
