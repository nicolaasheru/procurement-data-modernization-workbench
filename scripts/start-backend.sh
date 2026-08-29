#!/usr/bin/env sh
set -eu

: "${DATABASE_URL:?DATABASE_URL must point to a PostgreSQL database with permission to create the vector extension}"

python -m backend.app.cli retrieval-migrate

if [ "${SKIP_RETRIEVAL_INDEX:-0}" != "1" ]; then
  python -m backend.app.cli retrieval-index --sqlite "${OPERATIONAL_DB_PATH:-/app/data/workbench.db}"
fi

exec uvicorn backend.app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --proxy-headers \
  --forwarded-allow-ips="*"
