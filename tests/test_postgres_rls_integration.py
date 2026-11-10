"""PostgreSQL RLS tests. Run only against disposable databases whose names contain 'test'."""
import os
from urllib.parse import urlparse
from uuid import uuid4

import pytest

psycopg = pytest.importorskip(
    "psycopg",
    reason="Install project requirements to run PostgreSQL integration tests",
)
from psycopg.errors import InsufficientPrivilege, RaiseException, CheckViolation

ADMIN_URL = os.getenv("TEST_ADMIN_DATABASE_URL")
RUNTIME_URL = os.getenv("TEST_RUNTIME_DATABASE_URL")


def _safe_test_url(url):
    return bool(url) and "test" in urlparse(url).path.lstrip("/").lower()


pytestmark = [
    pytest.mark.postgres_rls,
    pytest.mark.skipif(
        not (_safe_test_url(ADMIN_URL) and _safe_test_url(RUNTIME_URL)),
        reason="Set TEST_ADMIN_DATABASE_URL and TEST_RUNTIME_DATABASE_URL to disposable *test* databases",
    ),
]


def test_runtime_role_is_least_privileged():
    with psycopg.connect(RUNTIME_URL) as conn:
        superuser, bypassrls = conn.execute("""
            SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user
        """).fetchone()
        assert superuser is False
        assert bypassrls is False
        owner_superuser, owner_bypassrls = conn.execute("""
            SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname='potok_owner'
        """).fetchone()
        assert owner_superuser is False
        assert owner_bypassrls is False
        owned = conn.execute("""
            SELECT c.relname FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=current_schema()
              AND c.relname IN ('companies','memberships','audit_events')
              AND c.relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)
        """).fetchall()
        assert owned == []
        owner_owned = conn.execute("""
            SELECT count(*) FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=current_schema() AND c.relkind='r'
              AND c.relowner=(SELECT oid FROM pg_roles WHERE rolname='potok_owner')
        """).fetchone()[0]
        assert owner_owned > 0
        can_update = conn.execute(
            "SELECT has_table_privilege(current_user, 'audit_events', 'UPDATE')"
        ).fetchone()[0]
        can_delete = conn.execute(
            "SELECT has_table_privilege(current_user, 'audit_events', 'DELETE')"
        ).fetchone()[0]
        assert can_update is False
        assert can_delete is False


def test_rls_isolates_tenants_and_audit_is_append_only():
    company_a, company_b = uuid4(), uuid4()
    user_a, user_b = uuid4(), uuid4()
    member_a, member_b = uuid4(), uuid4()
    audit_a, audit_b = uuid4(), uuid4()

    # Fixture creation and cleanup use the disposable admin connection.
    with psycopg.connect(ADMIN_URL) as admin:
        admin.execute(
            "INSERT INTO companies(id,name,status) VALUES (%s,%s,'active'),(%s,%s,'active')",
            (company_a, "RLS test A", company_b, "RLS test B"),
        )
        admin.execute(
            """INSERT INTO users(id,email,password_hash,is_active)
               VALUES (%s,%s,'test-hash',true),(%s,%s,'test-hash',true)""",
            (user_a, f"{user_a}@example.invalid", user_b, f"{user_b}@example.invalid"),
        )
        admin.execute(
            """INSERT INTO memberships(id,company_id,user_id,role,status)
               VALUES (%s,%s,%s,'director','active'),(%s,%s,%s,'director','active')""",
            (member_a, company_a, user_a, member_b, company_b, user_b),
        )
        admin.execute(
            """INSERT INTO audit_events
               (id,company_id,actor_user_id,action,entity_type,outcome,details)
               VALUES (%s,%s,%s,'fixture.created','test','success','{}'::jsonb),
                      (%s,%s,%s,'fixture.created','test','success','{}'::jsonb)""",
            (audit_a, company_a, user_a, audit_b, company_b, user_b),
        )

    try:
        with psycopg.connect(RUNTIME_URL) as runtime:
            runtime.execute(
                "SELECT set_config('app.user_id', %s, true)", (str(user_a),)
            )
            visible_memberships = runtime.execute(
                "SELECT company_id FROM memberships ORDER BY company_id"
            ).fetchall()
            assert visible_memberships == [(company_a,)]

            runtime.execute(
                "SELECT set_config('app.tenant_id', %s, true)", (str(company_a),)
            )
            assert runtime.execute("SELECT id FROM companies").fetchall() == [(company_a,)]
            visible_audit = runtime.execute(
                "SELECT id, company_id FROM audit_events"
            ).fetchall()
            assert visible_audit == [(audit_a, company_a)]

        # Tenant A may append an event for A, but may not write into tenant B.
        allowed_id = uuid4()
        with psycopg.connect(RUNTIME_URL) as runtime:
            runtime.execute(
                "SELECT set_config('app.user_id', %s, true)", (str(user_a),)
            )
            runtime.execute(
                "SELECT set_config('app.tenant_id', %s, true)", (str(company_a),)
            )
            runtime.execute(
                """INSERT INTO audit_events
                   (id,company_id,actor_user_id,action,entity_type,outcome,details)
                   VALUES (%s,%s,%s,'test.allowed','test','success','{}'::jsonb)""",
                (allowed_id, company_a, user_a),
            )

        with psycopg.connect(RUNTIME_URL) as runtime:
            runtime.execute(
                "SELECT set_config('app.user_id', %s, true)", (str(user_a),)
            )
            runtime.execute(
                "SELECT set_config('app.tenant_id', %s, true)", (str(company_a),)
            )
            with pytest.raises((InsufficientPrivilege, CheckViolation)):
                runtime.execute(
                    """INSERT INTO audit_events
                       (id,company_id,actor_user_id,action,entity_type,outcome,details)
                       VALUES (%s,%s,%s,'test.denied','test','success','{}'::jsonb)""",
                    (uuid4(), company_b, user_a),
                )

        # The runtime role has no UPDATE/DELETE grants; database trigger is a second barrier.
        with psycopg.connect(RUNTIME_URL) as runtime:
            assert runtime.execute(
                "SELECT has_table_privilege(current_user, 'audit_events', 'UPDATE')"
            ).fetchone()[0] is False
            assert runtime.execute(
                "SELECT has_table_privilege(current_user, 'audit_events', 'DELETE')"
            ).fetchone()[0] is False

    finally:
        # Fixtures intentionally remain in this disposable database: audit_events
        # are append-only, so cleanup must not attempt to delete their records.
        pass
