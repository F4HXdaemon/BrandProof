from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.security import create_invite_token, decode_invite_token
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.schemas.auth_and_user import (
    OrganizationOut,
    OrganizationUpdate,
    UserOut,
    InviteCreateRequest,
    InviteResponse,
    InviteVerifyResponse,
)
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("/current", response_model=OrganizationOut)
def get_current_organization(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.put("/current", response_model=OrganizationOut)
def update_current_organization(
    update_data: OrganizationUpdate,
    current_user: User = Depends(require_roles([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if update_data.name is not None:
        org.name = update_data.name
    if update_data.domain is not None:
        org.domain = update_data.domain
    if update_data.is_active is not None:
        org.is_active = update_data.is_active

    db.commit()
    db.refresh(org)

    record_audit_event(
        db=db,
        organization_id=org.id,
        actor_id=current_user.id,
        action="ORGANIZATION_UPDATED",
        entity_type="Organization",
        entity_id=org.id,
        metadata={"name": org.name}
    )

    return org


@router.get("/current/members", response_model=List[UserOut])
def get_organization_members(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    users = db.query(User).filter(User.organization_id == current_user.organization_id).all()
    return [UserOut.model_validate(u) for u in users]


@router.post("/current/invites", response_model=InviteResponse)
def create_organization_invite(
    payload: InviteCreateRequest,
    current_user: User = Depends(require_roles([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Generate a cryptographically signed invitation token for this organization.
    Only Organization Admins can generate invitations.
    """
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    invite_token = create_invite_token(
        organization_id=org.id,
        organization_name=org.name,
        email=payload.email,
        expires_in_days=payload.expires_in_days or 7,
    )

    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=payload.expires_in_days or 7)).isoformat()

    record_audit_event(
        db=db,
        organization_id=org.id,
        actor_id=current_user.id,
        action="ORGANIZATION_INVITE_CREATED",
        entity_type="Organization",
        entity_id=org.id,
        metadata={"email": payload.email, "expires_in_days": payload.expires_in_days}
    )

    return InviteResponse(
        invite_token=invite_token,
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        email=payload.email,
        expires_at=expires_at,
    )


@router.get("/invites/verify", response_model=InviteVerifyResponse)
def verify_invite_token(
    token: str = Query(..., description="Cryptographic invitation token"),
    db: Session = Depends(get_db)
):
    """
    Public endpoint to verify an invitation token prior to registration.
    Allows prospective users to confirm the organization name and validity.
    """
    payload, error_reason = decode_invite_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_reason or "Invalid or expired invitation token."
        )

    org_id = payload.get("org_id")
    org = db.query(Organization).filter(Organization.id == org_id, Organization.is_active.is_(True)).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The organization associated with this invite does not exist or has been deactivated."
        )

    return InviteVerifyResponse(
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        email=payload.get("email"),
        valid=True,
    )

