from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_rls_migration_forces_rls_on_core_tables():
    sql = (ROOT / "migrations/versions/0003_tenant_rls.py").read_text()
    assert "ALTER TABLE memberships FORCE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE companies FORCE ROW LEVEL SECURITY" in sql
    assert "CREATE POLICY memberships_self_access" in sql
    assert "CREATE POLICY companies_member_access" in sql

def test_request_context_is_transaction_local():
    source = (ROOT / "app/tenant_context.py").read_text()
    assert "set_config('app.user_id', :user_id, true)" in source
    assert "set_config('app.tenant_id', :tenant_id, true)" in source

def test_runtime_role_warning_is_documented():
    doc = (ROOT / "docs/V06_RLS_SECURITY.md").read_text()
    assert "BYPASSRLS" in doc
    assert "не является владельцем таблиц" in doc
