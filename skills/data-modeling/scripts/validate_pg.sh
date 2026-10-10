#!/usr/bin/env bash
# 임시 PostgreSQL 인스턴스를 띄워 DDL(과 선택적 스모크 테스트)을 실제로 실행한다.
# 사용: bash validate_pg.sh 02_ddl_postgresql.sql [smoke.sql]
# - Postgres 가 없으면 apt-get 으로 설치 시도 (root 권한 필요)
# - root 로는 postgres 가 안 뜨므로 'postgres' 시스템 사용자로 실행
# - 끝나면 인스턴스와 데이터 디렉터리를 삭제한다
set -euo pipefail
DDL=${1:?DDL 파일 경로}; SMOKE=${2:-}
PORT=${PGPORT_TMP:-5499}; WORK=/tmp/pgvalidate.$$

if ! ls -d /usr/lib/postgresql/*/bin >/dev/null 2>&1; then
  echo "[validate] postgres 없음 → apt-get 설치 시도"; apt-get install -y -q postgresql >/dev/null 2>&1 || { echo "[validate] 설치 실패 — pglast 구문검사로 대체하세요"; exit 2; }
fi
PGBIN=$(ls -d /usr/lib/postgresql/*/bin | sort -V | tail -1)
mkdir -p "$WORK"; cp "$DDL" "$WORK/ddl.sql"; [ -n "$SMOKE" ] && cp "$SMOKE" "$WORK/smoke.sql"; chmod -R a+rX "$WORK"; chown -R postgres "$WORK" 2>/dev/null || true
RUN="su postgres -c"; id postgres >/dev/null 2>&1 || RUN="bash -c"
cleanup(){ $RUN "$PGBIN/pg_ctl -D $WORK/data stop -m immediate >/dev/null 2>&1" || true; rm -rf "$WORK"; }
trap cleanup EXIT

$RUN "$PGBIN/initdb -D $WORK/data -E UTF8 --locale=C.UTF-8 >$WORK/initdb.log 2>&1"
$RUN "$PGBIN/pg_ctl -D $WORK/data -o '-p $PORT -k $WORK' -l $WORK/pg.log start >/dev/null"; sleep 2
PSQL="$PGBIN/psql -h $WORK -p $PORT -d postgres -v ON_ERROR_STOP=1"
echo "[validate] DDL 실행 ..."; $RUN "$PSQL -q -f $WORK/ddl.sql" && echo "[validate] DDL_OK"
$RUN "$PSQL -Atc \"select 'tables='||count(*) from information_schema.tables where table_schema not in ('pg_catalog','information_schema')\""
$RUN "$PSQL -Atc \"select 'fks='||count(*) from information_schema.table_constraints where constraint_type='FOREIGN KEY'\""
$RUN "$PSQL -Atc \"select 'cols_not_in_term='||count(*) from information_schema.columns c where table_schema not in ('pg_catalog','information_schema','meta') and not exists (select 1 from meta.term t where t.phys_name=c.column_name)\"" 2>/dev/null || true
if [ -n "$SMOKE" ]; then echo "[validate] 스모크 테스트 ..."; $RUN "$PSQL -Atq -f $WORK/smoke.sql" 2>&1 | grep -E "OK:|rows|ERROR|FAIL" || true; fi
echo "[validate] done"
