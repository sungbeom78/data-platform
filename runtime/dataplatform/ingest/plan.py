"""적재 계획(ingest_plan.json) — 프로파일 + 용어사전 + 기존 테이블 비교로 '어디에 어떻게 넣을지' 초안을 만든다.
초안의 빈칸(테이블명·미등록 단어의 영문명)은 Claude/사용자가 채우고, approved=true 로 바꾼 뒤 apply 한다."""
from __future__ import annotations
import os, re
from .profile import profile as do_profile
from .source import fetch, read, estimate_rows


def _snake(s: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def propose_name(gl, label: str) -> dict:
    """원본 컬럼명 → 물리명 제안. 한글은 사전 단어 최장일치, 영문은 snake_case 토큰 검사"""
    if re.search(r"[가-힣]", label):
        words, rest = gl.compose_kor(label)
        if rest:
            return {"name": None, "kor": re.sub(r"\s+", "", label), "missing": [rest], "tokens": [w.abbr for w in words]}
        return {"name": "_".join(w.abbr for w in words), "kor": re.sub(r"\s+", "", label), "missing": [], "tokens": [w.abbr for w in words]}
    sn = _snake(label)
    miss = gl.check_identifier(sn) if sn else [label]
    return {"name": sn if sn and not miss else None, "kor": label, "missing": miss, "tokens": sn.split("_") if sn else []}


def source_maps(conn, exclude) -> dict:
    """이전 적재로 만든 테이블의 '원본: <원본컬럼명>' COMMENT → {(schema, table): {원본컬럼: 물리컬럼}}
    pi.pi_<t> 의 컬럼(_enc/_hash)은 본 테이블 <t> 쪽으로 합친다."""
    rows = conn.execute(
        "SELECT n.nspname s, c.relname t, a.attname col, substring(d.description from '원본: (.*)$') src "
        "FROM pg_description d JOIN pg_class c ON c.oid=d.objoid JOIN pg_namespace n ON n.oid=c.relnamespace "
        "JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=d.objsubid "
        "WHERE d.objsubid > 0 AND d.description LIKE '%%원본: %%' AND n.nspname <> ALL(%s)", (list(exclude),)).fetchall()
    out, pi = {}, {}
    for r in rows:
        src = re.sub(r"\s*\[.*$", "", r["src"] or "").strip()
        if r["s"] == "pi" and r["t"].startswith("pi_"):
            pi.setdefault(r["t"][3:], {})[src] = re.sub(r"_(enc|hash)$", "", r["col"])
        else:
            out.setdefault((r["s"], r["t"]), {})[src] = r["col"]
    for (s, t), m in out.items():
        m.update(pi.get(t, {}))
    return out


def match_tables(conn, names: list[str], exclude, srcs: list[str] | None = None) -> list[dict]:
    if conn is None:
        return []
    out = []
    if srcs:
        for (s, t), m in source_maps(conn, exclude).items():
            hit = [x for x in srcs if x in m]
            if hit:
                out.append({"schema": s, "table": t, "score": round(len(hit) / len(set(srcs) | set(m)), 3), "matched": len(hit),
                            "of": len(srcs), "by": "원본 컬럼명", "mapping": m})
    want = {n for n in names if n}
    if want:
        rows = conn.execute("SELECT table_schema s, table_name t, array_agg(column_name::text) cols FROM information_schema.columns "
                            "WHERE table_schema <> ALL(%s) AND table_schema NOT IN ('sec','api','ingest','meta','pi') "
                            "GROUP BY 1,2", (list(exclude),)).fetchall()
        seen = {(x["schema"], x["table"]) for x in out}
        for r in rows:
            if (r["s"], r["t"]) in seen:
                continue
            cols = set(r["cols"]) - {"created_at", "updated_at", "job_id"}
            inter = len(want & cols)
            if inter:
                out.append({"schema": r["s"], "table": r["t"], "score": round(inter / len(want | cols), 3), "matched": inter,
                            "of": len(want), "by": "물리 컬럼명"})
    return sorted(out, key=lambda x: -x["score"])[:5]


def make_plan(cfg, gl, conn, src: str, sheet=None, schema="pub", src_type=None, src_name=None, provider=None, license=None) -> dict:
    work = cfg["ingest"]["work_dir"]
    files = fetch(src, work)
    if not files:
        raise ValueError("표 형식 파일(csv/xlsx/json)을 찾지 못했습니다")
    path = files[0]
    sheets = read(path, sheet=sheet, nrows=50000)
    sname, df = next(iter(sheets.items()))
    total = estimate_rows(path)
    prof = do_profile(df, total_rows=total, file_bytes=os.path.getsize(path), cfg=cfg)
    cols = []
    for c in prof["columns"]:
        nm = propose_name(gl, c["src"])
        cols.append({"src": c["src"], "name": nm["name"], "kor": nm["kor"], "type": c["type"],
                     "nullable": True, "pi": c["pi"], "missing": nm["missing"], "samples": c["samples"],
                     "null_ratio": c["null_ratio"], "distinct": c["distinct"]})
    cand = match_tables(conn, [c["name"] for c in cols if not c["pi"]], cfg["access"]["exclude_schemas"], [c["src"] for c in cols])
    mode = "append" if cand and cand[0]["score"] >= 0.8 else "new"
    if mode == "append" and cand[0].get("mapping"):
        for c in cols:  # 이전 적재와 같은 원본 컬럼 → 같은 물리 컬럼
            if c["src"] in cand[0]["mapping"]:
                c["name"] = cand[0]["mapping"][c["src"]]; c["missing"] = []
    for x in cand:
        x.pop("mapping", None)
    missing = sorted({m for c in cols for m in c["missing"]})
    tname = None
    base = src_name or os.path.splitext(os.path.basename(path))[0]
    tw, trest = gl.compose_kor(base) if re.search(r"[가-힣]", base) else ([], base)
    if tw and not trest:
        tname = "_".join(w.full for w in tw)
    return {
        "version": 1, "approved": False,
        "source": {"src": src, "file": path, "other_files": files[1:], "sheet": sname if sheet is not None or path.lower().endswith(('.xlsx', '.xls', '.xlsm')) else None,
                   "type": src_type or ("URL" if re.match(r"^https?://", src) else "FILE"),
                   "name": src_name or base, "provider": provider, "license": license},
        "store": prof["store_recommendation"], "store_reasons": prof["store_reasons"],
        "target": {"schema": candidates_schema(cand, mode) or schema, "table": cand[0]["table"] if mode == "append" else tname,
                   "kor": base, "mode": mode, "candidates": cand, "policy": None},
        "lake": {"partition_by": prof["time_columns"][0] if prof["time_columns"] else None},
        "rows_estimated": prof["rows"], "file_bytes": prof["file_bytes"],
        "columns": cols,
        "words_to_register": [{"kor": m, "abbr": "", "full": "", "desc": ""} for m in missing],
        "notes": [
            "name 이 null 인 컬럼: missing 단어를 words_to_register 에 영문(full)·약어(abbr)로 채우고 name 을 지정",
            "테이블명은 단어 영문 전체형(full) 조합, 컬럼명은 약어(abbr) 조합",
            "pi.crypto: aes(복원 필요) / hmac(검색만) / aes+hmac(둘 다) — 비우면 개인정보 아님으로 처리",
            "store=LAKE 이면 DB 대신 Parquet(디스크)에 저장하고 DuckDB 로 조회",
            "검토 후 approved=true 로 바꾸고 apply",
        ],
    }


def candidates_schema(cand, mode):
    return cand[0]["schema"] if cand and mode == "append" else None
