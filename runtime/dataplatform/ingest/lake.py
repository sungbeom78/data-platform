"""로그성·대용량 데이터의 디스크 저장(Parquet, 월 파티션) + DuckDB 조회.
DB 에는 ingest.lake_dataset 카탈로그만 남기고, 필요하면 일/월 집계만 DB 테이블로 만든다.
개인정보 컬럼은 레이크에 원문을 쓰지 않는다: lake_pi_policy=hmac → 검색 해시(16진)만, drop → 제외."""
from __future__ import annotations
import os, re, json
import pandas as pd
import pyarrow as pa, pyarrow.parquet as pq
from .load import _conv


def _part_value(v) -> str:
    s = str(v or "")
    m = re.match(r"(\d{4})[-./]?(\d{2})", s)
    return f"{m.group(1)}{m.group(2)}" if m else "unknown"


def write_lake(conn, cfg, cr, plan, chunks, src_id) -> dict:
    t = plan["target"]
    name = f"{t['schema']}__{t['table']}"
    root = os.path.abspath(os.path.join(cfg["ingest"]["lake_dir"], name))
    os.makedirs(root, exist_ok=True)
    policy = cfg["ingest"].get("lake_pi_policy", "hmac")
    pcol = (plan.get("lake") or {}).get("partition_by")
    cols = [c for c in plan["columns"] if not c.get("skip")]
    total, files, dropped = 0, 0, []
    for i, df in enumerate(chunks):
        out = {}
        for c in cols:
            s = df[c["src"]] if c["src"] in df.columns else pd.Series([None] * len(df))
            if c.get("pi") and c["pi"].get("crypto"):
                if policy == "drop":
                    dropped.append(c["name"]); continue
                out[c["name"] + "_hash"] = s.map(lambda v: cr.hmac(v).hex() if v is not None else None)
                continue
            def safe(v, ty=c["type"]):
                try:
                    r = _conv(ty, v)
                    return float(r) if hasattr(r, "as_tuple") else r
                except Exception:
                    return None
            out[c["name"]] = s.map(safe)
        frame = pd.DataFrame(out)
        frame["ym"] = df[next(c["src"] for c in cols if c["name"] == pcol)].map(_part_value) if pcol and any(c["name"] == pcol for c in cols) else "all"
        for ym, part in frame.groupby("ym"):
            d = os.path.join(root, f"ym={ym}"); os.makedirs(d, exist_ok=True)
            pq.write_table(pa.Table.from_pandas(part.drop(columns=["ym"]), preserve_index=False),
                           os.path.join(d, f"part-{i:05d}.parquet"), compression="zstd")
            files += 1
        total += len(frame)
    size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(root) for f in fs)
    conn.execute("INSERT INTO ingest.lake_dataset (dataset_nm, path_val, partition_col_nm, row_cnt, byte_cnt, src_id) "
                 "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (dataset_nm) DO UPDATE SET row_cnt=ingest.lake_dataset.row_cnt+EXCLUDED.row_cnt, "
                 "byte_cnt=EXCLUDED.byte_cnt, updated_at=now()", (name, root, pcol, total, size, src_id))
    conn.commit()
    return {"rows": total, "dataset": name, "path": root, "files": files, "bytes": size, "pi_dropped": sorted(set(dropped)),
            "query_example": f"python -m dataplatform lake-query \"SELECT ym, count(*) FROM {name} GROUP BY 1 ORDER BY 1\""}


def query(conn, cfg, sql_text: str, limit: int = 1000) -> pd.DataFrame:
    """레이크 데이터셋을 이름으로 참조하는 SQL 실행 (DuckDB). 예: SELECT … FROM pub__access_log WHERE ym='202609'"""
    import duckdb
    from ..compat import posix_path
    db = duckdb.connect()
    for r in conn.execute("SELECT dataset_nm, path_val FROM ingest.lake_dataset WHERE use_yn"):
        name = r["dataset_nm"].replace('"', '""')
        db.execute(f"CREATE VIEW \"{name}\" AS SELECT * FROM read_parquet('{posix_path(r['path_val'])}/**/*.parquet', "
                   "hive_partitioning=1, hive_types_autocast=0)")
    return db.execute(f"SELECT * FROM ({sql_text}) q LIMIT {int(limit)}").df()
