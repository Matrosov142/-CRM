"""Append-only audit event writer. Call inside the business transaction."""
from uuid import UUID
from sqlalchemy.orm import Session
from app.models import AuditEvent

def record_audit(
    db: Session, *, company_id: UUID, actor_user_id: UUID,
    action: str, entity_type: str, entity_id: str | None = None,
    outcome: str = "success", details: dict | None = None,
) -> AuditEvent:
    if outcome not in {"success", "denied", "failure"}:
        raise ValueError("Unsupported audit outcome")
    event = AuditEvent(
        company_id=company_id, actor_user_id=actor_user_id,
        action=action, entity_type=entity_type, entity_id=entity_id,
        outcome=outcome, details=details or {},
    )
    db.add(event)
    db.flush()
    return event
