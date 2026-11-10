from pathlib import Path


def test_director_membership_migration_is_tenant_scoped_and_not_publicly_mutating():
    migration = Path(__file__).resolve().parents[1] / "migrations/versions/0006_director_membership_management.py"
    source = migration.read_text(encoding="utf-8")
    assert "SECURITY DEFINER" in source
    assert "app_is_company_director(company_id)" in source
    assert "app.tenant_id" in source
    assert "app.user_id" in source
    assert "ALTER TABLE memberships NO FORCE ROW LEVEL SECURITY" in source


def test_staff_api_exposes_director_management_operations():
    router = Path(__file__).resolve().parents[1] / "app/routers/employees.py"
    source = router.read_text(encoding="utf-8")
    assert '@router.get("", response_model=list[EmployeeResponse])' in source
    assert '@router.patch("/{membership_id}/role")' in source
    assert '@router.post("/{membership_id}/revoke")' in source
    assert 'Нельзя отозвать доступ последнего директора' in source


def test_employee_listing_exposes_membership_id_for_membership_scoped_controls():
    root = Path(__file__).resolve().parents[1]
    schema = (root / "app/schemas.py").read_text(encoding="utf-8")
    router = (root / "app/routers/employees.py").read_text(encoding="utf-8")
    assert "membership_id: UUID" in schema
    assert "membership_id=member.id" in router
