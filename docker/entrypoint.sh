#!/usr/bin/env bash
# docker/entrypoint.sh — Container entrypoint
# Runs DB migrations then starts Gunicorn (production) or Uvicorn (development).
set -euo pipefail

log() { echo "[entrypoint] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }

# ── Wait for MySQL ─────────────────────────────────────────────────────────
wait_for_db() {
  local retries=30
  log "Waiting for database..."
  until python -c "
import asyncio, sys, os
from sqlalchemy.ext.asyncio import create_async_engine
async def ping():
    url = os.getenv('DATABASE_URL', '')
    if not url:
        sys.exit(0)
    engine = create_async_engine(url, pool_pre_ping=True)
    async with engine.connect() as c:
        await c.execute(__import__('sqlalchemy').text('SELECT 1'))
    await engine.dispose()
asyncio.run(ping())
" 2>/dev/null; do
    retries=$((retries - 1))
    if [ "$retries" -eq 0 ]; then
      log "ERROR: Database not reachable after 30 attempts. Aborting."
      exit 1
    fi
    log "  database not ready, retrying in 2s ($retries attempts left)..."
    sleep 2
  done
  log "Database is ready."
}

# ── Run Alembic migrations ─────────────────────────────────────────────────
run_migrations() {
  log "Running Alembic migrations..."
  alembic upgrade head
  log "Migrations complete."
}

# ── Main ───────────────────────────────────────────────────────────────────
ENVIRONMENT="${ENVIRONMENT:-production}"
SKIP_MIGRATIONS="${SKIP_MIGRATIONS:-false}"

# Workers: skip migrations (they have no DB write role)
if [ "${WORKER_MODE:-false}" = "true" ]; then
  log "Worker mode — skipping migrations."
else
  wait_for_db
  if [ "$SKIP_MIGRATIONS" != "true" ]; then
    run_migrations
  fi
fi

# Start the correct server
if [ "$ENVIRONMENT" = "development" ]; then
  log "Starting Uvicorn (development / hot-reload)..."
  exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level info
else
  log "Starting Gunicorn (production)..."
  exec gunicorn app.main:app \
    -c gunicorn.conf.py
fi