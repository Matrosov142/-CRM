"""Employee invitations and staff access management."""
from datetime import datetime, timedelta, timezone
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.database import get_db
from app.models import EmployeeInvitation, Membership, User
from app.permissions import require_director
from app.schemas import (
    EmployeeInviteRequest, EmployeeInviteResponse,
    AcceptEmployeeInviteRequest, EmployeeResponse, EmployeeRoleUpdateRequest,
)
from app.security import hash_password
from app.tenant_context import set_tenant_context
from app.invitation_security import ALLOWED_ROLES, INVITE_TTL_HOURS, token_hash

router = APIRouter(prefix="/api/v1/employees", tags=["Сотрудники"])

@router.post("/invitations", response_model=EmployeeInviteResponse, status_code=201)
def create_invitation(
    payload: EmployeeInviteRequest,
    membership: Membership = Depends(require_director()),
    db: Session = Depends(get_db),
):
    email = str(payload.email).lower()
    role = payload.role.strip()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=422, detail="Недопустимая роль сотрудника")
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        existing = db.query(Membership).filter(
            Membership.company_id == membership.company_id,
            Membership.user_id == existing_user.id,
        ).first()
        if existing and existing.status == "active":
            raise HTTPException(status_code=409, detail="Сотрудник уже имеет доступ к компании")
    now = datetime.now(timezone.utc)
    # Revoke any previous unaccepted invitation for the same address.
    old = db.query(EmployeeInvitation).filter(
        EmployeeInvitation.company_id == membership.company_id,
        EmployeeInvitation.email == email,
        EmployeeInvitation.accepted_at.is_(None),
        EmployeeInvitation.revoked_at.is_(None),
    ).all()
    for item in old:
        item.revoked_at = now
    raw_token = secrets.token_urlsafe(48)
    invitation = EmployeeInvitation(
        company_id=membership.company_id, email=email, role=role,
        token_hash=token_hash(raw_token), invited_by_user_id=membership.user_id,
        expires_at=now + timedelta(hours=INVITE_TTL_HOURS),
    )
    db.add(invitation)
    record_audit(
        db, company_id=membership.company_id, actor_user_id=membership.user_id,
        action="employee.invitation_created", entity_type="employee_invitation",
        entity_id=str(invitation.id), details={"email": email, "role": role},
    )
    db.commit()
    return EmployeeInviteResponse(
        id=invitation.id, email=email, role=role,
        expires_at=invitation.expires_at.isoformat(),
        invitation_token=raw_token,
    )


@router.post("/invitations/accept", status_code=201)
def accept_invitation(
    payload: AcceptEmployeeInviteRequest,
    db: Session = Depends(get_db),
):
    digest = token_hash(payload.invitation_token)
    # Token hash is installed as transaction-local RLS context; only the matching
    # invitation row is visible to this unauthenticated acceptance request.
    db.execute(
        text("SELECT set_config('app.invitation_token_hash', :digest, true)"),
        {"digest": digest},
    )
    invitation = db.query(EmployeeInvitation).filter(
        EmployeeInvitation.token_hash == digest
    ).with_for_update().first()
    now = datetime.now(timezone.utc)
    if (invitation is None or invitation.accepted_at is not None
            or invitation.revoked_at is not None or invitation.expires_at <= now):
        db.rollback()
        raise HTTPException(status_code=400, detail="Приглашение недействительно или истекло")
    # Switch to tenant context before touching tenant-protected records.
    set_tenant_context(db, invitation.invited_by_user_id, invitation.company_id)
    user = db.query(User).filter(User.email == invitation.email).with_for_update().first()
    if user is None:
        user = User(email=invitation.email, password_hash=hash_password(payload.password))
        db.add(user)
        db.flush()
    elif not user.is_active:
        db.rollback()
        raise HTTPException(status_code=403, detail="Учётная запись пользователя заблокирована")
    existing = db.query(Membership).filter(
        Membership.company_id == invitation.company_id,
        Membership.user_id == user.id,
    ).first()
    if existing and existing.status == "active":
        db.rollback()
        raise HTTPException(status_code=409, detail="Доступ к компании уже активен")
    if existing:
        existing.role = invitation.role
        existing.status = "active"
    else:
        db.add(Membership(
            company_id=invitation.company_id, user_id=user.id,
            role=invitation.role, status="active",
        ))
    invitation.accepted_at = now
    record_audit(
        db, company_id=invitation.company_id, actor_user_id=user.id,
        action="employee.invitation_accepted", entity_type="membership",
        details={"email": invitation.email, "role": invitation.role},
    )
    db.commit()
    return {"accepted": True, "company_id": str(invitation.company_id),
            "message": "Доступ к компании активирован. Теперь можно войти в систему."}




@router.get("", response_model=list[EmployeeResponse])
def list_employees(
    actor: Membership = Depends(require_director()),
    db: Session = Depends(get_db),
):
    rows = (db.query(Membership, User)
        .join(User, Membership.user_id == User.id)
        .filter(Membership.company_id == actor.company_id)
        .order_by(User.email)
        .all())
    return [
        EmployeeResponse(id=user.id, membership_id=member.id, email=user.email,
                         role=member.role, status=member.status)
        for member, user in rows
    ]


@router.patch("/{membership_id}/role")
def change_employee_role(
    membership_id: UUID,
    payload: EmployeeRoleUpdateRequest,
    actor: Membership = Depends(require_director()),
    db: Session = Depends(get_db),
):
    role = payload.role.strip()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=422, detail="Недопустимая роль сотрудника")
    target = db.query(Membership).filter(
        Membership.id == membership_id,
        Membership.company_id == actor.company_id,
        Membership.status == "active",
    ).with_for_update().first()
    if target is None:
        raise HTTPException(status_code=404, detail="Активный доступ сотрудника не найден")
    if target.user_id == actor.user_id:
        raise HTTPException(status_code=409, detail="Нельзя изменить собственную роль директора")
    if target.role == "director":
        raise HTTPException(status_code=409, detail="Нельзя изменить роль другого директора этим действием")
    previous_role = target.role
    target.role = role
    record_audit(
        db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="employee.role_changed", entity_type="membership",
        entity_id=str(target.id),
        details={"user_id": str(target.user_id), "previous_role": previous_role, "new_role": role},
    )
    db.commit()
    return {"updated": True, "membership_id": str(target.id), "role": role}


@router.post("/{membership_id}/revoke")
def revoke_employee_access(
    membership_id: UUID,
    actor: Membership = Depends(require_director()),
    db: Session = Depends(get_db),
):
    target = db.query(Membership).filter(
        Membership.id == membership_id,
        Membership.company_id == actor.company_id,
        Membership.status == "active",
    ).with_for_update().first()
    if target is None:
        raise HTTPException(status_code=404, detail="Активный доступ сотрудника не найден")
    if target.user_id == actor.user_id:
        raise HTTPException(status_code=409, detail="Нельзя отозвать собственный доступ директора")
    if target.role == "director":
        active_directors = db.query(Membership).filter(
            Membership.company_id == actor.company_id,
            Membership.role == "director",
            Membership.status == "active",
        ).count()
        if active_directors <= 1:
            raise HTTPException(status_code=409, detail="Нельзя отозвать доступ последнего директора")
    target.status = "revoked"
    record_audit(
        db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="employee.access_revoked", entity_type="membership",
        entity_id=str(target.id),
        details={"user_id": str(target.user_id), "previous_role": target.role},
    )
    db.commit()
    return {"revoked": True, "membership_id": str(target.id)}
