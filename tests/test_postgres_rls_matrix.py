"""Structural RLS coverage gate for every tenant-owned table in PostgreSQL 16."""
import os
from urllib.parse import urlparse

import pytest

psycopg = pytest.importorskip("psycopg", reason="PostgreSQL RLS matrix requires psycopg")
RUNTIME_URL = os.getenv("TEST_RUNTIME_DATABASE_URL")


def _safe_test_url(url):
    return bool(url) and "test" in urlparse(url).path.lstrip("/").lower()


pytestmark = pytest.mark.skipif(
    not _safe_test_url(RUNTIME_URL),
    reason="Set TEST_RUNTIME_DATABASE_URL to a disposable database whose name contains 'test'",
)


def test_every_company_scoped_table_has_forced_rls_and_policy():
    # auth_sessions is intentionally pre-tenant: auth validates JWT subject + company + JTI
    # before tenant context is established. All other company_id tables must be RLS protected.
    intentional_pre_tenant_tables = {"auth_sessions"}
    # memberships stays ENABLEd with tenant/user policies but NO FORCE so its
    # SECURITY DEFINER director-check function can inspect membership rows.
    intentional_not_forced_tables = {"memberships"}
    with psycopg.connect(RUNTIME_URL) as conn:
        rows = conn.execute("""
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                   count(p.policyname) AS policy_count,
                   string_agg(coalesce(p.qual, '') || ' ' || coalesce(p.with_check, ''), ' ') AS policy_sql
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN information_schema.columns col
              ON col.table_schema = n.nspname AND col.table_name = c.relname
            LEFT JOIN pg_policies p
              ON p.schemaname = n.nspname AND p.tablename = c.relname
            WHERE n.nspname = current_schema()
              AND c.relkind = 'r'
              AND col.column_name = 'company_id'
            GROUP BY c.relname, c.relrowsecurity, c.relforcerowsecurity
            ORDER BY c.relname
        """).fetchall()

    failures = []
    discovered = {row[0] for row in rows}
    for table, enabled, forced, policy_count, policy_sql in rows:
        if table in intentional_pre_tenant_tables:
            continue
        if not enabled or (not forced and table not in intentional_not_forced_tables):
            failures.append(f"{table}: ENABLE/FORCE ROW LEVEL SECURITY is not active")
        if not policy_count:
            failures.append(f"{table}: no RLS policy exists")
        elif "app.tenant_id" not in (policy_sql or "") and table not in {"memberships"}:
            failures.append(f"{table}: no policy references app.tenant_id")

    if not discovered:
        failures.append("No company_id tables discovered; schema/migration setup is incomplete")
    assert not failures, "Tenant RLS coverage failures:\\n- " + "\\n- ".join(failures)
