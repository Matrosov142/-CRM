#!/bin/sh
set -eu

# Only this short-lived job receives the schema-owner credential.
export MIGRATION_DATABASE_URL="postgresql+psycopg://potok_owner:${DB_OWNER_PASSWORD}@db:5432/potok_crm"
alembic upgrade head

# The schema owner grants runtime DML rights on objects it owns.
export PGPASSWORD="${DB_OWNER_PASSWORD}"
psql -h db -U potok_owner -d potok_crm -v ON_ERROR_STOP=1 <<'SQL'
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO potok_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO potok_runtime;
REVOKE UPDATE, DELETE ON audit_events FROM potok_runtime;
SQL

unset PGPASSWORD MIGRATION_DATABASE_URL DB_OWNER_PASSWORD RUNTIME_DB_PASSWORD
echo "Database migrations and runtime grants completed."
