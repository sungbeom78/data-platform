#!/usr/bin/env python3
"""임시 PostgreSQL 인스턴스를 띄워 DDL(과 선택적 스모크 테스트)을 실제로 실행한다 — Windows·macOS·Linux 공용.
(validate_pg.sh 와 같은 일을 하는 파이썬 판. bash 가 없는 Windows 에서는 이것을 쓴다)

사용:  python validate_pg.py 02_ddl_postgresql.sql [smoke_test.sql]
종료코드: 0 통과 · 1 DDL/스모크 실패 · 77 PostgreSQL 이 없어 실행 못 함(통과 아님)
PostgreSQL 찾는 순서: PATH 의 pg_ctl → /usr/lib/postgresql/*/bin → C:/Program Files/PostgreSQL/*/bin → 환경변수 PG_BIN
"""
from __future__ import annotations
import glob, os, shlex, shutil, socket, subprocess, sys, tempfile
from pathlib import Path

SKIP_ENV = 77


def pg_bin() -> Path | None:
    if os.environ.get("PG_BIN") and Path(os.environ["PG_BIN"]).exists():
        return Path(os.environ["PG_BIN"])
    w = shutil.which("pg_ctl")
    if w:
        return Path(w).parent
    c = sorted(glob.glob("/usr/lib/postgresql/*/bin")) + sorted(glob.glob("C:/Program Files/PostgreSQL/*/bin"))
    return Path(c[-1]) if c else None


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):  # cp949 콘솔에서도 죽지 않게
        try:
            s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    ddl = Path(argv[0]).resolve()
    smoke = Path(argv[1]).resolve() if len(argv) > 1 else None
    b = pg_bin()
    if b is None:
        print("[validate] PostgreSQL(initdb/pg_ctl/psql)을 찾지 못함 — 설치하거나 PG_BIN 을 지정하세요. (미실행: 통과 아님)")
        return SKIP_ENV
    ext = ".exe" if os.name == "nt" else ""
    as_root = os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() == 0
    if as_root and subprocess.run(["id", "postgres"], capture_output=True).returncode != 0:
        print("[validate] root 로는 postgres 를 띄울 수 없고 postgres 사용자도 없음")
        return SKIP_ENV
    env = dict(os.environ, PGCLIENTENCODING="UTF8")

    def run(args):
        args = [str(a) for a in args]
        if as_root:
            args = ["su", "postgres", "-c", shlex.join(args)]
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)

    work = Path(tempfile.mkdtemp(prefix="pgvalidate-"))
    os.chmod(work, 0o777)
    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        port = so.getsockname()[1]
    data, log = work / "data", work / "pg.log"
    host = "127.0.0.1" if os.name == "nt" else str(work)
    shutil.copy(ddl, work / "ddl.sql")
    if smoke:
        shutil.copy(smoke, work / "smoke.sql")
    for f in work.iterdir():
        os.chmod(f, 0o666)
    try:
        r = run([b / f"initdb{ext}", "-D", data, "-E", "UTF8", "--no-locale", "-A", "trust", "-U", "postgres"])
        if r.returncode != 0:
            print("[validate] initdb 실패\n" + r.stderr[-1500:])
            return SKIP_ENV
        opts = f"-p {port}" + ("" if os.name == "nt" else f" -k {work}")
        r = run([b / f"pg_ctl{ext}", "-D", data, "-o", opts, "-l", log, "-w", "start"])
        if r.returncode != 0:
            print("[validate] postgres 시작 실패\n" + (r.stderr + (log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""))[-1500:])
            return SKIP_ENV
        psql = [b / f"psql{ext}", "-h", host, "-p", port, "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1"]
        print("[validate] DDL 실행 ...")
        r = run(psql + ["-q", "-f", work / "ddl.sql"])
        if r.returncode != 0:
            print("[validate] DDL_FAIL\n" + r.stderr.strip()[-2000:])
            return 1
        print("[validate] DDL_OK")
        for label, q in (("tables", "select count(*) from information_schema.tables where table_schema not in ('pg_catalog','information_schema')"),
                         ("fks", "select count(*) from information_schema.table_constraints where constraint_type='FOREIGN KEY'")):
            print(f"{label}=" + run(psql + ["-Atc", q]).stdout.strip())
        q = run(psql + ["-Atc", "select count(*) from information_schema.columns c where table_schema not in "
                                "('pg_catalog','information_schema','meta') and not exists (select 1 from meta.term t where t.phys_name=c.column_name)"])
        if q.returncode == 0:
            print("cols_not_in_term=" + q.stdout.strip())
        if smoke:
            print("[validate] 스모크 테스트 ...")
            r = run(psql + ["-At", "-f", work / "smoke.sql"])
            text = r.stdout + r.stderr
            lines = [l for l in text.splitlines() if any(k in l for k in ("OK:", "rows", "ERROR", "FAIL"))]
            print("\n".join(lines))
            if r.returncode != 0 or any(("FAIL" in l or "ERROR" in l) for l in lines):
                return 1
        print("[validate] done")
        return 0
    finally:
        run([b / f"pg_ctl{ext}", "-D", data, "stop", "-m", "immediate"])
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
