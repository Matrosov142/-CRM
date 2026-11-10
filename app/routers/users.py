from fastapi import APIRouter, Depends
from app.dependencies import get_current_membership
from app.models import Membership

router = APIRouter(prefix="/api/v1/users", tags=["Пользователи"])

@router.get("/me")
def current_user(membership: Membership = Depends(get_current_membership)):
    return {"id": str(membership.user_id), "email": membership.user.email,
            "company_id": str(membership.company_id), "role": membership.role}
