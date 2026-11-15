from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.schemas.auth_and_user import OrganizationOut, OrganizationUpdate, UserOut
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
