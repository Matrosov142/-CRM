from datetime import datetime, timedelta, timezone
import secrets
import jwt
from app.config import settings

def _password_hasher():
    from pwdlib import PasswordHash
    return PasswordHash.recommended()

def hash_password(password: str) -> str:
    return _password_hasher().hash(password)

def verify_password(password: str, hashed: str) -> bool:
    try:
        return _password_hasher().verify(password, hashed)
    except Exception:
        return False

def create_access_token(user_id: str, company_id: str, role: str, *, jti: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    claims = {"sub": user_id, "company_id": company_id, "role": role,
              "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes),
              "type": "access"}
    if jti is not None:
        claims["jti"] = jti
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
                      options={"require": ["exp", "iat", "sub"]})
