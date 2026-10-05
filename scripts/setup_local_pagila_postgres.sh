#!/bin/zsh
set -euo pipefail

if [[ $# -lt 1 ]]; then
 echo "usage: $0 /path/to/pagila-repo-or-files"
 exit 1
fi

PAGILA_DIR="$1"
PG_BIN_DIR="${PG_BIN_DIR:-/opt/homebrew/opt/libpq/bin}"
INITDB="${PG_BIN_DIR}/initdb"
PG_CTL="${PG_BIN_DIR}/pg_ctl"
CREATEDB="${PG_BIN_DIR}/createdb"
PSQL="${PG_BIN_DIR}/psql"
PGDATA_DIR="${PGDATA_DIR:-/Users/richiek/work/tahi/.local/pagila-pgdata}"
PGHOST_DIR="${PGHOST_DIR:-/Users/richiek/work/tahi/.local}"
PGPORT="${PGPORT:-55432}"
PGDATABASE="${PGDATABASE:-pagila}"

SCHEMA_SQL="${PAGILA_DIR}/pagila-schema.sql"
DATA_SQL="${PAGILA_DIR}/pagila-data.sql"
INSERT_SQL="${PAGILA_DIR}/pagila-insert-data.sql"
SANITIZED_DIR="${PGDATA_DIR}-sanitized"
SANITIZED_SCHEMA_SQL="${SANITIZED_DIR}/pagila-schema.sql"
SANITIZED_DATA_SQL="${SANITIZED_DIR}/pagila-data.sql"

if [[ ! -x "${INITDB}" || ! -x "${PG_CTL}" || ! -x "${CREATEDB}" || ! -x "${PSQL}" ]]; then
 echo "postgres client binaries not found in ${PG_BIN_DIR}"
 exit 1
fi

if [[ ! -f "${SCHEMA_SQL}" ]]; then
 echo "missing ${SCHEMA_SQL}"
 exit 1
fi

if [[ ! -f "${DATA_SQL}" && ! -f "${INSERT_SQL}" ]]; then
 echo "missing pagila-data.sql and pagila-insert-data.sql in ${PAGILA_DIR}"
 exit 1
fi

mkdir -p "${PGHOST_DIR}"
mkdir -p "$(dirname "${PGDATA_DIR}")"
mkdir -p "${SANITIZED_DIR}"

awk '
BEGIN {
 skipping_json_table_view = 0
}
/^SET transaction_timeout = 0;$/ {
 next
}
/^ALTER (SCHEMA|TYPE|DOMAIN|FUNCTION|PROCEDURE|AGGREGATE|SEQUENCE|TABLE|VIEW|MATERIALIZED VIEW) .* OWNER TO postgres;$/ {
 next
}
/^CREATE VIEW public\.films_per_customer_rental AS$/ {
 print "CREATE VIEW public.films_per_customer_rental AS"
 print " SELECT NULL::date AS rental_date,"
 print " NULL::text AS customer,"
 print " NULL::bigint AS film_no,"
 print " NULL::text AS title,"
 print " NULL::public.mpaa_rating AS mpaa"
 print " WHERE false;"
 skipping_json_table_view = 1
 next
}
skipping_json_table_view {
 if ($0 ~ /^--/) {
 skipping_json_table_view = 0
 print
 }
 next
}
{
 print
}
' "${SCHEMA_SQL}" > "${SANITIZED_SCHEMA_SQL}"
if [[ -f "${DATA_SQL}" ]]; then
 cp "${DATA_SQL}" "${SANITIZED_DATA_SQL}"
fi

if [[ ! -d "${PGDATA_DIR}" ]]; then
 "${INITDB}" -D "${PGDATA_DIR}" >/dev/null
fi

if ! "${PG_CTL}" -D "${PGDATA_DIR}" status >/dev/null 2>&1; then
 "${PG_CTL}" -D "${PGDATA_DIR}" -o "-k ${PGHOST_DIR} -p ${PGPORT}" -l "${PGDATA_DIR}/server.log" start >/dev/null
fi

"${PG_BIN_DIR}/dropdb" -h "${PGHOST_DIR}" -p "${PGPORT}" --if-exists "${PGDATABASE}" >/dev/null 2>&1 || true
"${CREATEDB}" -h "${PGHOST_DIR}" -p "${PGPORT}" "${PGDATABASE}"

"${PSQL}" -h "${PGHOST_DIR}" -p "${PGPORT}" -d "${PGDATABASE}" -v ON_ERROR_STOP=1 -f "${SANITIZED_SCHEMA_SQL}" >/dev/null
if [[ -f "${DATA_SQL}" ]]; then
 "${PSQL}" -h "${PGHOST_DIR}" -p "${PGPORT}" -d "${PGDATABASE}" -v ON_ERROR_STOP=1 -f "${SANITIZED_DATA_SQL}" >/dev/null
else
 "${PSQL}" -h "${PGHOST_DIR}" -p "${PGPORT}" -d "${PGDATABASE}" -v ON_ERROR_STOP=1 -f "${INSERT_SQL}" >/dev/null
fi

echo "Pagila is ready."
echo "export PGHOST=127.0.0.1"
echo "export PGPORT=${PGPORT}"
echo "export PGDATABASE=${PGDATABASE}"
echo "export PGUSER=postgres"
echo "Run:"
echo " PYTHONPATH=/Users/richiek/work/tahi/src python3 /Users/richiek/work/tahi/examples/postgres_pagila_schema_demo.py --live-postgres"
