from fastapi import APIRouter, Depends
from app.permissions import require_director
from app.models import Membership

router = APIRouter(prefix="/api/v1/admin", tags=["Администрирование"])

@router.get("/access-check")
def director_access_check(membership: Membership = Depends(require_director())):
    return {"allowed": True, "company_id": str(membership.company_id)}
