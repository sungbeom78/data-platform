"""데이터 조회 API (FastAPI).

인증: POST /auth/token (아이디·비밀번호 → JWT)  또는  헤더 X-API-Key: dpk_…  (팀·시스템 계정)
행위 권한(api.action_policy):  LOGIN·LIST(b 이상) / MODIFY·GRANT(a 이상 + 관리자) / CALL(+ API 사용권한)
실행: 읽기 전용 트랜잭션 + statement_timeout + SET ROLE <호출 계정 DB 롤> → 등급·분류 정책을 DB 가 최종 판정
"""
from __future__ import annotations
import hashlib, json, time
from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from psycopg import sql, errors as pgerr
from psycopg.types.json import Jsonb
from .. import access, accounts
from ..crypto import Crypto
from ..db import connect, audit
from .sqlguard import check, to_psycopg, bind, SqlRejected


class TokenReq(BaseModel):
    login_id: str
    password: str


class ApiReq(BaseModel):
    api_nm: str = Field(pattern=r"^[a-z][a-z0-9_]{1,62}$")
    sql: str
    api_desc: str | None = None
    params: list[dict] = []
    max_rows: int | None = None
    timeout_ms: int | None = None


class GrantReq(BaseModel):
    login_id: str | None = None
    role_cd: str | None = None


def create_app(cfg) -> FastAPI:
    app = FastAPI(title="data-platform 조회 API", version="2.0")
    cr = Crypto(cfg["crypto"])
    secret = cfg["api"]["jwt_secret"] or ""
    if len(secret) < 32:
        raise RuntimeError("api.jwt_secret 이 비어 있거나 짧습니다 — keygen --write 로 채우세요")

    def db():
        conn = connect(cfg)
        try:
            yield conn
        finally:
            conn.close()

    def current(request: Request, conn=Depends(db), authorization: str | None = Header(None), x_api_key: str | None = Header(None)):
        acct = None
        if x_api_key:
            acct = accounts.verify_key(conn, cr, x_api_key)
        elif authorization and authorization.lower().startswith("bearer "):
            try:
                claims = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
                acct = access.load_account(conn, acct_id=int(claims["sub"]))
            except jwt.PyJWTError:
                acct = None
        if not acct or not acct.use_yn:
            raise HTTPException(401, "인증 필요")
        ok, why = access.authorize_action(conn, acct, "LOGIN")  # 로그인 = 목록 조회 이상 등급
        if not ok:
            raise HTTPException(403, why)
        return acct

    def need(conn, acct, act):
        ok, why = access.authorize_action(conn, acct, act)
        if not ok:
            raise HTTPException(403, why)

    @app.exception_handler(SqlRejected)
    async def _rej(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.post("/auth/token")
    def token(req: TokenReq, conn=Depends(db)):
        acct = accounts.login(conn, cr, req.login_id, req.password)
        if not acct:
            raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다")
        ok, why = access.authorize_action(conn, acct, "LOGIN")
        if not ok:
            raise HTTPException(403, why)
        exp = datetime.now(timezone.utc) + timedelta(minutes=int(cfg["api"]["token_ttl_min"]))
        tok = jwt.encode({"sub": str(acct.acct_id), "login": acct.login_id, "exp": exp}, secret, algorithm="HS256")
        audit(conn, acct.acct_id, "LOGIN", acct.login_id, None); conn.commit()
        return {"access_token": tok, "token_type": "bearer", "expires_at": exp.isoformat(), "grade": acct.grade_cd, "admin": acct.admin_yn}

    @app.get("/me")
    def me(acct=Depends(current)):
        return {"login_id": acct.login_id, "name": acct.acct_nm, "type": acct.acct_type_cd, "grade": acct.grade_cd,
                "admin": acct.admin_yn, "categories": sorted(acct.categories), "roles": sorted(acct.roles)}

    @app.get("/apis")
    def list_apis(acct=Depends(current), conn=Depends(db)):
        need(conn, acct, "LIST")
        rows = conn.execute(
            "SELECT d.api_nm, d.api_desc, d.param_val AS params, d.max_row_cnt, d.timeout_ms, d.use_yn, "
            "EXISTS (SELECT 1 FROM api.api_grant g WHERE g.api_id=d.api_id AND (g.acct_id=%s OR g.role_cd = ANY(%s))) AS granted "
            "FROM api.api_definition d ORDER BY d.api_nm", (acct.acct_id, list(acct.roles))).fetchall()
        if access.authorize_action(conn, acct, "MODIFY")[0]:
            for r, s in zip(rows, conn.execute("SELECT sql_val FROM api.api_definition ORDER BY api_nm").fetchall()):
                r["sql"] = s["sql_val"]
        return rows

    def _validate_tables(conn, acct, tables):
        pols = access.load_policies(conn)
        scope = access.managed_schemas(conn, cfg)
        denied = [f"{s}.{t}" for s, t in tables
                  if (scope is not None and s not in scope) or not access.allowed(acct, access.effective_policy(pols, s, t))]
        if denied:
            raise HTTPException(403, f"등록 계정이 접근할 수 없는 테이블: {denied}")

    @app.post("/apis")
    def create_api(req: ApiReq, acct=Depends(current), conn=Depends(db)):
        need(conn, acct, "MODIFY")
        info = check(req.sql)
        declared = {p["name"] for p in req.params}
        undeclared = [p for p in info["params"] if p not in declared]
        params = req.params + [{"name": p, "type": "text", "required": True} for p in undeclared]
        _validate_tables(conn, acct, info["tables"])
        try:
            conn.execute("INSERT INTO api.api_definition (api_nm, api_desc, sql_val, param_val, max_row_cnt, timeout_ms, owner_acct_id) "
                         "VALUES (%s,%s,%s,%s,%s,%s,%s)", (req.api_nm, req.api_desc, info["sql"], Jsonb(params),
                                                         req.max_rows or cfg["api"]["default_max_rows"],
                                                         req.timeout_ms or cfg["api"]["default_timeout_ms"], acct.acct_id))
        except pgerr.UniqueViolation:
            raise HTTPException(409, f"이미 있는 API: {req.api_nm}")
        audit(conn, acct.acct_id, "API_CREATE", req.api_nm, {"tables": info["tables"]}); conn.commit()
        return {"api_nm": req.api_nm, "params": params, "tables": info["tables"]}

    @app.put("/apis/{api_nm}")
    def update_api(api_nm: str, req: ApiReq, acct=Depends(current), conn=Depends(db)):
        need(conn, acct, "MODIFY")
        info = check(req.sql)
        _validate_tables(conn, acct, info["tables"])
        params = req.params + [{"name": p, "type": "text", "required": True} for p in info["params"] if p not in {x["name"] for x in req.params}]
        n = conn.execute("UPDATE api.api_definition SET sql_val=%s, api_desc=%s, param_val=%s, max_row_cnt=coalesce(%s,max_row_cnt), "
                         "timeout_ms=coalesce(%s,timeout_ms), updated_at=now() WHERE api_nm=%s AND api_nm <> 'sys_table_read'",
                         (info["sql"], req.api_desc, Jsonb(params), req.max_rows, req.timeout_ms, api_nm)).rowcount
        if not n:
            raise HTTPException(404, "API 없음")
        audit(conn, acct.acct_id, "API_UPDATE", api_nm, {"tables": info["tables"]}); conn.commit()
        return {"api_nm": api_nm, "params": params}

    @app.delete("/apis/{api_nm}")
    def delete_api(api_nm: str, acct=Depends(current), conn=Depends(db)):
        need(conn, acct, "MODIFY")
        n = conn.execute("DELETE FROM api.api_definition WHERE api_nm=%s AND api_nm <> 'sys_table_read'", (api_nm,)).rowcount
        if not n:
            raise HTTPException(404, "API 없음")
        audit(conn, acct.acct_id, "API_DELETE", api_nm, None); conn.commit()
        return {"deleted": api_nm}

    def _api_id(conn, api_nm):
        r = conn.execute("SELECT api_id FROM api.api_definition WHERE api_nm=%s", (api_nm,)).fetchone()
        if not r:
            raise HTTPException(404, "API 없음")
        return r["api_id"]

    @app.post("/apis/{api_nm}/grants")
    def grant(api_nm: str, req: GrantReq, acct=Depends(current), conn=Depends(db)):
        need(conn, acct, "GRANT")
        if bool(req.login_id) == bool(req.role_cd):
            raise HTTPException(400, "login_id 또는 role_cd 중 하나만 지정")
        aid = _api_id(conn, api_nm)
        if req.login_id:
            t = access.load_account(conn, login_id=req.login_id)
            if not t:
                raise HTTPException(404, "계정 없음")
            conn.execute("INSERT INTO api.api_grant (api_id, acct_id, grant_acct_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", (aid, t.acct_id, acct.acct_id))
        else:
            conn.execute("INSERT INTO api.api_grant (api_id, role_cd, grant_acct_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", (aid, req.role_cd, acct.acct_id))
        audit(conn, acct.acct_id, "API_GRANT", api_nm, req.model_dump()); conn.commit()
        return {"granted": api_nm, **req.model_dump()}

    @app.delete("/apis/{api_nm}/grants")
    def revoke(api_nm: str, req: GrantReq, acct=Depends(current), conn=Depends(db)):
        need(conn, acct, "GRANT")
        aid = _api_id(conn, api_nm)
        if req.login_id:
            t = access.load_account(conn, login_id=req.login_id)
            conn.execute("DELETE FROM api.api_grant WHERE api_id=%s AND acct_id=%s", (aid, t.acct_id if t else -1))
        else:
            conn.execute("DELETE FROM api.api_grant WHERE api_id=%s AND role_cd=%s", (aid, req.role_cd))
        audit(conn, acct.acct_id, "API_REVOKE", api_nm, req.model_dump()); conn.commit()
        return {"revoked": api_nm, **req.model_dump()}

    @app.get("/apis/{api_nm}/grants")
    def grants(api_nm: str, acct=Depends(current), conn=Depends(db)):
        need(conn, acct, "GRANT")
        return conn.execute("SELECT a.login_id, g.role_cd, g.created_at FROM api.api_grant g LEFT JOIN sec.account a ON a.acct_id=g.acct_id "
                            "WHERE g.api_id=%s", (_api_id(conn, api_nm),)).fetchall()

    def _granted(conn, acct, api_nm) -> dict:
        d = conn.execute("SELECT * FROM api.api_definition WHERE api_nm=%s AND use_yn", (api_nm,)).fetchone()
        if not d:
            raise HTTPException(404, "API 없음")
        need(conn, acct, "CALL")
        g = conn.execute("SELECT 1 FROM api.api_grant WHERE api_id=%s AND (acct_id=%s OR role_cd = ANY(%s))",
                         (d["api_id"], acct.acct_id, list(acct.roles))).fetchone()
        if not g:
            raise HTTPException(403, f"API '{api_nm}' 사용권한이 없습니다 — 관리자에게 부여 요청")
        return d

    def _execute(conn, acct, d, query, params, limit):
        conn.commit()  # 앞선 조회 트랜잭션 종료 → 새 READ ONLY 트랜잭션
        t0 = time.time()
        ph = cr.hmac(json.dumps(params, sort_keys=True, default=str), normalize=False)
        try:
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                conn.execute(sql.SQL("SET LOCAL statement_timeout = {}").format(sql.Literal(int(d["timeout_ms"]))))
                conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(acct.db_role)))
                cur = conn.execute(query, params)
                rows = cur.fetchmany(limit + 1)
                cols = [c.name for c in cur.description] if cur.description else []
            trunc = len(rows) > limit
            rows = rows[:limit]
            conn.execute("INSERT INTO api.call_log (api_id, acct_id, param_hash, row_cnt, elapsed_ms, result_cd) VALUES (%s,%s,%s,%s,%s,'OK')",
                         (d["api_id"], acct.acct_id, ph, len(rows), int((time.time() - t0) * 1000)))
            conn.commit()
            return {"api": d["api_nm"], "columns": cols, "rows": rows, "row_count": len(rows), "truncated": trunc,
                    "elapsed_ms": int((time.time() - t0) * 1000)}
        except (pgerr.InsufficientPrivilege, pgerr.QueryCanceled, pgerr.Error) as e:
            code = 403 if isinstance(e, pgerr.InsufficientPrivilege) else 504 if isinstance(e, pgerr.QueryCanceled) else 400
            conn.rollback()
            conn.execute("INSERT INTO api.call_log (api_id, acct_id, param_hash, elapsed_ms, result_cd, msg_val) VALUES (%s,%s,%s,%s,%s,%s)",
                         (d["api_id"], acct.acct_id, ph, int((time.time() - t0) * 1000), type(e).__name__[:30], str(e)[:500]))
            conn.commit()
            msg = "데이터 접근 권한이 없습니다(등급/분류 정책)" if code == 403 else "실행 시간 초과" if code == 504 else str(e).split("\n")[0]
            raise HTTPException(code, msg)

    @app.api_route("/q/{api_nm}", methods=["GET", "POST"])
    async def call(api_nm: str, request: Request, acct=Depends(current), conn=Depends(db)):
        d = _granted(conn, acct, api_nm)
        if api_nm == "sys_table_read":
            raise HTTPException(400, "내장 API 는 /data/{schema}/{table} 로 호출")
        given = dict(request.query_params)
        if request.method == "POST":
            try:
                given.update(await request.json())
            except Exception:
                pass
        limit = min(int(given.pop("_limit", d["max_row_cnt"])), d["max_row_cnt"])
        params = bind(d["param_val"], given)
        return _execute(conn, acct, d, to_psycopg(d["sql_val"]), params, limit)

    @app.get("/data/{schema}/{table}")
    def table_read(schema: str, table: str, request: Request, limit: int = 100, acct=Depends(current), conn=Depends(db)):
        d = _granted(conn, acct, "sys_table_read")
        if not access.check_table(conn, acct, schema, table, cfg):
            raise HTTPException(403, "데이터 접근 권한이 없습니다(등급/분류 정책)")
        filters = {k: v for k, v in request.query_params.items() if k != "limit"}
        cols = {r["column_name"] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s", (schema, table))}
        if not cols:
            raise HTTPException(404, "테이블 없음")
        bad = [k for k in filters if k not in cols]
        if bad:
            raise HTTPException(400, f"없는 컬럼: {bad}")
        q = sql.SQL("SELECT * FROM {}.{}").format(sql.Identifier(schema), sql.Identifier(table))
        if filters:
            q += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(sql.SQL("{}::text = {}").format(sql.Identifier(k), sql.Placeholder(k)) for k in filters)
        return _execute(conn, acct, d, q, filters, min(limit, d["max_row_cnt"]))

    return app
