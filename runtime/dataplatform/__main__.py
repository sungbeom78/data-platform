"""data-platform CLI —  python -m dataplatform <명령> [--config config/system.yaml]

설치·키      keygen [--write]  |  init --admin-password …  |  rotate-keys
용어         glossary info | glossary check <물리명…> | glossary split <한글명…> | glossary add --kor --abbr --full
권한         account add|update|list|explain  |  category add  |  grade add  |  role add|members
             policy set|remove|list  |  key issue|revoke  |  sync
적재         ingest plan <파일|URL> [--schema pub] [--out plan.json]  |  ingest apply plan.json --by <id> --approval-quote "<사용자 답>" [--physical-quote "<답>"]  |  ingest jobs
             public-api <URL> --out data.json [--param k=v]  |  lake-query "<SQL>"
API          api create|list|grant|revoke (관리자 CLI)  |  serve
"""
from __future__ import annotations
import argparse, getpass, json, os, sys


def _cfg(a):
    from .config import load
    return load(a.config)


def _conn(cfg, autocommit=False):
    from .db import connect
    return connect(cfg, autocommit=autocommit)


def _print(x):
    print(json.dumps(x, ensure_ascii=False, indent=2, default=str))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dataplatform", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    sp = ap.add_subparsers(dest="cmd", required=True)

    k = sp.add_parser("keygen", help="128비트 키 생성(설정 파일의 빈 키만 채움)"); k.add_argument("--write", action="store_true")
    i = sp.add_parser("init", help="공통 스키마 설치 + 관리자 + 동기화")
    i.add_argument("--admin-login", default="admin"); i.add_argument("--admin-password"); i.add_argument("--admin-name", default="플랫폼 관리자")
    sp.add_parser("rotate-keys", help="active_key 로 AES 값 재암호화")
    sp.add_parser("sync", help="정책 → DB 롤/권한 동기화")

    g = sp.add_parser("glossary"); gs = g.add_subparsers(dest="sub", required=True)
    gs.add_parser("info")
    gc = gs.add_parser("check"); gc.add_argument("names", nargs="+")
    gk = gs.add_parser("split"); gk.add_argument("labels", nargs="+")
    ga = gs.add_parser("add"); ga.add_argument("--kor", required=True); ga.add_argument("--abbr", required=True)
    ga.add_argument("--full", required=True); ga.add_argument("--desc", default=""); ga.add_argument("--class-word", action="store_true")

    ac = sp.add_parser("account"); acs = ac.add_subparsers(dest="sub", required=True)
    a1 = acs.add_parser("add"); a1.add_argument("login_id"); a1.add_argument("--name", required=True); a1.add_argument("--grade", required=True)
    a1.add_argument("--type", default="USER", choices=["USER", "TEAM", "SYSTEM"]); a1.add_argument("--admin", action="store_true")
    a1.add_argument("--password"); a1.add_argument("--category", action="append", default=[])
    a2 = acs.add_parser("update"); a2.add_argument("login_id"); a2.add_argument("--grade"); a2.add_argument("--admin", choices=["y", "n"])
    a2.add_argument("--use", choices=["y", "n"]); a2.add_argument("--password"); a2.add_argument("--add-category", action="append", default=[])
    a2.add_argument("--remove-category", action="append", default=[])
    acs.add_parser("list")
    a4 = acs.add_parser("explain"); a4.add_argument("login_id")

    ct = sp.add_parser("category"); cts = ct.add_subparsers(dest="sub", required=True)
    c1 = cts.add_parser("add"); c1.add_argument("code"); c1.add_argument("--name", required=True)
    gr = sp.add_parser("grade"); grs = gr.add_subparsers(dest="sub", required=True)
    g1 = grs.add_parser("add"); g1.add_argument("code"); g1.add_argument("--name", required=True); g1.add_argument("--rank", type=int, required=True)

    ro = sp.add_parser("role"); ros = ro.add_subparsers(dest="sub", required=True)
    r1 = ros.add_parser("add"); r1.add_argument("role_cd"); r1.add_argument("--name", required=True); r1.add_argument("--category", action="append", default=[])
    r1.add_argument("--desc")
    r2 = ros.add_parser("members"); r2.add_argument("role_cd"); r2.add_argument("--add", action="append", default=[]); r2.add_argument("--remove", action="append", default=[])

    po = sp.add_parser("policy"); pos = po.add_subparsers(dest="sub", required=True)
    p1 = pos.add_parser("set"); p1.add_argument("schema"); p1.add_argument("--table", default="*"); p1.add_argument("--min-grade"); p1.add_argument("--category")
    p2 = pos.add_parser("remove"); p2.add_argument("schema"); p2.add_argument("--table", default="*")
    pos.add_parser("list")

    ke = sp.add_parser("key"); kes = ke.add_subparsers(dest="sub", required=True)
    k1 = kes.add_parser("issue"); k1.add_argument("login_id"); k1.add_argument("--days", type=int, default=365)
    k2 = kes.add_parser("revoke"); k2.add_argument("prefix")

    ig = sp.add_parser("ingest"); igs = ig.add_subparsers(dest="sub", required=True)
    n1 = igs.add_parser("plan"); n1.add_argument("src"); n1.add_argument("--sheet"); n1.add_argument("--schema", default="pub")
    n1.add_argument("--name"); n1.add_argument("--provider"); n1.add_argument("--license"); n1.add_argument("--type", choices=["FILE", "URL", "API", "PUBLIC"])
    n1.add_argument("--out", default="ingest_plan.json")
    n2 = igs.add_parser("apply"); n2.add_argument("plan"); n2.add_argument("--by", required=True, help="실행 계정 login_id (INGEST 권한)")
    n2.add_argument("--approval-quote", required=True, help="적재 승인 — 사용자 답을 그대로 인용")
    n2.add_argument("--physical-quote", help="새 테이블 생성 승인 — 사용자 답을 그대로 인용 (신규 테이블일 때 필수)")
    igs.add_parser("jobs")
    pa = sp.add_parser("public-api"); pa.add_argument("url"); pa.add_argument("--out", default="public_api.json")
    pa.add_argument("--param", action="append", default=[]); pa.add_argument("--max-pages", type=int, default=1000)
    lq = sp.add_parser("lake-query"); lq.add_argument("sql"); lq.add_argument("--limit", type=int, default=100); lq.add_argument("--as", dest="as_login")

    api = sp.add_parser("api"); aps = api.add_subparsers(dest="sub", required=True)
    x1 = aps.add_parser("create"); x1.add_argument("api_nm"); x1.add_argument("--sql", required=True); x1.add_argument("--desc")
    x1.add_argument("--params", default="[]", help='JSON 예: [{"name":"ym","type":"text"}]'); x1.add_argument("--max-rows", type=int)
    x1.add_argument("--timeout-ms", type=int); x1.add_argument("--by", default="admin")
    aps.add_parser("list")
    x3 = aps.add_parser("grant"); x3.add_argument("api_nm"); x3.add_argument("--login"); x3.add_argument("--role"); x3.add_argument("--by", default="admin")
    x4 = aps.add_parser("revoke"); x4.add_argument("api_nm"); x4.add_argument("--login"); x4.add_argument("--role"); x4.add_argument("--by", default="admin")
    sp.add_parser("serve")

    from .compat import utf8_stdio
    utf8_stdio()
    a = ap.parse_args(argv)
    cfg = _cfg(a)

    if a.cmd == "keygen":
        from .setup import keygen
        path = a.config or cfg.path or os.path.join(os.getcwd(), "config", "system.yaml")
        made = keygen(path, write=a.write)
        _print({"config": path if a.write else None, "generated": list(made) if a.write else made,
                "note": "기존 키는 덮어쓰지 않습니다" if a.write else "--write 로 설정 파일에 저장"})
        return

    from .crypto import Crypto
    from . import access, accounts
    cr = Crypto(cfg["crypto"])
    conn = _conn(cfg, autocommit=a.cmd in ("init",))

    def actor(login):
        x = access.load_account(conn, login_id=login) if login else None
        return x.acct_id if x else None

    if a.cmd == "init":
        from .setup import init
        pw = a.admin_password or (getpass.getpass("관리자 비밀번호: ") if sys.stdin.isatty() else None)
        conn.autocommit = False
        _print(init(conn, cfg, a.admin_login, pw, a.admin_name))
    elif a.cmd == "rotate-keys":
        from .setup import rotate_keys
        _print(rotate_keys(conn, cfg))
    elif a.cmd == "sync":
        _print(access.sync(conn, cfg))
    elif a.cmd == "glossary":
        from .glossary import open_glossary, Word
        gl = open_glossary(cfg, conn)
        if a.sub == "info":
            _print(gl.info())
        elif a.sub == "check":
            _print({n: (gl.check_identifier(n) or "OK") for n in a.names})
        elif a.sub == "split":
            out = {}
            for l in a.labels:
                ws, rest = gl.compose_kor(l)
                out[l] = {"tokens": [f"{w.kor}:{w.abbr}/{w.full}" for w in ws], "missing": rest}
            _print(out)
        elif a.sub == "add":
            _print(gl.register([Word(a.kor, a.abbr, a.full, a.class_word, a.desc)]))
    elif a.cmd == "account":
        if a.sub == "add":
            aid = accounts.create_account(conn, cr, a.login_id, a.name, a.grade, a.type, a.admin, a.password, a.category)
            conn.commit(); _print({"acct_id": aid, "sync": access.sync(conn, cfg)})
        elif a.sub == "update":
            yn = lambda v: None if v is None else v == "y"
            accounts.update_account(conn, cr, a.login_id, a.grade, yn(a.admin), yn(a.use), a.password)
            if a.add_category or a.remove_category:
                accounts.set_categories(conn, a.login_id, a.add_category, a.remove_category)
            conn.commit(); _print({"updated": a.login_id, "sync": access.sync(conn, cfg)})
        elif a.sub == "list":
            _print([{"login_id": x.login_id, "name": x.acct_nm, "type": x.acct_type_cd, "grade": x.grade_cd, "admin": x.admin_yn,
                     "use": x.use_yn, "categories": sorted(x.categories), "roles": sorted(x.roles), "db_role": x.db_role}
                    for x in access.load_accounts(conn).values()])
        elif a.sub == "explain":
            x = access.load_account(conn, login_id=a.login_id)
            _print(access.explain(conn, x, cfg))
    elif a.cmd == "category":
        accounts.add_category(conn, a.code, a.name); conn.commit(); _print({"category": a.code})
    elif a.cmd == "grade":
        accounts.add_grade(conn, a.code, a.name, a.rank); conn.commit(); _print({"grade": a.code, "rank": a.rank})
    elif a.cmd == "role":
        if a.sub == "add":
            accounts.create_role(conn, a.role_cd, a.name, a.category, a.desc)
        else:
            accounts.role_members(conn, a.role_cd, a.add, a.remove)
        conn.commit(); _print({"role": a.role_cd, "sync": access.sync(conn, cfg)})
    elif a.cmd == "policy":
        if a.sub == "set":
            accounts.set_policy(conn, a.schema, a.table, a.min_grade, a.category); conn.commit(); _print(access.sync(conn, cfg))
        elif a.sub == "remove":
            accounts.remove_policy(conn, a.schema, a.table); conn.commit(); _print(access.sync(conn, cfg))
        else:
            _print(conn.execute("SELECT schema_nm, table_nm, min_grade_cd, ctgr_cd, use_yn FROM meta.object_policy ORDER BY 1,2").fetchall())
    elif a.cmd == "key":
        if a.sub == "issue":
            key = accounts.issue_key(conn, cr, a.login_id, a.days); conn.commit()
            _print({"api_key": key, "note": "키 원문은 지금 한 번만 표시됩니다. 안전한 곳에 보관하세요."})
        else:
            accounts.revoke_key(conn, a.prefix); conn.commit(); _print({"revoked": a.prefix})
    elif a.cmd == "ingest":
        from .glossary import open_glossary
        if a.sub == "plan":
            from .ingest.plan import make_plan
            gl = open_glossary(cfg, conn)
            plan = make_plan(cfg, gl, conn, a.src, a.sheet, a.schema, a.type, a.name, a.provider, a.license)
            json.dump(plan, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            _print({"plan": a.out, "store": plan["store"], "store_reasons": plan["store_reasons"], "target": plan["target"],
                    "rows_estimated": plan["rows_estimated"], "pi_columns": [c["src"] for c in plan["columns"] if c.get("pi")],
                    "unnamed_columns": [c["src"] for c in plan["columns"] if not c["name"]],
                    "words_to_register": [w["kor"] for w in plan["words_to_register"]]})
        elif a.sub == "apply":
            from .ingest.load import apply
            gl = open_glossary(cfg, conn)
            plan = json.load(open(a.plan, encoding="utf-8"))
            from .ingest.load import PlanError
            try:
                _print(apply(conn, cfg, gl, plan, approval={"by": a.by, "quote": a.approval_quote, "physical_quote": a.physical_quote}))
            except PlanError as e:
                print(f"[적재 중단] {e}", file=sys.stderr)
                sys.exit(1)
        else:
            _print(conn.execute("SELECT j.job_id, s.src_nm, j.target_schema_nm||'.'||j.target_table_nm target, j.store_type_cd, j.status_cd, "
                                "j.row_cnt, j.aprv_val->>'by' approved_by, j.aprv_val->>'quote' approval_quote, j.start_at, j.end_at FROM ingest.job j JOIN ingest.source s USING (src_id) ORDER BY j.job_id DESC LIMIT 30").fetchall())
    elif a.cmd == "public-api":
        from .ingest.source import datago_api
        params = dict(p.split("=", 1) for p in a.param)
        _print({"saved": datago_api(a.url, cfg["public_data"]["service_key"], params, a.out, a.max_pages)})
    elif a.cmd == "lake-query":
        from .ingest.lake import query
        if a.as_login:
            x = access.load_account(conn, login_id=a.as_login)
            pols = access.load_policies(conn)
            names = [r["dataset_nm"] for r in conn.execute("SELECT dataset_nm FROM ingest.lake_dataset")]
            denied = [n for n in names if n in a.sql and not access.allowed(x, access.effective_policy(pols, "lake", n))]
            if denied:
                sys.exit(f"접근 불가 데이터셋(lake 정책): {denied}")
        print(query(conn, cfg, a.sql, a.limit).to_string())
    elif a.cmd == "api":
        from .api.sqlguard import check
        from psycopg.types.json import Jsonb
        by = access.load_account(conn, login_id=getattr(a, "by", "admin"))
        if a.sub != "list":
            need = "MODIFY" if a.sub == "create" else "GRANT"
            ok, why = access.authorize_action(conn, by, need)
            if not ok:
                sys.exit(why)
        if a.sub == "create":
            info = check(a.sql)
            pols = access.load_policies(conn)
            scope = access.managed_schemas(conn, cfg)
            denied = [f"{s_}.{t_}" for s_, t_ in info["tables"]
                      if (scope is not None and s_ not in scope) or not access.allowed(by, access.effective_policy(pols, s_, t_))]
            if denied:
                sys.exit(f"등록 계정({by.login_id})이 접근할 수 없는 테이블: {denied}")
            params = json.loads(a.params)
            params += [{"name": p, "type": "text", "required": True} for p in info["params"] if p not in {x["name"] for x in params}]
            conn.execute("INSERT INTO api.api_definition (api_nm, api_desc, sql_val, param_val, max_row_cnt, timeout_ms, owner_acct_id) "
                         "VALUES (%s,%s,%s,%s,%s,%s,%s)", (a.api_nm, a.desc, info["sql"], Jsonb(params),
                                                         a.max_rows or cfg["api"]["default_max_rows"], a.timeout_ms or cfg["api"]["default_timeout_ms"], by.acct_id))
            from .db import audit
            audit(conn, by.acct_id, "API_CREATE", a.api_nm, {"tables": info["tables"]}); conn.commit()
            _print({"api_nm": a.api_nm, "params": params, "tables": info["tables"]})
        elif a.sub == "list":
            _print(conn.execute("SELECT d.api_nm, d.api_desc, d.param_val, (SELECT array_agg(coalesce(ac.login_id, 'role:'||g.role_cd)) "
                                "FROM api.api_grant g LEFT JOIN sec.account ac ON ac.acct_id=g.acct_id WHERE g.api_id=d.api_id) grants "
                                "FROM api.api_definition d ORDER BY 1").fetchall())
        else:
            aid = conn.execute("SELECT api_id FROM api.api_definition WHERE api_nm=%s", (a.api_nm,)).fetchone()["api_id"]
            tgt = access.load_account(conn, login_id=a.login).acct_id if a.login else None
            if a.sub == "grant":
                col = "acct_id" if tgt else "role_cd"
                conn.execute(f"INSERT INTO api.api_grant (api_id, {col}, grant_acct_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                             (aid, tgt or a.role, by.acct_id))
            else:
                conn.execute("DELETE FROM api.api_grant WHERE api_id=%s AND (acct_id=%s OR role_cd=%s)", (aid, tgt, a.role))
            from .db import audit
            audit(conn, by.acct_id, "API_" + a.sub.upper(), a.api_nm, {"login": a.login, "role": a.role}); conn.commit()
            _print({a.sub: a.api_nm, "login": a.login, "role": a.role})
    elif a.cmd == "serve":
        import uvicorn
        from .api.app import create_app
        uvicorn.run(create_app(cfg), host=cfg["api"]["host"], port=int(cfg["api"]["port"]))
    conn.close()


if __name__ == "__main__":
    main()
