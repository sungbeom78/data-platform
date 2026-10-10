"""계정·팀·역할·분류·API 키·접근정책 관리 (CLI·API 공용). 모든 변경은 sec.audit_log 에 기록."""
from __future__ import annotations
import secrets
from datetime import datetime, timedelta, timezone
from .crypto import Crypto
from .db import audit
from . import access


def create_account(conn, crypto: Crypto, login_id, acct_nm, grade_cd, acct_type_cd="USER", admin=False,
                   password=None, categories=(), by=None) -> int:
    pw = crypto.hash_password(password) if password else None
    r = conn.execute("INSERT INTO sec.account (login_id, acct_nm, acct_type_cd, grade_cd, admin_yn, pwd_hash) "
                     "VALUES (%s,%s,%s,%s,%s,%s) RETURNING acct_id", (login_id, acct_nm, acct_type_cd, grade_cd, admin, pw)).fetchone()
    for c in categories:
        conn.execute("INSERT INTO sec.account_category (acct_id, ctgr_cd) VALUES (%s,%s) ON CONFLICT DO NOTHING", (r["acct_id"], c))
    audit(conn, by, "ACCOUNT_CREATE", login_id, {"grade": grade_cd, "type": acct_type_cd, "admin": admin, "categories": list(categories)})
    return r["acct_id"]


def _acct_id(conn, login_id):
    r = conn.execute("SELECT acct_id FROM sec.account WHERE login_id=%s", (login_id,)).fetchone()
    if not r:
        raise ValueError(f"계정 없음: {login_id}")
    return r["acct_id"]


def update_account(conn, crypto: Crypto, login_id, grade_cd=None, admin=None, use=None, password=None, by=None):
    aid = _acct_id(conn, login_id)
    sets, vals = [], []
    for col, v in (("grade_cd", grade_cd), ("admin_yn", admin), ("use_yn", use)):
        if v is not None:
            sets.append(f"{col}=%s"); vals.append(v)
    if password:
        sets.append("pwd_hash=%s"); vals.append(crypto.hash_password(password))
    if sets:
        conn.execute(f"UPDATE sec.account SET {', '.join(sets)}, updated_at=now() WHERE acct_id=%s", (*vals, aid))
    audit(conn, by, "ACCOUNT_UPDATE", login_id, {"grade": grade_cd, "admin": admin, "use": use, "password": bool(password)})


def set_categories(conn, login_id, add=(), remove=(), by=None):
    aid = _acct_id(conn, login_id)
    for c in add:
        conn.execute("INSERT INTO sec.account_category (acct_id, ctgr_cd) VALUES (%s,%s) ON CONFLICT DO NOTHING", (aid, c))
    for c in remove:
        conn.execute("DELETE FROM sec.account_category WHERE acct_id=%s AND ctgr_cd=%s", (aid, c))
    audit(conn, by, "ACCOUNT_CATEGORY", login_id, {"add": list(add), "remove": list(remove)})


def create_role(conn, role_cd, role_nm, categories=(), desc=None, by=None):
    conn.execute("INSERT INTO sec.role (role_cd, role_nm, role_desc) VALUES (%s,%s,%s) ON CONFLICT (role_cd) DO UPDATE "
                 "SET role_nm=EXCLUDED.role_nm, role_desc=EXCLUDED.role_desc, updated_at=now()", (role_cd, role_nm, desc))
    for c in categories:
        conn.execute("INSERT INTO sec.role_category (role_cd, ctgr_cd) VALUES (%s,%s) ON CONFLICT DO NOTHING", (role_cd, c))
    audit(conn, by, "ROLE_UPSERT", role_cd, {"categories": list(categories)})


def role_members(conn, role_cd, add=(), remove=(), by=None):
    for l in add:
        conn.execute("INSERT INTO sec.role_member (role_cd, acct_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (role_cd, _acct_id(conn, l)))
    for l in remove:
        conn.execute("DELETE FROM sec.role_member WHERE role_cd=%s AND acct_id=%s", (role_cd, _acct_id(conn, l)))
    audit(conn, by, "ROLE_MEMBER", role_cd, {"add": list(add), "remove": list(remove)})


def add_grade(conn, grade_cd, grade_nm, rank, by=None):
    conn.execute("INSERT INTO sec.grade (grade_cd, grade_nm, grade_rank) VALUES (%s,%s,%s) ON CONFLICT (grade_cd) DO UPDATE "
                 "SET grade_nm=EXCLUDED.grade_nm, grade_rank=EXCLUDED.grade_rank, updated_at=now()", (grade_cd, grade_nm, rank))
    audit(conn, by, "GRADE_UPSERT", grade_cd, {"rank": rank})


def add_category(conn, ctgr_cd, ctgr_nm, sort_no=99, by=None):
    conn.execute("INSERT INTO sec.category (ctgr_cd, ctgr_nm, sort_no) VALUES (%s,%s,%s) ON CONFLICT (ctgr_cd) DO UPDATE "
                 "SET ctgr_nm=EXCLUDED.ctgr_nm, updated_at=now()", (ctgr_cd, ctgr_nm, sort_no))
    audit(conn, by, "CATEGORY_UPSERT", ctgr_cd, None)


def set_policy(conn, schema, table="*", min_grade=None, category=None, by=None):
    conn.execute("INSERT INTO meta.object_policy (schema_nm, table_nm, min_grade_cd, ctgr_cd) VALUES (%s,%s,%s,%s) "
                 "ON CONFLICT (schema_nm, table_nm) DO UPDATE SET min_grade_cd=EXCLUDED.min_grade_cd, ctgr_cd=EXCLUDED.ctgr_cd, "
                 "use_yn=true, updated_at=now()", (schema, table or "*", min_grade, category))
    audit(conn, by, "POLICY_SET", f"{schema}.{table or '*'}", {"min_grade": min_grade, "category": category})


def remove_policy(conn, schema, table="*", by=None):
    conn.execute("DELETE FROM meta.object_policy WHERE schema_nm=%s AND table_nm=%s", (schema, table or "*"))
    audit(conn, by, "POLICY_REMOVE", f"{schema}.{table or '*'}", None)


# ---- API 키 (팀·시스템 계정) ----
def issue_key(conn, crypto: Crypto, login_id, days=365, by=None) -> str:
    """키 원문은 이 때 한 번만 반환. DB 에는 접두와 HMAC 해시만 저장"""
    aid = _acct_id(conn, login_id)
    prefix = "dpk_" + secrets.token_hex(3)
    key = prefix + "_" + secrets.token_urlsafe(24)
    exp = datetime.now(timezone.utc) + timedelta(days=days) if days else None
    conn.execute("INSERT INTO sec.account_key (acct_id, key_prefix, key_hash, expire_at) VALUES (%s,%s,%s,%s)",
                 (aid, prefix, crypto.hmac(key, normalize=False), exp))
    audit(conn, by, "KEY_ISSUE", login_id, {"prefix": prefix, "days": days})
    return key


def verify_key(conn, crypto: Crypto, key: str) -> access.Account | None:
    if not key or not key.startswith("dpk_") or key.count("_") < 2:
        return None
    prefix = "_".join(key.split("_")[:2])
    r = conn.execute("SELECT k.acct_id, k.key_hash FROM sec.account_key k WHERE k.key_prefix=%s AND k.use_yn "
                     "AND (k.expire_at IS NULL OR k.expire_at > now())", (prefix,)).fetchone()
    if not r:
        return None
    import hmac as _h
    if not _h.compare_digest(bytes(r["key_hash"]), crypto.hmac(key, normalize=False)):
        return None
    return access.load_account(conn, acct_id=r["acct_id"])


def revoke_key(conn, prefix, by=None):
    conn.execute("UPDATE sec.account_key SET use_yn=false, updated_at=now() WHERE key_prefix=%s", (prefix,))
    audit(conn, by, "KEY_REVOKE", prefix, None)


def login(conn, crypto: Crypto, login_id, password) -> access.Account | None:
    r = conn.execute("SELECT acct_id, pwd_hash FROM sec.account WHERE login_id=%s AND use_yn", (login_id,)).fetchone()
    if not r or not crypto.verify_password(r["pwd_hash"], password):
        return None
    return access.load_account(conn, acct_id=r["acct_id"])
