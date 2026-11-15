from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import hash_password
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.schemas.auth_and_user import UserCreate, UserUpdate, UserOut
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=List[UserOut])
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    users = db.query(User).filter(User.organization_id == current_user.organization_id).all()
    return [UserOut.model_validate(u) for u in users]


@router.post("", response_model=UserOut)
def create_user(
    user_in: UserCreate,
    current_user: User = Depends(require_roles([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    new_user = User(
        organization_id=current_user.organization_id,
        email=user_in.email.lower(),
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role.value if isinstance(user_in.role, UserRole) else str(user_in.role),
        title=user_in.title,
        avatar_url=user_in.avatar_url,
        is_active=user_in.is_active,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="USER_CREATED",
        entity_type="User",
        entity_id=new_user.id,
        metadata={"email": new_user.email, "role": new_user.role}
    )

    return UserOut.model_validate(new_user)


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.id == user_id,
        User.organization_id == current_user.organization_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only Admin or user themselves can update
    if current_user.role != UserRole.ADMIN.value and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this profile")

    user = db.query(User).filter(
        User.id == user_id,
        User.organization_id == current_user.organization_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.title is not None:
        user.title = user_in.title
    if user_in.avatar_url is not None:
        user.avatar_url = user_in.avatar_url
    if user_in.role is not None and current_user.role == UserRole.ADMIN.value:
        user.role = user_in.role.value if isinstance(user_in.role, UserRole) else str(user_in.role)
    if user_in.is_active is not None and current_user.role == UserRole.ADMIN.value:
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
        metadata={"email": user.email, "role": user.role}
    )

    return UserOut.model_validate(user)
