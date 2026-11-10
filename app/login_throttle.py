"""Persistent, privacy-preserving login failure throttling.

Only keyed digests of normalized identifiers are stored; raw email and IP are not.
The table is global/pre-tenant because it protects unauthenticated login requests.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.models import LoginFailure

WINDOW_MINUTES = 15
MAX_FAILURES_PER_EMAIL = 8
MAX_FAILURES_PER_IP = 30


def _digest(value: str) -> str:
    key = settings.jwt_secret.encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _client_ip(request: Request) -> str:
    # Do not trust X-Forwarded-For unless a trusted-proxy policy is configured.
    return request.client.host if request.client else "unknown"


def enforce_login_throttle(db: Session, request: Request, email: str) -> tuple[str, str]:
    email_hash = _digest("email:" + email.strip().lower())
    ip_hash = _digest("ip:" + _client_ip(request))
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)
    email_count = db.query(LoginFailure).filter(
        LoginFailure.email_hash == email_hash,
        LoginFailure.attempted_at >= cutoff,
    ).count()
    ip_count = db.query(LoginFailure).filter(
        LoginFailure.ip_hash == ip_hash,
        LoginFailure.attempted_at >= cutoff,
    ).count()
    if email_count >= MAX_FAILURES_PER_EMAIL or ip_count >= MAX_FAILURES_PER_IP:
        raise HTTPException(
            status_code=429,
            detail="Слишком много неудачных попыток входа. Повторите попытку позже.",
            headers={"Retry-After": str(WINDOW_MINUTES * 60)},
        )
    return email_hash, ip_hash


def record_login_failure(db: Session, email_hash: str, ip_hash: str) -> None:
    db.add(LoginFailure(
        email_hash=email_hash,
        ip_hash=ip_hash,
        attempted_at=datetime.now(timezone.utc),
    ))
    db.commit()


def prune_old_login_failures(db: Session, *, now: datetime | None = None) -> int:
    """Bound table growth; called opportunistically, never on every request."""
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(days=2)
    return db.query(LoginFailure).filter(LoginFailure.attempted_at < cutoff).delete(synchronize_session=False)
