"""Server-side role checks. UI visibility is never an authorization boundary."""
from enum import StrEnum
from fastapi import Depends, HTTPException

class Role(StrEnum):
    DIRECTOR = "director"
    TENDER_SPECIALIST = "tender_specialist"
    PROCUREMENT_MANAGER = "procurement_manager"
    WAREHOUSE = "warehouse"
    LOGISTICS = "logistics"
    ACCOUNTING = "accounting"

def require_roles(*allowed: Role):
    from app.dependencies import get_current_membership
    allowed_values = {role.value for role in allowed}
    def dependency(membership = Depends(get_current_membership)):
        if membership.role not in allowed_values:
            raise HTTPException(status_code=403, detail="Недостаточно прав для выполнения действия")
        return membership
    return dependency

def require_director():
    from app.dependencies import get_current_membership
    def dependency(membership = Depends(get_current_membership)):
        if membership.role != Role.DIRECTOR.value:
            raise HTTPException(status_code=403, detail="Требуется подтверждение директора")
        return membership
    return dependency
