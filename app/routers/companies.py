from fastapi import APIRouter, Depends
from app.dependencies import get_current_membership
from app.models import Membership
from app.schemas import CompanyResponse

router = APIRouter(prefix="/api/v1/companies", tags=["Компании"])

@router.get("/current", response_model=CompanyResponse)
def current_company(membership: Membership = Depends(get_current_membership)):
    return membership.company
