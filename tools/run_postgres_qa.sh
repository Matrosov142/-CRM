#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://postgres:postgres@127.0.0.1:55432/potok_test}"
export TEST_ADMIN_DATABASE_URL="${TEST_ADMIN_DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:55432/potok_test}"
export TEST_RUNTIME_DATABASE_URL="${TEST_RUNTIME_DATABASE_URL:-postgresql://potok_runtime:runtime-only@127.0.0.1:55432/potok_test}"
export JWT_SECRET="${JWT_SECRET:-local-test-only-secret-not-for-production-0123456789}"

docker compose -f compose.postgres-test.yml up -d --wait
cleanup() { docker compose -f compose.postgres-test.yml down -v; }
trap cleanup EXIT

until docker exec potok-crm-postgres-test pg_isready -U postgres -d potok_test >/dev/null 2>&1; do sleep 1; done

docker exec -i potok-crm-postgres-test psql -U postgres -d potok_test -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='potok_runtime') THEN
    CREATE ROLE potok_runtime LOGIN PASSWORD 'runtime-only' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
  END IF;
END $$;
GRANT CONNECT ON DATABASE potok_test TO potok_runtime;
GRANT USAGE ON SCHEMA public TO potok_runtime;
SQL

python -m pip install -r requirements.txt
alembic upgrade head

docker exec -i potok-crm-postgres-test psql -U postgres -d potok_test -v ON_ERROR_STOP=1 <<'SQL'
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO potok_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO potok_runtime;
REVOKE UPDATE, DELETE ON audit_events FROM potok_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO potok_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO potok_runtime;
SQL

python -m compileall -q app migrations tests
python tools/release_audit.py
python -m pytest -q
