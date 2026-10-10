"""등록 SQL 검사 — SELECT 단일문만, 위험 함수 금지, 참조 테이블 추출, :파라미터 → psycopg 자리표시자 변환."""
from __future__ import annotations
import re
import pglast
from pglast import ast
from pglast.visitors import Visitor

DENY_FUNCS = {"pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file", "lo_import", "lo_export",
              "lo_get", "dblink", "dblink_exec", "pg_terminate_backend", "pg_cancel_backend", "set_config", "pg_reload_conf",
              "copy", "pg_advisory_lock", "query_to_xml", "pg_file_write", "current_setting"}
PARAM = re.compile(r"(?<![:\w]):([a-zA-Z_][a-zA-Z0-9_]*)")


class SqlRejected(ValueError):
    pass


class _V(Visitor):
    def __init__(self):
        self.tables, self.funcs, self.bad = set(), set(), []

    def visit_RangeVar(self, ancestors, node):
        self.tables.add((node.schemaname or "public", node.relname))

    def visit_FuncCall(self, ancestors, node):
        self.funcs.add(".".join(n.sval for n in node.funcname).lower())

    def visit_IntoClause(self, ancestors, node):
        self.bad.append("SELECT INTO 금지")

    def visit_LockingClause(self, ancestors, node):
        self.bad.append("FOR UPDATE/SHARE 금지")


def _for_parse(sql_text: str) -> str:
    # :name 을 파서가 이해하는 $n 으로 바꿔서 구문 검사
    names = []
    def rep(m):
        if m.group(1) not in names:
            names.append(m.group(1))
        return f"${names.index(m.group(1)) + 1}"
    return PARAM.sub(rep, sql_text)


def check(sql_text: str) -> dict:
    s = sql_text.strip().rstrip(";")
    try:
        stmts = pglast.parse_sql(_for_parse(s))
    except pglast.parser.ParseError as e:
        raise SqlRejected(f"SQL 구문 오류: {e}") from e
    if len(stmts) != 1:
        raise SqlRejected("SQL 은 한 문장만 등록할 수 있습니다")
    st = stmts[0].stmt
    if not isinstance(st, ast.SelectStmt):
        raise SqlRejected(f"SELECT 문만 허용 (현재 {type(st).__name__})")
    v = _V(); v(stmts[0])
    if v.bad:
        raise SqlRejected(", ".join(v.bad))
    # CTE 안의 DML(WITH x AS (DELETE …)) 차단
    for node in _walk(st):
        if isinstance(node, (ast.InsertStmt, ast.UpdateStmt, ast.DeleteStmt, ast.MergeStmt if hasattr(ast, "MergeStmt") else ast.DeleteStmt)):
            raise SqlRejected("쿼리 안에 INSERT/UPDATE/DELETE 가 있습니다")
    deny = {f for f in v.funcs if f.split(".")[-1] in DENY_FUNCS or f.startswith("pg_catalog.pg_")}
    if deny:
        raise SqlRejected(f"사용할 수 없는 함수: {sorted(deny)}")
    params = []
    for m in PARAM.finditer(s):
        if m.group(1) not in params:
            params.append(m.group(1))
    ctes = {c.ctename for c in (st.withClause.ctes if st.withClause else [])}
    tables = sorted(t for t in v.tables if not (t[0] == "public" and t[1] in ctes))
    return {"sql": s, "params": params, "tables": tables}


def _walk(node):
    if isinstance(node, ast.Node):
        yield node
        for name in node:
            yield from _walk(getattr(node, name))
    elif isinstance(node, (list, tuple)):
        for x in node:
            yield from _walk(x)


def to_psycopg(sql_text: str) -> str:
    """:name → %(name)s, 기존 % 는 %% 로 이스케이프"""
    s = sql_text.replace("%", "%%")
    return PARAM.sub(lambda m: f"%({m.group(1)})s", s)


TYPES = {"text": str, "string": str, "int": int, "integer": int, "number": float, "numeric": float, "bool": bool,
         "boolean": bool, "date": str, "timestamp": str}


def bind(spec: list[dict], given: dict) -> dict:
    out = {}
    for p in spec:
        n = p["name"]
        if n in given and given[n] not in (None, ""):
            v = given[n]
            ty = TYPES.get(p.get("type", "text"), str)
            try:
                out[n] = (str(v).lower() in ("1", "true", "y", "yes")) if ty is bool else ty(v)
            except (TypeError, ValueError):
                raise SqlRejected(f"파라미터 {n}: {p.get('type')} 형식이 아닙니다")
        elif p.get("required", True) and "default" not in p:
            raise SqlRejected(f"필수 파라미터 누락: {n}")
        else:
            out[n] = p.get("default")
    return out
