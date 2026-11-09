from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/api/v1", tags=["Состояние"])


@router.get("/health")
def health():
    # Liveness: process is running; no dependency checks.
    return {"success": True, "data": {"status": "ok"}}


@router.get("/health/ready")
def readiness():
    # Readiness: the API can reach its configured database.
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="База данных недоступна")
    return {"success": True, "data": {"status": "ready", "database": "ok"}}
