from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import hash_password
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.organization import OrganizationMembership, MembershipStatus
from app.schemas.auth_and_user import UserCreate, UserUpdate, UserOut, OnboardingUpdatePayload
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=List[UserOut])
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all users who are members of the current active organization."""
    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == current_user.organization_id,
        OrganizationMembership.status == MembershipStatus.ACTIVE.value
    ).all()

    results = []
    for m in memberships:
        u = m.user
        u_out = UserOut.model_validate(u)
        u_out.role = m.role
        u_out.organization_id = m.organization_id
        results.append(u_out)
    return results


@router.patch("/me/onboarding", response_model=UserOut)
def update_my_onboarding(
    payload: OnboardingUpdatePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update onboarding tour completion state for the currently authenticated user."""
    current_user.onboarding_completed = payload.onboarding_completed
    db.commit()
    db.refresh(current_user)

    out = UserOut.model_validate(current_user)
    out.role = current_user.role
    out.organization_id = current_user.organization_id
    return out


@router.post("", response_model=UserOut)
def create_user(
    user_in: UserCreate,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OWNER])),
    db: Session = Depends(get_db)
):
    """Directly provision a user into the current organization (Admin or Owner only)."""
    existing = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    assigned_role = user_in.role.value if isinstance(user_in.role, UserRole) else str(user_in.role)
    new_user = User(
        organization_id=current_user.organization_id,
        email=user_in.email.lower(),
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        role=assigned_role,
        title=user_in.title,
        avatar_url=user_in.avatar_url,
        is_active=user_in.is_active,
    )
    db.add(new_user)
    db.flush()

    membership = OrganizationMembership(
        user_id=new_user.id,
        organization_id=current_user.organization_id,
        role=assigned_role,
        status=MembershipStatus.ACTIVE.value,
        joined_at=datetime.now(timezone.utc),
        invited_by_id=current_user.id,
    )
    db.add(membership)
    db.commit()
    db.refresh(new_user)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="USER_CREATED",
        entity_type="User",
        entity_id=new_user.id,
        metadata={"email": new_user.email, "role": assigned_role}
    )

    out = UserOut.model_validate(new_user)
    out.role = assigned_role
    out.organization_id = current_user.organization_id
    return out


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve profile of a user within the current organization."""
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.organization_id == current_user.organization_id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="User not found in current organization")

    user = membership.user
    out = UserOut.model_validate(user)
    out.role = membership.role
    out.organization_id = membership.organization_id
    return out


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update profile or organization role for a user."""
    is_admin = current_user.role in (UserRole.ADMIN.value, UserRole.OWNER.value)
    if not is_admin and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this profile")

    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.organization_id == current_user.organization_id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="User not found in current organization")

    user = membership.user

    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.title is not None:
        user.title = user_in.title
    if user_in.avatar_url is not None:
        user.avatar_url = user_in.avatar_url
    if user_in.role is not None and is_admin:
        assigned_role = user_in.role.value if isinstance(user_in.role, UserRole) else str(user_in.role)
        membership.role = assigned_role
        user.role = assigned_role
    if user_in.is_active is not None and is_admin:
        user.is_active = user_in.is_active

    db.commit()
    db.refresh(user)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="USER_UPDATED",
        entity_type="User",
        entity_id=user.id,
        metadata={"email": user.email, "role": membership.role}
    )

    out = UserOut.model_validate(user)
    out.role = membership.role
    out.organization_id = membership.organization_id
    return out
