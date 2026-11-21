import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    decode_invite_token,
    hash_invitation_token,
)
from app.core.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.organization import (
    Organization,
    OrganizationMembership,
    OrganizationInvitation,
    MembershipStatus,
    InvitationStatus,
)
from app.schemas.auth_and_user import LoginRequest, TokenResponse, RegisterRequest, UserOut
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RateLimiter:
    """
    Sliding window rate limiter for authentication brute-force protection.
    Tracks failed attempts by client IP and account email.
    """
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)
        self.lock = Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self.lock:
            self.attempts[key] = [t for t in self.attempts[key] if now - t < self.window_seconds]
            if len(self.attempts[key]) >= self.max_attempts:
                oldest = self.attempts[key][0]
                retry_after = int(self.window_seconds - (now - oldest)) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many attempts. Please try again in {retry_after} seconds.",
                    headers={"Retry-After": str(max(retry_after, 1))},
                )

    def record_failure(self, key: str) -> None:
        with self.lock:
            self.attempts[key].append(time.time())

    def reset(self, key: str) -> None:
        with self.lock:
            if key in self.attempts:
                del self.attempts[key]


login_limiter = RateLimiter(max_attempts=5, window_seconds=300)
register_limiter = RateLimiter(max_attempts=15, window_seconds=300)


def _slugify(text: str) -> str:
    """Generate a clean URL-safe slug from text."""
    slug = re.sub(r"[^\w\s-]", "", text.strip().lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug or "org"


def _set_auth_cookie(response: Response, token: str) -> None:
    """Set secure authentication cookie for browser session handling and Next.js middleware."""
    response.set_cookie(
        key="brandproof_token",
        value=token,
        max_age=86400,
        httponly=False,  # Allows frontend client state to read for hydration sync while protected
        samesite="lax",
        path="/",
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, http_req: Request, response: Response, db: Session = Depends(get_db)):
    """Authenticate a user and return a JWT access token with brute-force rate limiting."""
    client_ip = http_req.client.host if http_req.client else "unknown"
    rate_key = f"{client_ip}:{request.email.lower()}"
    login_limiter.check(rate_key)

    user = db.query(User).filter(User.email == request.email.lower()).first()
    if not user or not verify_password(request.password, user.hashed_password):
        login_limiter.record_failure(rate_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Reset failed attempts upon successful login
    login_limiter.reset(rate_key)

    # Resolve active organization membership
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.status == MembershipStatus.ACTIVE.value
    ).first()

    active_org_id = membership.organization_id if membership else user.organization_id
    active_role = membership.role if membership else user.role

    # Ensure organization is active
    if active_org_id:
        org = db.query(Organization).filter(Organization.id == active_org_id, Organization.is_active.is_(True)).first()
        if not org:
            # Fall back to any active org membership
            fallback_mem = db.query(OrganizationMembership).join(
                Organization, OrganizationMembership.organization_id == Organization.id
            ).filter(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.status == MembershipStatus.ACTIVE.value,
                Organization.is_active.is_(True)
            ).first()
            if fallback_mem:
                active_org_id = fallback_mem.organization_id
                active_role = fallback_mem.role

    user.organization_id = active_org_id
    user.role = active_role

    access_token = create_access_token(
        subject=user.id,
        extra_claims={
            "role": active_role,
            "org_id": active_org_id,
            "email": user.email,
        }
    )

    _set_auth_cookie(response, access_token)

    record_audit_event(
        db=db,
        organization_id=active_org_id or "system",
        actor_id=user.id,
        action="USER_LOGIN",
        entity_type="User",
        entity_id=user.id,
        metadata={"email": user.email, "role": active_role}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user)
    )


@router.post("/register", response_model=TokenResponse)
def register(request: RegisterRequest, http_req: Request, response: Response, db: Session = Depends(get_db)):
    """
    Register a new user account and either create a new isolated organization workspace
    or join an existing organization via a verified cryptographic invitation.
    
    Security Invariant: A registrant can NEVER join or take over an existing organization
    through public registration without a valid cryptographically-signed invitation.
    Users joining via invitation receive the role assigned by the inviting admin.
    """
    client_ip = http_req.client.host if http_req.client else "unknown"
    reg_key = f"reg:{client_ip}"
    register_limiter.check(reg_key)

    # 1. Enforce password complexity
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )
    if len(request.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must not exceed 72 bytes.",
        )

    # 2. Check if user email already exists
    existing_user = db.query(User).filter(User.email == request.email.lower()).first()
    if existing_user:
        register_limiter.record_failure(reg_key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists. Please sign in to accept or switch organizations.",
        )

    now = datetime.now(timezone.utc)

    # 3. Handle organization association: either via invitation token OR founding new organization
    if request.invite_token:
        # A) JOINING EXISTING ORGANIZATION VIA INVITATION
        raw_token = request.invite_token.strip()
        token_hash = hash_invitation_token(raw_token)

        # First check database-backed invitations
        db_invite = db.query(OrganizationInvitation).filter(
            OrganizationInvitation.token_hash == token_hash
        ).first()

        invited_org_id = None
        assigned_role = UserRole.CREATOR.value
        invited_by_uid = None

        if db_invite:
            if db_invite.status != InvitationStatus.PENDING.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This invitation has already been used or was revoked.",
                )
            if db_invite.is_expired:
                db_invite.status = InvitationStatus.EXPIRED.value
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invitation link has expired. Please request a new invitation.",
                )
            if db_invite.invited_email and db_invite.invited_email.lower() != request.email.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"This invitation was issued specifically for {db_invite.invited_email}.",
                )
            invited_org_id = db_invite.organization_id
            assigned_role = db_invite.assigned_role
            invited_by_uid = db_invite.invited_by_id
        else:
            # Fallback to legacy JWT invite token decoding
            invite_payload, invite_error = decode_invite_token(raw_token)
            if not invite_payload:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=invite_error or "Invalid or expired invitation token.",
                )
            invited_email = invite_payload.get("email")
            if invited_email and invited_email.lower() != request.email.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"This invitation was issued specifically for {invited_email}.",
                )
            invited_org_id = invite_payload.get("org_id")
            assigned_role = UserRole.CREATOR.value

        org = db.query(Organization).filter(
            Organization.id == invited_org_id,
            Organization.is_active.is_(True)
        ).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The invited organization does not exist or is inactive.",
            )

        # SECURITY INVARIANT: Users cannot self-escalate roles during registration
        if request.role and request.role.value != assigned_role and request.role in (UserRole.ADMIN, UserRole.OWNER):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Privileged roles cannot be self-assigned during registration.",
            )

        assigned_title = "Team Member"
        action_name = "USER_JOINED_ORGANIZATION"

        # Create global user
        user = User(
            organization_id=org.id,
            email=request.email.lower(),
            hashed_password=hash_password(request.password),
            full_name=request.full_name.strip(),
            role=assigned_role,
            title=assigned_title,
            is_active=True,
        )
        db.add(user)
        db.flush()

        # Create OrganizationMembership
        membership = OrganizationMembership(
            user_id=user.id,
            organization_id=org.id,
            role=assigned_role,
            status=MembershipStatus.ACTIVE.value,
            joined_at=now,
            invited_by_id=invited_by_uid,
        )
        db.add(membership)

        if db_invite:
            db_invite.status = InvitationStatus.ACCEPTED.value
            db_invite.accepted_by_id = user.id

        db.commit()
        db.refresh(user)

    else:
        # B) FOUNDING A NEW ISOLATED ORGANIZATION
        if not request.organization_name or len(request.organization_name.strip()) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization name must be at least 2 characters long.",
            )

        org_name = request.organization_name.strip()
        base_slug = _slugify(request.organization_slug or org_name)
        if len(base_slug) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid organization slug.",
            )

        # Strictly prevent organization collision / takeover
        existing_org = db.query(Organization).filter(Organization.slug == base_slug).first()
        if existing_org:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An organization with this slug already exists. Please choose a unique organization name.",
            )

        email_domain = request.email.split("@")[-1].lower() if "@" in request.email else None

        # Create new Organization atomically
        org = Organization(
            name=org_name,
            slug=base_slug,
            domain=email_domain,
            is_active=True,
        )
        db.add(org)
        db.flush()

        assigned_role = UserRole.ADMIN.value
        assigned_title = "Organization Owner"
        action_name = "ORGANIZATION_INITIALIZED"

        # Create User record
        user = User(
            organization_id=org.id,
            email=request.email.lower(),
            hashed_password=hash_password(request.password),
            full_name=request.full_name.strip(),
            role=assigned_role,
            title=assigned_title,
            is_active=True,
        )
        db.add(user)
        db.flush()

        # Set owner reference on Organization
        org.owner_id = user.id

        # Create OrganizationMembership
        membership = OrganizationMembership(
            user_id=user.id,
            organization_id=org.id,
            role=assigned_role,
            status=MembershipStatus.ACTIVE.value,
            joined_at=now,
        )
        db.add(membership)
        db.commit()
        db.refresh(user)

    access_token = create_access_token(
        subject=user.id,
        extra_claims={
            "role": user.role,
            "org_id": user.organization_id,
            "email": user.email,
        }
    )

    _set_auth_cookie(response, access_token)

    record_audit_event(
        db=db,
        organization_id=org.id,
        actor_id=user.id,
        action=action_name,
        entity_type="User",
        entity_id=user.id,
        metadata={"name": org.name, "admin": user.email, "role": user.role}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user)
    )


@router.post("/logout")
def logout(response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Log out the current authenticated user, invalidate session cookie, and record audit event.
    """
    response.delete_cookie(
        key="brandproof_token",
        path="/",
        samesite="lax",
    )
    record_audit_event(
        db=db,
        organization_id=current_user.organization_id or "system",
        actor_id=current_user.id,
        action="USER_LOGOUT",
        entity_type="User",
        entity_id=current_user.id,
        metadata={"email": current_user.email}
    )
    return {"success": True, "message": "Successfully logged out."}


@router.get("/me", response_model=UserOut)
def get_current_authenticated_user(current_user: User = Depends(get_current_user)):
    """Retrieve profile of currently authenticated user in active organization context."""
    return UserOut.model_validate(current_user)
