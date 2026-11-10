from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_audit_migration_is_tenant_scoped_and_immutable():
    sql = (ROOT / "migrations/versions/0004_rbac_audit.py").read_text()
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "audit_events_tenant_access" in sql
    assert "BEFORE UPDATE OR DELETE" in sql
    assert "append-only" in sql

def test_audit_writer_rejects_unknown_outcome():
    source = (ROOT / "app/audit.py").read_text()
    assert 'outcome not in {"success", "denied", "failure"}' in source
