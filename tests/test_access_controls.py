from app.rbac import Action, effective_permission, has_permission
from app.access_control import VALID_OPERATIONS


def test_role_permissions_default_to_deny():
    assert has_permission("warehouse", Action.WAREHOUSE_RECEIVE)
    assert not has_permission("warehouse", Action.PAYMENTS_APPROVE)
    assert not has_permission("unknown_role", Action.FINANCE_VIEW)
    assert not has_permission("warehouse", "unknown.action")


def test_explicit_permission_override_wins_over_role_matrix():
    assert effective_permission("warehouse", Action.FINANCE_VIEW) is False
    assert effective_permission("warehouse", Action.FINANCE_VIEW, True) is True
    assert effective_permission("procurement_manager", Action.PROCUREMENT_EDIT, False) is False
    assert effective_permission("procurement_manager", Action.PROCUREMENT_EDIT, None) is True


def test_only_declared_operation_limits_are_supported():
    assert VALID_OPERATIONS == {
        "purchase", "supplier_advance", "payment", "warehouse_write_off"
    }


def test_permission_dependency_uses_persisted_override():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "app/rbac.py").read_text()
    assert "EmployeePermissionOverride" in source
    assert "EmployeePermissionOverride.allowed" not in source  # row value is read per membership
    assert "effective_permission(membership.role, action, override)" in source


def test_operation_limit_audit_serializes_decimal_as_exact_json_string():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "app/routers/access.py").read_text(encoding="utf-8")
    assert '"limit_amount": str(payload.limit_amount)' in source
    assert '"amount": str(payload.amount)' in source
