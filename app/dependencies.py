from fastapi import Depends, HTTPException, Request
from datetime import datetime, timezone
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt
from app.database import get_db
from app.models import User, Membership, AuthSession
from app.security import decode_access_token
from app.tenant_context import set_tenant_context
import hmac
from app.routers.auth import SESSION_COOKIE, CSRF_COOKIE
from app.config import settings

bearer = HTTPBearer(auto_error=False)

def get_current_membership(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                           db: Session = Depends(get_db)) -> Membership:
    cookie_token = request.cookies.get(SESSION_COOKIE)
    token = cookie_token or (credentials.credentials if credentials else None)
    if not token:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    if cookie_token and request.method not in ("GET", "HEAD", "OPTIONS"):
        csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
        csrf_header = request.headers.get("X-CSRF-Token", "")
        origin = request.headers.get("origin")
        if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
            raise HTTPException(status_code=403, detail="Проверка CSRF не пройдена")
        if not origin or origin not in settings.allowed_origins:
            raise HTTPException(status_code=403, detail="Недопустимый источник запроса")
    try:
        claims = decode_access_token(token)
        if claims.get("type") != "access":
            raise ValueError("Wrong token type")
        user_id, company_id = claims["sub"], claims["company_id"]
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Недействительный токен")
    if cookie_token:
        jti = None
        try:
            jti = decode_access_token(cookie_token).get("jti")
        except Exception:
            pass
        if not jti:
            raise HTTPException(status_code=401, detail="Сессия не зарегистрирована на сервере")
        active_session = db.query(AuthSession).filter(
            AuthSession.jti == jti, AuthSession.user_id == user_id, AuthSession.company_id == company_id,
            AuthSession.revoked_at.is_(None), AuthSession.expires_at > datetime.now(timezone.utc)
        ).first()
        if active_session is None:
            raise HTTPException(status_code=401, detail="Сессия завершена или отозвана")
    set_tenant_context(db, user_id, company_id)
    membership = (db.query(Membership).join(User, Membership.user_id == User.id)
        .filter(Membership.user_id == user_id, Membership.company_id == company_id,
                Membership.status == "active", User.is_active.is_(True)).first())
    if membership is None:
        raise HTTPException(status_code=403, detail="Нет активного доступа к компании")
    return membership
