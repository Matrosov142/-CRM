#!/bin/sh
set -eu

# This one-shot container is the only application-side service that receives
# the PostgreSQL bootstrap administrator password. It exits before API starts.
export PGPASSWORD="${DB_ADMIN_PASSWORD}"
if ! psql -h db -U potok_admin -d potok_crm -Atqc 'SELECT 1' >/dev/null 2>&1; then
  # Upgrade an older pilot volume whose initial PostgreSQL superuser was potok_owner.
  export PGPASSWORD="${DB_OWNER_PASSWORD}"
  psql -h db -U potok_owner -d potok_crm -v ON_ERROR_STOP=1 \
    -v admin_password="${DB_ADMIN_PASSWORD}" <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'potok_admin') THEN
    CREATE ROLE potok_admin;
  END IF;
END
$$;
ALTER ROLE potok_admin WITH LOGIN SUPERUSER PASSWORD :'admin_password';
ALTER ROLE potok_owner WITH NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
SQL
  export PGPASSWORD="${DB_ADMIN_PASSWORD}"
fi

psql -h db -U potok_admin -d potok_crm -v ON_ERROR_STOP=1 \
  -v owner_password="${DB_OWNER_PASSWORD}" \
  -v runtime_password="${RUNTIME_DB_PASSWORD}" <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'potok_owner') THEN
    CREATE ROLE potok_owner;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'potok_runtime') THEN
    CREATE ROLE potok_runtime;
  END IF;
END
$$;

ALTER ROLE potok_owner WITH LOGIN PASSWORD :'owner_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
ALTER ROLE potok_runtime WITH LOGIN PASSWORD :'runtime_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

GRANT CONNECT ON DATABASE potok_crm TO potok_owner, potok_runtime;
GRANT USAGE, CREATE ON SCHEMA public TO potok_owner;
GRANT USAGE ON SCHEMA public TO potok_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE potok_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO potok_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE potok_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO potok_runtime;
SQL

unset PGPASSWORD DB_ADMIN_PASSWORD DB_OWNER_PASSWORD RUNTIME_DB_PASSWORD
echo "PostgreSQL role bootstrap completed."
