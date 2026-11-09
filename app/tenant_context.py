"""Transaction-local PostgreSQL session context for RLS policies."""
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.orm import Session

def set_user_context(db: Session, user_id: UUID) -> None:
    # SET LOCAL semantics: set_config(..., true) is scoped to current transaction.
    db.execute(text("SELECT set_config('app.user_id', :user_id, true)"),
               {"user_id": str(user_id)})

def set_tenant_context(db: Session, user_id: UUID, company_id: UUID) -> None:
    set_user_context(db, user_id)
    db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
               {"tenant_id": str(company_id)})
