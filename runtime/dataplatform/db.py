"""DB 연결 도우미 (psycopg 3)."""
from __future__ import annotations
import psycopg
from psycopg import sql
from psycopg.rows import dict_row


def connect(cfg, autocommit: bool = False, dict_rows: bool = True) -> psycopg.Connection:
    return psycopg.connect(cfg["database"]["dsn"], autocommit=autocommit,
                           row_factory=dict_row if dict_rows else psycopg.rows.tuple_row)


def ident(*parts: str) -> sql.Composable:
    return sql.SQL(".").join(sql.Identifier(p) for p in parts)


def exists(conn, regclass: str) -> bool:
    return conn.execute("SELECT to_regclass(%s) IS NOT NULL AS ok", (regclass,)).fetchone()["ok"]


def audit(conn, acct_id, act_cd: str, target: str | None = None, detail: dict | None = None):
    from psycopg.types.json import Jsonb
    conn.execute("INSERT INTO sec.audit_log (acct_id, act_cd, target_val, dtl_val) VALUES (%s,%s,%s,%s)",
                 (acct_id, act_cd, target, Jsonb(detail) if detail is not None else None))
