"""승인된 적재 계획 실행: (신규면) model.json → data-modeling exporter → DDL 실행 → 접근 동기화 → 적재.
개인정보 컬럼은 pi 스키마의 pi_<테이블> 에 암호화(aes)·검색해시(hmac)로만 저장된다."""
from __future__ import annotations
import datetime as dt, json, os, re, subprocess, sys
from decimal import Decimal, InvalidOperation
from psycopg import sql
from ..crypto import Crypto
from ..glossary import Word
from .. import access
from .source import read, iter_csv
from ..setup import DM_SCRIPTS


class PlanError(Exception):
    pass


def validate_plan(plan: dict, gl) -> list[str]:
    errs = []
    if not plan.get("approved"):
        errs.append("approved=false — 사용자 승인 후 apply 하세요")
    t = plan["target"]
    if not t.get("table"):
        errs.append("target.table 이 비어 있음")
    elif gl.check_identifier(t["table"]):
        errs.append(f"테이블명 {t['table']}: 사전에 없는 토큰 {gl.check_identifier(t['table'])}")
    if t.get("table") and t["table"].startswith("pi_"):
        errs.append("테이블명은 pi_ 로 시작할 수 없음(개인정보 테이블은 자동 생성)")
    names = set()
    for c in plan["columns"]:
        if c.get("skip"):
            continue
        if not c.get("name"):
            errs.append(f"컬럼 '{c['src']}': name 미지정 (missing={c.get('missing')})")
            continue
        miss = gl.check_identifier(c["name"])
        if miss:
            errs.append(f"컬럼 {c['name']}: 사전에 없는 토큰 {miss}")
        if c["name"] in names:
            errs.append(f"컬럼명 중복: {c['name']}")
        names.add(c["name"])
        if c.get("pi") and c["pi"].get("crypto") not in (None, "", "aes", "hmac", "aes+hmac"):
            errs.append(f"컬럼 {c['name']}: pi.crypto 는 aes|hmac|aes+hmac")
    return errs


def register_words(plan: dict, gl) -> list[str]:
    ws = [Word(w["kor"], w["abbr"].lower(), w["full"].lower(), bool(w.get("is_class")), w.get("desc", ""))
          for w in plan.get("words_to_register", []) if w.get("abbr") and w.get("full")]
    bad = [w for w in ws if not re.match(r"^[a-z][a-z0-9]*$", w.abbr) or not re.match(r"^[a-z][a-z0-9_]*$", w.full)]
    if bad:
        raise PlanError(f"단어 형식 오류(소문자·숫자): {[w.kor for w in bad]}")
    return gl.register(ws) if ws else []


# ---------------- model.json 생성 ----------------
def _domain_of(typ: str) -> tuple[str, str]:
    m = re.match(r"varchar\((\d+)\)", typ)
    if m: return f"문자({m.group(1)})", typ
    m = re.match(r"numeric\((\d+),(\d+)\)", typ)
    if m: return f"숫자({m.group(1)},{m.group(2)})", typ
    return {"integer": ("정수", typ), "bigint": ("큰정수", typ), "date": ("일자", typ), "timestamptz": ("시각", typ),
            "boolean": ("여부", typ), "text": ("텍스트", typ), "bytea": ("바이트", typ)}.get(typ, (typ, typ))


def _pi_parts(c):
    """개인정보 컬럼 → pi_ 테이블 컬럼들 [(name, kor, crypto)]"""
    cr = (c.get("pi") or {}).get("crypto") or ""
    out = []
    if "aes" in cr: out.append((c["name"] + "_enc", c["kor"] + "암호문", "aes"))
    if "hmac" in cr: out.append((c["name"] + "_hash", c["kor"] + "해시", "hmac"))
    return out


def build_model(plan: dict, gl) -> dict:
    t = plan["target"]; T = t["table"]; S = t["schema"]
    abbr_of = lambda full_tok: (gl.lookup(full_tok).abbr if gl.lookup(full_tok) else full_tok)
    idc = "_".join(abbr_of(x) for x in T.split("_")) + "_id"
    doms = {"식별자": ("bigint", "시스템 대리키"), "시각": ("timestamptz", "일시"),
            "암호문": ("bytea", "AES-128-GCM 암호문(키번호1+nonce12+암호문+태그)"), "해시값": ("bytea", "HMAC-SHA256 32바이트")}
    cols_main = [{"name": idc, "kor": t.get("kor", T) + "식별자", "domain": "식별자", "nullable": False, "pk": True, "identity": True}]
    cols_pi = [{"name": idc, "kor": t.get("kor", T) + "식별자", "domain": "식별자", "nullable": False, "pk": True,
                "fk": {"table": T, "column": idc, "on_delete": "CASCADE"}}]
    for c in plan["columns"]:
        if c.get("skip"):
            continue
        if c.get("pi") and c["pi"].get("crypto"):
            for n, k, cr in _pi_parts(c):
                cols_pi.append({"name": n, "kor": k, "domain": "암호문" if cr == "aes" else "해시값", "nullable": True,
                                "pi": True, "crypto": cr, "pi_type": c["pi"].get("pi_type", "개인정보"),
                                "sensitive": bool(c["pi"].get("sensitive")), "description": f"원본: {c['src']}"})
            continue
        dn, ty = _domain_of(c["type"]); doms.setdefault(dn, (ty, c["type"]))
        cols_main.append({"name": c["name"], "kor": c["kor"], "domain": dn, "nullable": True, "description": f"원본: {c['src']}"})
    aud = [{"name": "job_id", "kor": "작업식별자", "domain": "식별자", "nullable": True, "description": "ingest.job 적재 작업"},
           {"name": "created_at", "kor": "생성시각", "domain": "시각", "nullable": False, "default": "now()"},
           {"name": "updated_at", "kor": "수정시각", "domain": "시각", "nullable": False, "default": "now()"}]
    tables = [{"name": T, "schema": S, "kor": t.get("kor", T), "kind": "기준", "is_pi": False,
               "description": f"{plan['source'].get('name')} 적재 테이블 (원천: {plan['source'].get('provider') or plan['source']['type']})",
               "columns": cols_main + aud}]
    if len(cols_pi) > 1:
        tables.append({"name": "pi_" + T, "kor": t.get("kor", T) + "개인정보", "kind": "PI", "is_pi": True,
                       "description": f"{T} 의 개인정보(암호화). {T} 와 1:1", "columns": cols_pi + aud[1:]})
    names = [x["name"] for tb in tables for x in tb["columns"]] + [tb["name"] for tb in tables]
    words = gl.model_words(names)
    tok2kor = {}
    for w in words:
        tok2kor[w["abbr"]] = w["kor"]; tok2kor[w["full"]] = w["kor"]
    terms = {}
    for tb in tables:
        terms.setdefault(tb["name"], {"kor": tb["kor"], "phys": tb["name"], "word_path": ">".join(tok2kor.get(x, x) for x in tb["name"].split("_")), "domain": None, "desc": tb["description"]})
        for x in tb["columns"]:
            terms.setdefault(x["name"], {"kor": x["kor"], "phys": x["name"], "word_path": ">".join(tok2kor.get(y, y) for y in x["name"].split("_")), "domain": x["domain"], "desc": x.get("description")})
    rels = [{"from": tb["name"], "from_col": x["name"], "to": x["fk"]["table"], "to_col": x["fk"]["column"], "type": "1:1",
             "optional": False, "on_delete": "CASCADE", "meaning": "본체 → 개인정보 1:1"} for tb in tables for x in tb["columns"] if x.get("fk")]
    pol = t.get("policy") or None
    return {
        "project": f"{t.get('kor', T)} 적재", "version": "1.0", "generated_at": dt.date.today().isoformat(),
        "db": "postgresql", "db_version": "16", "schema": S, "meta_schema": "meta", "meta_mode": "shared", "pi_schema": "pi",
        "pi_crypto_required": True, "modeling_tool": "pgModeler 1.1",
        "assumptions": [f"원천: {plan['source'].get('src')}", "원본 컬럼은 모두 NULL 허용(원천 품질 미보장)", "개인정보는 pi 스키마에 암호화 저장"],
        "open_questions": [], "words": words,
        "domains": [{"name": k, "type": v[0], "check": None, "example": "", "desc": v[1]} for k, v in doms.items()],
        "terms": list(terms.values()), "tables": tables, "relationships": rels,
        "access_policies": ([{"schema": S, "table": T, "min_grade": pol.get("min_grade"), "category": pol.get("category")}] if pol else []),
        "pi_suggestions": ["마스킹 뷰 제공 검토", "보존기간 경과 시 파기"], "dq_notes": ["원천 데이터 적재용 — 업무 모델링 시 정규화 재검토"],
    }


def _run(cmd):
    from ..compat import run_py
    r = run_py(cmd[1:]) if cmd and cmd[0] == sys.executable else subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise PlanError(f"{os.path.basename(cmd[1])} 실패:\n{r.stdout}\n{r.stderr}")
    return r.stdout


# ---------------- 값 변환 ----------------
def _conv(typ: str, v):
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    if typ in ("integer", "bigint"):
        return int(s.replace(",", ""))
    if typ.startswith("numeric"):
        return Decimal(s.replace(",", ""))
    if typ == "boolean":
        return s.lower() in ("y", "yes", "true", "t", "1")
    if typ == "date":
        for f in ("%Y-%m-%d", "%Y%m%d", "%Y.%m.%d", "%Y/%m/%d"):
            try:
                return dt.datetime.strptime(s.rstrip("."), f).date()
            except ValueError:
                pass
        raise ValueError(s)
    if typ == "timestamptz":
        return dt.datetime.fromisoformat(s.replace("/", "-").replace(".", "-", 2) if re.match(r"^\d{4}\.", s) else s.replace("/", "-"))
    m = re.match(r"varchar\((\d+)\)", typ)
    if m and len(s) > int(m.group(1)):
        raise ValueError(f"길이 초과({len(s)}>{m.group(1)})")
    return s


def _chunks(plan):
    f, sheet = plan["source"]["file"], plan["source"].get("sheet")
    if f.lower().endswith((".csv", ".tsv", ".txt")):
        yield from iter_csv(f)
    else:
        for _, df in read(f, sheet=sheet).items():
            yield df


def plan_digest(plan: dict) -> str:
    """승인 대상이 된 계획의 지문 — approved/approval 을 뺀 내용의 SHA-256"""
    import hashlib
    body = {k: v for k, v in plan.items() if k not in ("approved", "approval")}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def check_approval(conn, plan: dict, approval: dict | None) -> dict:
    """승인 증거 검사. 사용자 답을 그대로 인용한 quote 와 실행 계정(by)이 필수.
    새 DB 테이블을 만드는 적재는 물리 생성 승인(physical_quote)이 따로 필요하다(자동 승인 금지)."""
    from .. import access
    if not plan.get("approved"):
        raise PlanError("approved=false — 사용자 승인 후 apply 하세요")
    ap = dict(approval or plan.get("approval") or {})
    quote = (ap.get("quote") or "").strip()
    if not quote:
        raise PlanError("승인 근거 없음 — 사용자 답을 그대로 인용해 --approval-quote 로 넘기세요 (예: \"네, pub.shop 으로 적재해 주세요\")")
    if not ap.get("by"):
        raise PlanError("실행 계정 없음 — --by <login_id>")
    acct = access.load_account(conn, login_id=ap["by"])
    if not acct:
        raise PlanError(f"계정 없음: {ap['by']}")
    ok, why = access.authorize_action(conn, acct, "INGEST")
    if not ok:
        raise PlanError(f"적재 권한 없음({ap['by']}): {why}")
    creates = plan.get("store", "DB") == "DB" and plan["target"].get("mode") == "new"
    if creates and not (ap.get("physical_quote") or "").strip():
        raise PlanError(f"새 테이블 {plan['target']['schema']}.{plan['target']['table']} 생성 — 물리 생성 승인이 따로 필요합니다. "
                        "사용자 답을 인용해 --physical-quote 로 넘기세요")
    import datetime as _dt
    return {"by": acct.login_id, "acct_id": acct.acct_id, "quote": quote,
            "physical_quote": (ap.get("physical_quote") or "").strip() or None,
            "creates_table": creates, "at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "plan_sha256": plan_digest(plan), "target": f"{plan['target']['schema']}.{plan['target']['table']}",
            "mode": plan["target"].get("mode"), "store": plan.get("store", "DB"),
            "pi_columns": [c["src"] for c in plan["columns"] if c.get("pi") and not c.get("skip")],
            "words_to_register": [w["kor"] for w in plan.get("words_to_register", []) if w.get("abbr") and w.get("full")]}


def apply(conn, cfg, gl, plan: dict, acct_id=None, workdir=None, approval: dict | None = None) -> dict:
    from ..db import audit
    evidence = check_approval(conn, plan, approval)   # 승인 증거가 없으면 단어 등록·DB 변경 전에 멈춘다
    acct_id = evidence["acct_id"]
    reg = register_words(plan, gl)
    errs = validate_plan(plan, gl)
    if errs:
        raise PlanError("\n".join(errs))
    cr = Crypto(cfg["crypto"])
    t = plan["target"]; S, T = t["schema"], t["table"]
    src = plan["source"]
    sid = conn.execute("INSERT INTO ingest.source (src_nm, src_type_cd, src_url, provider_nm, license_nm) VALUES (%s,%s,%s,%s,%s) RETURNING src_id",
                       (src.get("name") or T, src.get("type", "FILE"), src.get("src"), src.get("provider"), src.get("license"))).fetchone()["src_id"]
    job = conn.execute("INSERT INTO ingest.job (src_id, target_schema_nm, target_table_nm, store_type_cd, status_cd, start_at, acct_id, profile_val, aprv_val) "
                       "VALUES (%s,%s,%s,%s,'RUNNING',now(),%s,%s,%s) RETURNING job_id",
                       (sid, S, T, plan.get("store", "DB"), acct_id, json.dumps({"columns": len(plan["columns"]), "rows_estimated": plan.get("rows_estimated")}),
                        json.dumps(evidence, ensure_ascii=False))).fetchone()["job_id"]
    audit(conn, acct_id, "INGEST_APPLY", evidence["target"], {**evidence, "job_id": job})
    conn.commit()
    rep = {"job_id": job, "registered_words": reg, "approval": {k: evidence[k] for k in ("by", "quote", "physical_quote", "plan_sha256")}}
    try:
        if plan.get("store") == "LAKE":
            from .lake import write_lake
            rep.update(write_lake(conn, cfg, cr, plan, _chunks(plan), sid))
        else:
            if t["mode"] == "new":
                rep["model"] = _create(conn, cfg, gl, plan, workdir)
            rep.update(_load_db(conn, cr, plan, job))
        conn.execute("UPDATE ingest.job SET status_cd='DONE', row_cnt=%s, end_at=now(), msg_val=%s, updated_at=now() WHERE job_id=%s",
                     (rep.get("rows", 0), json.dumps({k: v for k, v in rep.items() if k in ("bad_values", "model", "dataset")}, ensure_ascii=False, default=str)[:4000], job))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.execute("UPDATE ingest.job SET status_cd='FAIL', end_at=now(), msg_val=%s, updated_at=now() WHERE job_id=%s", (str(e)[:4000], job))
        audit(conn, acct_id, "INGEST_FAIL", evidence["target"], {"job_id": job, "error": str(e)[:500]})
        conn.commit()
        raise
    return rep


def _create(conn, cfg, gl, plan, workdir):
    T = plan["target"]["table"]
    wd = workdir or os.path.join(cfg["ingest"]["work_dir"], "models", T)
    os.makedirs(wd, exist_ok=True)
    model = build_model(plan, gl)
    mp = os.path.join(wd, "model.json")
    json.dump(model, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    _run([sys.executable, os.path.join(DM_SCRIPTS, "check_dictionary.py"), mp])
    _run([sys.executable, os.path.join(DM_SCRIPTS, "export_all.py"), mp, wd])
    ddl = open(os.path.join(wd, "02_ddl_postgresql.sql"), encoding="utf-8").read()
    if conn.execute("SELECT to_regclass(%s) IS NOT NULL ok", (f"{plan['target']['schema']}.{T}",)).fetchone()["ok"]:
        raise PlanError(f"{plan['target']['schema']}.{T} 가 이미 있습니다 — mode=append 로 바꾸거나 다른 이름을 쓰세요")
    conn.execute(ddl)  # BEGIN … COMMIT 포함
    conn.commit()
    access.sync(conn, cfg)
    return {"dir": wd, "files": ["model.json", "02_ddl_postgresql.sql", "03_model.dbm", "04_table_spec.xlsx"]}


def _load_db(conn, cr: Crypto, plan, job) -> dict:
    t = plan["target"]; S, T = t["schema"], t["table"]
    cols = [c for c in plan["columns"] if not c.get("skip")]
    plain = [c for c in cols if not (c.get("pi") and c["pi"].get("crypto"))]
    pic = [c for c in cols if c.get("pi") and c["pi"].get("crypto")]
    exist = {r["column_name"]: r["data_type"] for r in conn.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema=%s AND table_name=%s", (S, T))}
    if not exist:
        raise PlanError(f"{S}.{T} 없음")
    miss = [c["name"] for c in plain if c["name"] not in exist]
    if miss:
        raise PlanError(f"대상 테이블에 없는 컬럼: {miss}")
    pk = conn.execute("SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey) "
                      "WHERE i.indrelid=(%s)::regclass AND i.indisprimary", (f"{S}.{T}",)).fetchall()
    idc = pk[0]["attname"] if len(pk) == 1 else None
    if pic and not conn.execute("SELECT to_regclass(%s) IS NOT NULL ok", (f"pi.pi_{T}",)).fetchone()["ok"]:
        raise PlanError(f"개인정보 컬럼이 있는데 pi.pi_{T} 가 없습니다")
    names = [c["name"] for c in plain] + (["job_id"] if "job_id" in exist else [])
    ins = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(
        sql.Identifier(S), sql.Identifier(T), sql.SQL(", ").join(map(sql.Identifier, names)), sql.SQL(", ").join(sql.Placeholder() * len(names)))
    if pic:
        ins = ins + sql.SQL(" RETURNING {}").format(sql.Identifier(idc))
        pcols = [idc] + [n for c in pic for n, _, _ in _pi_parts(c)]
        pins = sql.SQL("INSERT INTO pi.{} ({}) VALUES ({})").format(
            sql.Identifier("pi_" + T), sql.SQL(", ").join(map(sql.Identifier, pcols)), sql.SQL(", ").join(sql.Placeholder() * len(pcols)))
    total, bad = 0, {}
    for df in _chunks(plan):
        recs, precs = [], []
        for _, row in df.iterrows():
            vals = []
            for c in plain:
                try:
                    vals.append(_conv(c["type"], row.get(c["src"])))
                except (ValueError, InvalidOperation):
                    bad[c["name"]] = bad.get(c["name"], 0) + 1; vals.append(None)
            if "job_id" in exist:
                vals.append(job)
            recs.append(vals)
            if pic:
                pv = []
                for c in pic:
                    raw = row.get(c["src"])
                    for _, _, m in _pi_parts(c):
                        pv.append(cr.apply(m, raw))
                precs.append(pv)
        with conn.cursor() as cur:
            if pic:
                cur.executemany(ins, recs, returning=True)
                ids = []
                while True:
                    ids.append(cur.fetchone()[idc])
                    if not cur.nextset():
                        break
                cur.executemany(pins, [[i] + p for i, p in zip(ids, precs)])
            else:
                with cur.copy(sql.SQL("COPY {}.{} ({}) FROM STDIN").format(sql.Identifier(S), sql.Identifier(T),
                                                                         sql.SQL(", ").join(map(sql.Identifier, names)))) as cp:
                    for r in recs:
                        cp.write_row(r)
        total += len(recs)
        conn.commit()
    return {"rows": total, "bad_values": bad, "pi_rows": total if pic else 0}
