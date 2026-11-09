from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import Company, User, Membership, AuthSession
from app.schemas import RegisterCompanyRequest, LoginRequest, TokenResponse
from app.security import hash_password, verify_password, create_access_token
from app.tenant_context import set_user_context, set_tenant_context
from app.login_throttle import enforce_login_throttle, record_login_failure, prune_old_login_failures
import secrets
import uuid
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/api/v1/auth", tags=["Авторизация"])

def _create_company_with_director(db: Session, company_name: str, email: str, password: str):
    company_id = uuid.uuid4()
    user = User(email=email, password_hash=hash_password(password))
    try:
        db.add(user)
        db.flush()
        # The INSERT-only bootstrap policy is limited to this selected company id
        # and transaction. It does not grant company reads or updates.
        db.execute(text("SELECT set_config('app.bootstrap_registration', 'on', true)"))
        db.execute(text("SELECT set_config('app.bootstrap_company_id', :company_id, true)"),
                   {"company_id": str(company_id)})
        set_user_context(db, user.id)
        company = Company(id=company_id, name=company_name.strip())
        db.add(company)
        db.flush()
        membership = Membership(company_id=company.id, user_id=user.id, role="director")
        db.add(membership)
        db.commit()
        return user, company, membership
    except Exception:
        db.rollback()
        raise


@router.post("/register-company", response_model=TokenResponse, status_code=201)
def register_company(payload: RegisterCompanyRequest, db: Session = Depends(get_db)):
    if not settings.allow_bootstrap_registration:
        raise HTTPException(status_code=404, detail="Регистрация временно недоступна")
    email = str(payload.email).lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Пользователь уже существует")
    user, company, _ = _create_company_with_director(db, payload.company_name, email, payload.password)
    return TokenResponse(access_token=create_access_token(str(user.id), str(company.id), "director"),
                         company_id=company.id, role="director")

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    email_hash, ip_hash = enforce_login_throttle(db, request, email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        record_login_failure(db, email_hash, ip_hash)
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    # Membership RLS permits a user to discover only their own company memberships.
    set_user_context(db, user.id)
    query = db.query(Membership).filter(Membership.user_id == user.id, Membership.status == "active")
    if payload.company_id:
        query = query.filter(Membership.company_id == payload.company_id)
    memberships = query.all()
    if not memberships:
        raise HTTPException(status_code=403, detail="Нет активного доступа к компании")
    if len(memberships) > 1 and payload.company_id is None:
        raise HTTPException(status_code=409, detail="Укажите компанию для входа")
    membership = memberships[0]
    set_tenant_context(db, user.id, membership.company_id)
    return TokenResponse(access_token=create_access_token(str(user.id), str(membership.company_id), membership.role),
                         company_id=membership.company_id, role=membership.role)


# Cookie-based browser session endpoints. Legacy bearer endpoints remain for API clients.
SESSION_COOKIE = "potok_session"
CSRF_COOKIE = "potok_csrf"

def _validate_browser_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin or origin not in settings.allowed_origins:
        raise HTTPException(status_code=403, detail="Недопустимый источник запроса")


def _set_browser_session(response: Response, token: str) -> None:
    csrf = secrets.token_urlsafe(32)
    secure = settings.environment != "development"
    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=secure, samesite="strict",
                        max_age=settings.access_token_minutes * 60, path="/",)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, secure=secure, samesite="strict",
                        max_age=settings.access_token_minutes * 60, path="/",)

def _create_browser_session(db: Session, user_id, company_id, role: str, user_agent: str | None = None) -> str:
    jti = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.access_token_minutes)
    token = create_access_token(str(user_id), str(company_id), role, jti=jti)
    db.add(AuthSession(jti=jti, user_id=user_id, company_id=company_id, created_at=now, expires_at=expires, user_agent=(user_agent or "")[:500] or None))
    db.commit()
    return token

def _revoke_browser_token(db: Session, token: str | None) -> None:
    if not token:
        return
    from app.security import decode_access_token
    try:
        claims = decode_access_token(token)
        jti = claims.get("jti")
    except Exception:
        jti = None
    if jti:
        session = db.query(AuthSession).filter(AuthSession.jti == jti, AuthSession.revoked_at.is_(None)).first()
        if session:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()

def _clear_browser_session(response: Response) -> None:
    secure = settings.environment != "development"
    response.delete_cookie(SESSION_COOKIE, path="/", secure=secure, httponly=True, samesite="strict")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=secure, httponly=False, samesite="strict")

@router.post("/session/login")
def session_login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    _validate_browser_origin(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    email = str(payload.email).strip().lower()
    email_hash, ip_hash = enforce_login_throttle(db, request, email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        record_login_failure(db, email_hash, ip_hash)
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    set_user_context(db, user.id)
    query = db.query(Membership).filter(Membership.user_id == user.id, Membership.status == "active")
    if payload.company_id:
        query = query.filter(Membership.company_id == payload.company_id)
    memberships = query.all()
    if not memberships:
        raise HTTPException(status_code=403, detail="Нет активного доступа к компании")
    if len(memberships) > 1 and payload.company_id is None:
        raise HTTPException(status_code=409, detail="Укажите компанию для входа")
    membership = memberships[0]
    set_tenant_context(db, user.id, membership.company_id)
    token = _create_browser_session(db, user.id, membership.company_id, membership.role, request.headers.get("user-agent"))
    _set_browser_session(response, token)
    return {"company_id": str(membership.company_id), "role": membership.role, "authenticated": True}

@router.post("/session/register-company", status_code=201)
def session_register_company(payload: RegisterCompanyRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    _validate_browser_origin(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    if not settings.allow_bootstrap_registration:
        raise HTTPException(status_code=404, detail="Регистрация временно недоступна")
    email = str(payload.email).lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Пользователь уже существует")
    user, company, _ = _create_company_with_director(db, payload.company_name, email, payload.password)
    set_tenant_context(db, user.id, company.id)
    _set_browser_session(response, _create_browser_session(db, user.id, company.id, "director", request.headers.get("user-agent")))
    return {"company_id": str(company.id), "role": "director", "authenticated": True}

@router.post("/session/logout")
def session_logout(response: Response, request: Request, db: Session = Depends(get_db)):
    # Logout is state-changing too; reject cross-site cookie logout attempts.
    if request is not None:
        csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
        csrf_header = request.headers.get("X-CSRF-Token", "")
        if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
            raise HTTPException(status_code=403, detail="Проверка CSRF не пройдена")
        _validate_browser_origin(request)
    _revoke_browser_token(db, request.cookies.get(SESSION_COOKIE))
    _clear_browser_session(response)
    return {"authenticated": False}


@router.post("/session/logout-all")
def session_logout_all(response: Response, request: Request, db: Session = Depends(get_db)):
    _validate_browser_origin(request)
    csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
    csrf_header = request.headers.get("X-CSRF-Token", "")
    if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail="Проверка CSRF не пройдена")
    from app.security import decode_access_token
    token = request.cookies.get(SESSION_COOKIE, "")
    try:
        claims = decode_access_token(token)
        user_id = claims["sub"]
        jti = claims["jti"]
    except Exception:
        _clear_browser_session(response)
        raise HTTPException(status_code=401, detail="Недействительная сессия")
    now = datetime.now(timezone.utc)
    current = db.query(AuthSession).filter(
        AuthSession.jti == jti, AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None), AuthSession.expires_at > now
    ).first()
    if current is None:
        _clear_browser_session(response)
        raise HTTPException(status_code=401, detail="Сессия завершена или отозвана")
    count = db.query(AuthSession).filter(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)).update({AuthSession.revoked_at: now}, synchronize_session=False)
    db.commit()
    _clear_browser_session(response)
    return {"revoked_sessions": count, "authenticated": False}


@router.get("/session/sessions")
def list_browser_sessions(request: Request, db: Session = Depends(get_db)):
    """List only the authenticated user's browser sessions; never expose tokens."""
    from app.security import decode_access_token
    token = request.cookies.get(SESSION_COOKIE, "")
    try:
        claims = decode_access_token(token)
        user_id, current_jti = claims["sub"], claims["jti"]
    except Exception:
        raise HTTPException(status_code=401, detail="Требуется действующая браузерная сессия")
    now = datetime.now(timezone.utc)
    current = db.query(AuthSession).filter(
        AuthSession.jti == current_jti, AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None), AuthSession.expires_at > now
    ).first()
    if current is None:
        raise HTTPException(status_code=401, detail="Сессия завершена или отозвана")
    rows = db.query(AuthSession).filter(
        AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None), AuthSession.expires_at > now
    ).order_by(AuthSession.created_at.desc()).limit(100).all()
    def device_label(ua: str | None) -> str:
        value = (ua or "").lower()
        if "iphone" in value: return "iPhone"
        if "ipad" in value: return "iPad"
        if "android" in value: return "Android"
        if "windows" in value: return "Windows"
        if "macintosh" in value or "mac os" in value: return "macOS"
        if "linux" in value: return "Linux"
        return "Неизвестное устройство"
    return {"sessions": [{
        "id": str(row.id), "device": device_label(row.user_agent),
        "user_agent": (row.user_agent or "")[:180],
        "created_at": row.created_at.isoformat(), "expires_at": row.expires_at.isoformat(),
        "current": row.jti == current_jti,
    } for row in rows]}


@router.delete("/session/sessions/{session_id}")
def revoke_browser_session(session_id: str, request: Request, response: Response, db: Session = Depends(get_db)):
    """Revoke one session owned by the current user, identified by opaque DB UUID."""
    _validate_browser_origin(request)
    csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
    csrf_header = request.headers.get("X-CSRF-Token", "")
    if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail="Проверка CSRF не пройдена")
    from app.security import decode_access_token
    try:
        claims = decode_access_token(request.cookies.get(SESSION_COOKIE, ""))
        user_id, current_jti = claims["sub"], claims["jti"]
    except Exception:
        raise HTTPException(status_code=401, detail="Недействительная сессия")
    now = datetime.now(timezone.utc)
    current = db.query(AuthSession).filter(
        AuthSession.jti == current_jti, AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None), AuthSession.expires_at > now
    ).first()
    if current is None:
        raise HTTPException(status_code=401, detail="Сессия завершена или отозвана")
    target = db.query(AuthSession).filter(
        AuthSession.id == session_id, AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None), AuthSession.expires_at > now
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Активный сеанс не найден")
    target.revoked_at = now
    db.commit()
    if target.jti == current_jti:
        _clear_browser_session(response)
    return {"revoked": True, "current_session": target.jti == current_jti}
