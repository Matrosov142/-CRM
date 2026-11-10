"""Tenant-scoped operational counts for the company dashboard."""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_membership
from app.models import ApprovalRequest, Membership, ProcurementOrder, StockReservation, Tender
from app.permissions import Role, require_roles
from app.tenant_context import set_tenant_context

router = APIRouter(prefix="/api/v1/dashboard", tags=["Панель компании"])
READ_ROLES = (
    Role.DIRECTOR,
    Role.TENDER_SPECIALIST,
    Role.PROCUREMENT_MANAGER,
    Role.WAREHOUSE,
    Role.LOGISTICS,
    Role.ACCOUNTING,
)


def _count(db: Session, model, company_id, *conditions) -> int:
    value = db.query(func.count(model.id)).filter(
        model.company_id == company_id, *conditions
    ).scalar()
    return int(value or 0)


@router.get("/summary")
def dashboard_summary(
    actor: Membership = Depends(require_roles(*READ_ROLES)),
    db: Session = Depends(get_db),
):
    """Return counts based on explicit lifecycle states, never demo values."""
    set_tenant_context(db, actor.user_id, actor.company_id)
    return {
        "open_tenders": _count(
            db, Tender, actor.company_id,
            Tender.status.in_(("new", "analysis", "preparing", "submitted")),
        ),
        "authorized_procurement_orders": _count(
            db, ProcurementOrder, actor.company_id,
            ProcurementOrder.status == "authorized",
        ),
        "pending_approvals": _count(
            db, ApprovalRequest, actor.company_id,
            ApprovalRequest.status == "pending",
        ),
        "active_reservations": _count(
            db, StockReservation, actor.company_id,
            StockReservation.status == "active",
        ),
    }
