"""Read-only ETP directory. Actual connectors are enabled only after verification."""
from fastapi import APIRouter, Depends, HTTPException
from app.etp.registry import get_platform, list_platforms
from app.dependencies import get_current_membership
from app.models import Membership
from app.permissions import Role, require_roles

router = APIRouter(prefix="/api/v1/etp", tags=["Электронные торговые площадки"])

@router.get("/platforms")
def platforms(actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.TENDER_SPECIALIST))):
    """List supported ETPs and verified integration capabilities for this tenant's staff."""
    return {"items": list_platforms(), "count": len(list_platforms()),
            "message": "Подключения пока не активированы. Ручной импорт остаётся доступным способом загрузки тендерных материалов."}

@router.get("/platforms/{code}")
def platform_detail(code: str, actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.TENDER_SPECIALIST))):
    item = get_platform(code)
    if item is None:
        raise HTTPException(status_code=404, detail="Электронная площадка не найдена")
    from dataclasses import asdict
    return asdict(item)

@router.post("/platforms/{code}/connect")
def connect_not_implemented(code: str, actor: Membership = Depends(require_roles(Role.DIRECTOR))):
    item = get_platform(code)
    if item is None:
        raise HTTPException(status_code=404, detail="Электронная площадка не найдена")
    raise HTTPException(status_code=409, detail="Подключение не включено: сначала необходимо проверить официальный API, условия площадки и пройти интеграционные испытания. Пароли от площадки не принимаются этим интерфейсом.")
