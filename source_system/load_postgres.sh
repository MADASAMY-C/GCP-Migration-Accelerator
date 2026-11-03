#!/usr/bin/env bash
# Load generated CSVs into Postgres. Honors PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE (defaults = docker-compose).
set -euo pipefail
export PGHOST="${PGHOST:-localhost}" PGPORT="${PGPORT:-5432}" PGUSER="${PGUSER:-retail}" PGPASSWORD="${PGPASSWORD:-retail}" PGDATABASE="${PGDATABASE:-retail}"
DATA_DIR="${1:-data}/oltp"
psql -v ON_ERROR_STOP=1 -f "$(dirname "$0")/schema.sql"
for t in customers products orders order_items payments; do
  echo "loading $t ..."
  psql -v ON_ERROR_STOP=1 -c "\\copy $t FROM '$DATA_DIR/$t.csv' WITH (FORMAT csv, HEADER true)"
done
psql -c "SELECT 'orders' AS t, COUNT(*) FROM orders UNION ALL SELECT 'customers', COUNT(*) FROM customers;"
