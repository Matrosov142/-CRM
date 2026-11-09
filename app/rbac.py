"""Central permission matrix. Unknown role/action combinations are denied."""
from enum import StrEnum
from fastapi import Depends, HTTPException

class Action(StrEnum):
    TENDERS_VIEW = "tenders.view"
    TENDERS_EDIT = "tenders.edit"
    TENDERS_APPROVE = "tenders.approve"
    PROCUREMENT_VIEW = "procurement.view"
    PROCUREMENT_EDIT = "procurement.edit"
    PROCUREMENT_APPROVE = "procurement.approve"
    WAREHOUSE_VIEW = "warehouse.view"
    WAREHOUSE_RECEIVE = "warehouse.receive"
    WAREHOUSE_WRITE_OFF = "warehouse.write_off"
    LOGISTICS_VIEW = "logistics.view"
    SHIPMENTS_EDIT = "shipments.edit"
    FINANCE_VIEW = "finance.view"
    PAYMENTS_APPROVE = "payments.approve"
    STAFF_MANAGE = "staff.manage"
    AUDIT_VIEW = "audit.view"

# Explicit grants only; anything not listed is denied.
ROLE_PERMISSIONS = {
    "director": set(Action),
    "tender_specialist": {
        Action.TENDERS_VIEW, Action.TENDERS_EDIT,
        Action.PROCUREMENT_VIEW, Action.LOGISTICS_VIEW,
    },
    "procurement_manager": {
        Action.TENDERS_VIEW, Action.PROCUREMENT_VIEW, Action.PROCUREMENT_EDIT,
        Action.WAREHOUSE_VIEW, Action.LOGISTICS_VIEW,
    },
    "warehouse": {
        Action.WAREHOUSE_VIEW, Action.WAREHOUSE_RECEIVE,
    },
    "logistics": {
        Action.LOGISTICS_VIEW, Action.SHIPMENTS_EDIT, Action.WAREHOUSE_VIEW,
    },
    "accounting": {
        Action.FINANCE_VIEW, Action.PAYMENTS_APPROVE,
        Action.PROCUREMENT_VIEW, Action.TENDERS_VIEW, Action.AUDIT_VIEW,
    },
}

def has_permission(role: str, action: Action | str) -> bool:
    try:
        normalized = Action(action)
    except ValueError:
        return False
    return normalized in ROLE_PERMISSIONS.get(role, set())

def require_permission(action: Action):
    """Resolve role permission plus tenant-scoped per-employee override."""
    from app.dependencies import get_current_membership
    from app.database import get_db
    from app.models import EmployeePermissionOverride
    from sqlalchemy.orm import Session

    def dependency(
        membership = Depends(get_current_membership),
        db: Session = Depends(get_db),
    ):
        override_row = db.query(EmployeePermissionOverride).filter(
            EmployeePermissionOverride.company_id == membership.company_id,
            EmployeePermissionOverride.membership_id == membership.id,
            EmployeePermissionOverride.action == action.value,
        ).first()
        override = None if override_row is None else override_row.allowed
        if not effective_permission(membership.role, action, override):
            raise HTTPException(status_code=403, detail="Недостаточно прав для выполнения действия")
        return membership
    return dependency


def effective_permission(role: str, action: Action | str, override: bool | None = None) -> bool:
    """An explicit director override wins; otherwise use role matrix (deny by default)."""
    if override is not None:
        return bool(override)
    return has_permission(role, action)
