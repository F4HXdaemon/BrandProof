import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.security import (
    generate_invitation_code,
    normalize_invitation_code,
    generate_invitation_token,
    hash_invitation_token,
    decode_invite_token,
    create_access_token,
)
from app.core.rate_limit import (
    invite_validate_limiter,
    invite_join_limiter,
    get_client_identifier,
)
from app.models.user import User, UserRole
from app.models.organization import (
    Organization,
    OrganizationMembership,
    OrganizationInvitation,
    MembershipStatus,
    InvitationStatus,
)
from app.schemas.auth_and_user import (
    OrganizationOut,
    OrganizationCreate,
    OrganizationUpdate,
    UserOrganizationOut,
    OrganizationMembershipOut,
    MemberRoleUpdateRequest,
    TransferOwnershipRequest,
    InviteCreateRequest,
    InviteResponse,
    InviteVerifyResponse,
    ValidateInvitationRequest,
    OrganizationInvitationOut,
    AcceptInvitationRequest,
    JoinInvitationRequest,
    JoinInvitationResponse,
    MembershipRequestApprovalRequest,
    SwitchOrganizationRequest,
    SwitchOrganizationResponse,
    UserOut,
)
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def _slugify(text: str) -> str:
    """Generate a clean URL-safe slug from text."""
    slug = re.sub(r"[^\w\s-]", "", text.strip().lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug or "org"


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="brandproof_token",
        value=token,
        max_age=86400,
        httponly=False,
        samesite="lax",
        path="/",
    )


# ==============================================================================
# Current Organization Profile & Settings
# ==============================================================================

@router.get("/current", response_model=OrganizationOut)
def get_current_organization(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve profile of the currently active organization."""
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.put("/current", response_model=OrganizationOut)
def update_current_organization(
    update_data: OrganizationUpdate,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OWNER])),
    db: Session = Depends(get_db)
):
    """Update settings of the currently active organization (Owner or Admin)."""
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if update_data.name is not None:
        org.name = update_data.name.strip()
    if update_data.domain is not None:
        org.domain = update_data.domain.strip() or None
    if update_data.is_active is not None:
        if not update_data.is_active and current_user.role != UserRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the Organization Owner can deactivate an organization.",
            )
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
        metadata={"name": org.name, "domain": org.domain, "is_active": org.is_active}
    )

    return org


# ==============================================================================
# Multi-Organization Membership & Organization Switching
# ==============================================================================

@router.get("/my-organizations", response_model=List[UserOrganizationOut])
def list_my_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all organizations the authenticated user belongs to with their
    organization-specific roles, joined timestamp, and current active status.
    """
    memberships = db.query(OrganizationMembership).join(
        Organization, OrganizationMembership.organization_id == Organization.id
    ).filter(
        OrganizationMembership.user_id == current_user.id,
        OrganizationMembership.status == MembershipStatus.ACTIVE.value,
        Organization.is_active.is_(True)
    ).order_by(OrganizationMembership.joined_at.asc()).all()

    # Ensure current_user's primary organization membership exists
    if current_user.organization_id and not any(m.organization_id == current_user.organization_id for m in memberships):
        primary_mem = db.query(OrganizationMembership).filter(
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.organization_id == current_user.organization_id
        ).first()
        if not primary_mem:
            primary_mem = OrganizationMembership(
                user_id=current_user.id,
                organization_id=current_user.organization_id,
                role=current_user.role or UserRole.CREATOR.value,
                status=MembershipStatus.ACTIVE.value,
                joined_at=current_user.created_at or datetime.now(timezone.utc),
            )
            db.add(primary_mem)
            db.commit()
            db.refresh(primary_mem)
        memberships.insert(0, primary_mem)

    results = []
    for m in memberships:
        org = m.organization
        is_curr = (org.id == current_user.organization_id)
        is_own = (org.owner_id == current_user.id)
        results.append(
            UserOrganizationOut(
                id=org.id,
                name=org.name,
                slug=org.slug,
                domain=org.domain,
                role=m.role,
                is_current=is_curr,
                is_owner=is_own,
                joined_at=m.joined_at.isoformat() if m.joined_at else m.created_at.isoformat(),
            )
        )
    return results


@router.post("/switch", response_model=SwitchOrganizationResponse)
def switch_organization(
    payload: SwitchOrganizationRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Switch the authenticated user's active organization.
    Validates active membership in the target organization and issues a fresh JWT token.
    """
    membership = db.query(OrganizationMembership).join(
        Organization, OrganizationMembership.organization_id == Organization.id
    ).filter(
        OrganizationMembership.user_id == current_user.id,
        OrganizationMembership.organization_id == payload.organization_id,
        OrganizationMembership.status == MembershipStatus.ACTIVE.value,
        Organization.is_active.is_(True)
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have an active membership in the requested organization.",
        )

    org = membership.organization

    # Update user's default organization
    current_user.organization_id = org.id
    current_user.role = membership.role
    db.commit()
    db.refresh(current_user)

    access_token = create_access_token(
        subject=current_user.id,
        extra_claims={
            "role": membership.role,
            "org_id": org.id,
            "email": current_user.email,
        }
    )

    _set_auth_cookie(response, access_token)

    record_audit_event(
        db=db,
        organization_id=org.id,
        actor_id=current_user.id,
        action="ORGANIZATION_SWITCHED",
        entity_type="Organization",
        entity_id=org.id,
        metadata={"switched_to": org.name, "role": membership.role}
    )

    return SwitchOrganizationResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(current_user),
        organization=OrganizationOut.model_validate(org),
        role=membership.role,
    )


@router.post("/create", response_model=SwitchOrganizationResponse)
def create_organization(
    payload: OrganizationCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new isolated organization workspace under the user's existing global account.
    The creator is automatically assigned as the Organization Owner.
    """
    if not payload.name or len(payload.name.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name must be at least 2 characters long.",
        )

    org_name = payload.name.strip()
    base_slug = _slugify(payload.slug or org_name)
    if len(base_slug) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization slug.",
        )

    # Prevent slug collision
    existing = db.query(Organization).filter(Organization.slug == base_slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this slug already exists. Please choose a unique name.",
        )

    now = datetime.now(timezone.utc)
    org = Organization(
        name=org_name,
        slug=base_slug,
        domain=payload.domain.strip() if payload.domain else None,
        is_active=True,
        owner_id=current_user.id,
    )
    db.add(org)
    db.flush()

    membership = OrganizationMembership(
        user_id=current_user.id,
        organization_id=org.id,
        role=UserRole.OWNER.value,
        status=MembershipStatus.ACTIVE.value,
        joined_at=now,
    )
    db.add(membership)

    current_user.organization_id = org.id
    current_user.role = UserRole.OWNER.value
    db.commit()
    db.refresh(org)
    db.refresh(current_user)

    access_token = create_access_token(
        subject=current_user.id,
        extra_claims={
            "role": UserRole.OWNER.value,
            "org_id": org.id,
            "email": current_user.email,
        }
    )

    _set_auth_cookie(response, access_token)

    record_audit_event(
        db=db,
        organization_id=org.id,
        actor_id=current_user.id,
        action="ORGANIZATION_INITIALIZED",
        entity_type="Organization",
        entity_id=org.id,
        metadata={"name": org.name, "slug": org.slug, "owner": current_user.email}
    )

    return SwitchOrganizationResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(current_user),
        organization=OrganizationOut.model_validate(org),
        role=UserRole.OWNER.value,
    )


# ==============================================================================
# Team Members Management
# ==============================================================================

@router.get("/current/members", response_model=List[OrganizationMembershipOut])
def get_organization_members(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all members belonging to the current active organization with roles and statuses."""
    memberships = db.query(OrganizationMembership).join(
        User, OrganizationMembership.user_id == User.id
    ).filter(
        OrganizationMembership.organization_id == current_user.organization_id
    ).order_by(OrganizationMembership.joined_at.asc()).all()

    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    owner_id = org.owner_id if org else None

    results = []
    for m in memberships:
        u = m.user
        results.append(
            OrganizationMembershipOut(
                id=m.id,
                user_id=u.id,
                full_name=u.full_name,
                email=u.email,
                role=m.role,
                title=u.title,
                avatar_url=u.avatar_url,
                status=m.status,
                joined_at=m.joined_at.isoformat() if m.joined_at else m.created_at.isoformat(),
                is_owner=(u.id == owner_id),
            )
        )
    return results


@router.put("/current/members/{membership_id}", response_model=OrganizationMembershipOut)
def update_member_role(
    membership_id: str,
    payload: MemberRoleUpdateRequest,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OWNER])),
    db: Session = Depends(get_db)
):
    """
    Update an organization member's role (Admin or Owner).
    Enforces governance safeguards:
    - Admins cannot modify the Owner.
    - Admins cannot promote anyone to Owner.
    - Admins cannot demote other Admins (only Owner can manage Admins).
    - The Owner's role cannot be demoted without transferring ownership.
    """
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.id == membership_id,
        OrganizationMembership.organization_id == current_user.organization_id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Member not found in current organization")

    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    is_target_owner = (org.owner_id == membership.user_id) if org else False
    is_actor_owner = (current_user.role == UserRole.OWNER.value)

    # Target is the owner
    if is_target_owner and payload.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change role of the Organization Owner. Transfer ownership first.",
        )

    # Actor is an Admin (not Owner)
    if not is_actor_owner:
        if is_target_owner:
            raise HTTPException(status_code=403, detail="Admins cannot modify the Organization Owner.")
        if payload.role == UserRole.OWNER:
            raise HTTPException(status_code=403, detail="Admins cannot assign the Owner role.")
        if membership.role == UserRole.ADMIN.value and membership.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only the Organization Owner can modify other Administrators.")

    old_role = membership.role
    membership.role = payload.role.value if isinstance(payload.role, UserRole) else str(payload.role)
    db.commit()
    db.refresh(membership)

    u = membership.user
    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="MEMBER_ROLE_UPDATED",
        entity_type="OrganizationMembership",
        entity_id=membership.id,
        metadata={"user": u.email, "old_role": old_role, "new_role": membership.role}
    )

    return OrganizationMembershipOut(
        id=membership.id,
        user_id=u.id,
        full_name=u.full_name,
        email=u.email,
        role=membership.role,
        title=u.title,
        avatar_url=u.avatar_url,
        status=membership.status,
        joined_at=membership.joined_at.isoformat() if membership.joined_at else membership.created_at.isoformat(),
        is_owner=is_target_owner,
    )


@router.delete("/current/members/{membership_id}")
def remove_member(
    membership_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove a member from the organization, or allow a member to leave.
    Enforces governance safeguards:
    - Non-admins can only remove their own membership (leave).
    - Admins cannot remove the Owner or other Admins.
    - The Owner cannot be removed without transferring ownership.
    """
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.id == membership_id,
        OrganizationMembership.organization_id == current_user.organization_id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Member not found in current organization")

    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    is_target_owner = (org.owner_id == membership.user_id) if org else False
    is_actor_owner = (current_user.role == UserRole.OWNER.value)
    is_actor_admin = (current_user.role == UserRole.ADMIN.value)
    is_self = (membership.user_id == current_user.id)

    if is_target_owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The Organization Owner cannot be removed. Transfer ownership before leaving.",
        )

    if not is_self:
        if not (is_actor_owner or is_actor_admin):
            raise HTTPException(status_code=403, detail="Permission denied: You cannot remove team members.")
        if is_actor_admin and not is_actor_owner:
            if membership.role in (UserRole.ADMIN.value, UserRole.OWNER.value):
                raise HTTPException(status_code=403, detail="Only the Owner can remove an Administrator.")

    member_email = membership.user.email if membership.user else "unknown"
    db.delete(membership)
    db.commit()

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="MEMBER_REMOVED",
        entity_type="OrganizationMembership",
        entity_id=membership_id,
        metadata={"removed_user": member_email, "actor": current_user.email}
    )

    return {"success": True, "message": f"Member {member_email} has been removed from the organization."}


# ==============================================================================
# Organization Ownership Transfer
# ==============================================================================

@router.post("/current/transfer-ownership")
def transfer_organization_ownership(
    payload: TransferOwnershipRequest,
    current_user: User = Depends(require_roles([UserRole.OWNER])),
    db: Session = Depends(get_db)
):
    """
    Transfer ownership of the organization to another active member (Owner only).
    The previous owner becomes an Admin; the target member becomes the new Owner.
    """
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if payload.new_owner_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You are already the Organization Owner.")

    # Verify target is an active member
    target_membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org.id,
        OrganizationMembership.user_id == payload.new_owner_user_id,
        OrganizationMembership.status == MembershipStatus.ACTIVE.value
    ).first()

    if not target_membership:
        raise HTTPException(status_code=404, detail="Target user is not an active member of this organization.")

    # Find current user's membership
    current_membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org.id,
        OrganizationMembership.user_id == current_user.id
    ).first()

    # Transfer roles
    org.owner_id = payload.new_owner_user_id
    target_membership.role = UserRole.OWNER.value
    if current_membership:
        current_membership.role = UserRole.ADMIN.value
    current_user.role = UserRole.ADMIN.value

    db.commit()

    record_audit_event(
        db=db,
        organization_id=org.id,
        actor_id=current_user.id,
        action="OWNERSHIP_TRANSFERRED",
        entity_type="Organization",
        entity_id=org.id,
        metadata={
            "previous_owner": current_user.email,
            "new_owner": target_membership.user.email if target_membership.user else payload.new_owner_user_id,
        }
    )

    return {
        "success": True,
        "message": f"Ownership successfully transferred to {target_membership.user.full_name if target_membership.user else 'new owner'}.",
        "new_owner_id": payload.new_owner_user_id,
    }


# ==============================================================================
# Organization Invitations & Membership Requests Helper Functions
# ==============================================================================

def _find_invitation_record(db: Session, identifier: str) -> tuple[Optional[OrganizationInvitation], Optional[dict]]:
    """
    Search for an invitation by:
    1. Cryptographic token SHA-256 hash.
    2. Case-insensitive and formatted/unformatted alphanumeric invitation code (e.g., BP-8K2M-9P4W or 8K2M9P4W).
    3. Legacy signed JWT invite token fallback.
    """
    raw = identifier.strip()
    if not raw:
        return None, None

    # 1. Check database token_hash
    token_hash = hash_invitation_token(raw)
    inv = db.query(OrganizationInvitation).filter(OrganizationInvitation.token_hash == token_hash).first()
    if inv:
        return inv, None

    # 2. Check code variants
    clean = raw.upper()
    variants = {raw, clean}
    no_dash = clean.replace("-", "").replace(" ", "")
    variants.add(no_dash)
    if no_dash.startswith("BP") and len(no_dash) == 10:
        variants.add(f"BP-{no_dash[2:6]}-{no_dash[6:]}")
    elif not no_dash.startswith("BP") and len(no_dash) == 8:
        variants.add(f"BP-{no_dash[:4]}-{no_dash[4:]}")

    inv = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.invitation_code.in_(list(variants))
    ).first()
    if inv:
        return inv, None

    # 3. Check legacy JWT invite token
    jwt_payload, _ = decode_invite_token(raw)
    if jwt_payload:
        return None, jwt_payload

    return None, None


def _validate_invitation_common(db: Session, identifier: str, client_ip: str) -> InviteVerifyResponse:
    """Shared logic for validating an invitation code or token."""
    invite_validate_limiter.check(client_ip)

    inv, jwt_payload = _find_invitation_record(db, identifier)
    if not inv and not jwt_payload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation code or token not found. Please verify the code and try again.",
        )

    if inv:
        if inv.status == InvitationStatus.REVOKED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invitation is no longer valid (revoked by an organization administrator).",
            )
        if inv.is_expired or inv.status == InvitationStatus.EXPIRED.value:
            if inv.status != InvitationStatus.EXPIRED.value:
                inv.status = InvitationStatus.EXPIRED.value
                db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invitation code has expired. Please request a new invitation.",
            )
        if inv.is_exhausted or inv.status == InvitationStatus.EXHAUSTED.value:
            if inv.status != InvitationStatus.EXHAUSTED.value:
                inv.status = InvitationStatus.EXHAUSTED.value
                db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invitation code has reached its maximum usage limit.",
            )
        if inv.status == InvitationStatus.ACCEPTED.value and inv.max_uses == 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This single-use invitation code has already been accepted.",
            )

        org = db.query(Organization).filter(
            Organization.id == inv.organization_id,
            Organization.is_active.is_(True)
        ).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The organization associated with this invite does not exist or has been deactivated.",
            )

        allowed_roles = inv.get_allowed_roles_list()
        return InviteVerifyResponse(
            organization_id=org.id,
            organization_name=org.name,
            organization_slug=org.slug,
            description=org.description,
            logo_url=org.logo_url,
            email=inv.invited_email,
            role=inv.assigned_role,
            allowed_roles=allowed_roles,
            expires_at=inv.expires_at.isoformat() if inv.expires_at else None,
            max_uses=inv.max_uses,
            use_count=inv.use_count,
            requires_approval=inv.requires_approval,
            inviter_name=inv.invited_by.full_name if inv.invited_by else None,
            valid=True,
        )

    # Legacy JWT payload
    org_id = jwt_payload.get("org_id")
    org = db.query(Organization).filter(Organization.id == org_id, Organization.is_active.is_(True)).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The organization associated with this invite does not exist or has been deactivated.",
        )

    return InviteVerifyResponse(
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        description=org.description,
        logo_url=org.logo_url,
        email=jwt_payload.get("email"),
        role="Creator",
        allowed_roles=["Creator"],
        expires_at=None,
        max_uses=1,
        use_count=0,
        requires_approval=False,
        valid=True,
    )


# ==============================================================================
# Organization Invitations Management Endpoints
# ==============================================================================

@router.post("/current/invitations", response_model=InviteResponse)
@router.post("/current/invites", response_model=InviteResponse)
def create_organization_invitation(
    payload: InviteCreateRequest,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OWNER])),
    db: Session = Depends(get_db)
):
    """
    Generate an organization invitation or shareable code.
    Governance safeguards:
    - Never allow issuing an OWNER invitation (must use transfer-ownership).
    - Admins cannot issue ADMIN invitations (only the Owner can grant Admin privileges).
    - Email-specific invitations revoke prior pending invites for that email.
    """
    target_email = str(payload.email).lower().strip() if payload.email else None
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    assigned_role = payload.role.value if isinstance(payload.role, UserRole) else str(payload.role or UserRole.CREATOR.value)

    # Security check: Never allow OWNER role in invitations
    if assigned_role == UserRole.OWNER.value:
        raise HTTPException(status_code=400, detail="Cannot invite members directly as Owner. Transfer ownership instead.")

    # Determine allowed roles
    if payload.allowed_roles:
        allowed_roles_list = [
            (r.value if isinstance(r, UserRole) else str(r))
            for r in payload.allowed_roles
        ]
        if UserRole.OWNER.value in allowed_roles_list:
            raise HTTPException(status_code=400, detail="Owner role cannot be granted through an invitation.")
    else:
        allowed_roles_list = [assigned_role]

    # Security check: Admins cannot grant ADMIN privileges
    is_owner = (current_user.role == UserRole.OWNER.value)
    if not is_owner:
        if assigned_role == UserRole.ADMIN.value or UserRole.ADMIN.value in allowed_roles_list:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the Organization Owner can issue invitations with Administrator privileges.",
            )

    # If email-bound, ensure user is not already active member
    if target_email:
        existing_member = db.query(OrganizationMembership).join(
            User, OrganizationMembership.user_id == User.id
        ).filter(
            OrganizationMembership.organization_id == org.id,
            User.email == target_email,
            OrganizationMembership.status == MembershipStatus.ACTIVE.value
        ).first()
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{target_email} is already an active member of this organization.",
            )

        # Revoke any prior pending invitations for this email in this org
        prior_invites = db.query(OrganizationInvitation).filter(
            OrganizationInvitation.organization_id == org.id,
            OrganizationInvitation.invited_email == target_email,
            OrganizationInvitation.status == InvitationStatus.PENDING.value
        ).all()
        for pi in prior_invites:
            pi.status = InvitationStatus.REVOKED.value

    # Generate cryptographic token and human-friendly invitation code
    raw_token, token_hash = generate_invitation_token()

    # Ensure unique invitation code
    for _ in range(5):
        code_candidate = generate_invitation_code()
        collision = db.query(OrganizationInvitation).filter(
            OrganizationInvitation.invitation_code == code_candidate
        ).first()
        if not collision:
            invitation_code = code_candidate
            break
    else:
        invitation_code = generate_invitation_code()

    days = payload.expires_in_days or 7
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    max_uses = payload.max_uses if (payload.max_uses is not None and payload.max_uses >= 0) else 1
    allowed_roles_str = ",".join(allowed_roles_list)

    invitation = OrganizationInvitation(
        organization_id=org.id,
        invited_email=target_email,
        assigned_role=assigned_role,
        allowed_roles=allowed_roles_str,
        invitation_code=invitation_code,
        token_hash=token_hash,
        expires_at=expires_at,
        max_uses=max_uses,
        use_count=0,
        requires_approval=bool(payload.requires_approval),
        status=InvitationStatus.PENDING.value,
        invited_by_id=current_user.id,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    record_audit_event(
        db=db,
        organization_id=org.id,
        actor_id=current_user.id,
        action="ORGANIZATION_INVITE_CREATED",
        entity_type="OrganizationInvitation",
        entity_id=invitation.id,
        metadata={
            "email": target_email,
            "role": assigned_role,
            "allowed_roles": allowed_roles_list,
            "code": invitation_code,
            "max_uses": max_uses,
            "requires_approval": invitation.requires_approval,
            "expires_at": expires_at.isoformat(),
        }
    )

    return InviteResponse(
        invite_token=raw_token,
        invitation_code=invitation_code,
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        email=target_email,
        role=assigned_role,
        allowed_roles=allowed_roles_list,
        expires_at=expires_at.isoformat(),
        max_uses=max_uses,
        use_count=0,
        requires_approval=invitation.requires_approval,
        invite_url=f"/invite/{raw_token}",
    )


@router.get("/current/invitations", response_model=List[OrganizationInvitationOut])
def list_current_invitations(
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OWNER])),
    db: Session = Depends(get_db)
):
    """List all invitations issued for the currently active organization."""
    invites = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.organization_id == current_user.organization_id,
    ).order_by(OrganizationInvitation.created_at.desc()).all()

    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    org_name = org.name if org else ""
    org_slug = org.slug if org else ""

    results = []
    for inv in invites:
        results.append(
            OrganizationInvitationOut(
                id=inv.id,
                organization_id=inv.organization_id,
                organization_name=org_name,
                organization_slug=org_slug,
                invited_email=inv.invited_email,
                assigned_role=inv.assigned_role,
                allowed_roles=inv.get_allowed_roles_list(),
                invitation_code=inv.invitation_code,
                status=inv.status,
                expires_at=inv.expires_at.isoformat() if inv.expires_at else "",
                created_at=inv.created_at.isoformat() if inv.created_at else "",
                max_uses=inv.max_uses,
                use_count=inv.use_count,
                requires_approval=inv.requires_approval,
                inviter_name=inv.invited_by.full_name if inv.invited_by else None,
            )
        )
    return results


@router.delete("/current/invitations/{invitation_id}")
def revoke_invitation(
    invitation_id: str,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OWNER])),
    db: Session = Depends(get_db)
):
    """Revoke a pending organization invitation (Admin or Owner)."""
    invite = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.id == invitation_id,
        OrganizationInvitation.organization_id == current_user.organization_id
    ).first()

    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found")

    invite.status = InvitationStatus.REVOKED.value
    db.commit()

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="ORGANIZATION_INVITE_REVOKED",
        entity_type="OrganizationInvitation",
        entity_id=invite.id,
        metadata={"email": invite.invited_email, "code": invite.invitation_code}
    )

    return {"success": True, "message": f"Invitation {invite.invitation_code or invite.id} has been revoked."}


# ==============================================================================
# Invitation Validation Endpoints (Public / Authenticated)
# ==============================================================================

@router.post("/invitations/validate", response_model=InviteVerifyResponse)
def validate_invitation_post(
    payload: ValidateInvitationRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Validate an invitation code or token via JSON body and return safe preview."""
    client_ip = get_client_identifier(request)
    return _validate_invitation_common(db, payload.code, client_ip)


@router.get("/invitations/validate", response_model=InviteVerifyResponse)
def validate_invitation_get(
    request: Request,
    code: str = Query(..., description="Invitation code or token"),
    db: Session = Depends(get_db)
):
    """Validate an invitation code or token via query param and return safe preview."""
    client_ip = get_client_identifier(request)
    return _validate_invitation_common(db, code, client_ip)


@router.get("/invitations/verify", response_model=InviteVerifyResponse)
@router.get("/invites/verify", response_model=InviteVerifyResponse)
def verify_invitation_token(
    request: Request,
    token: Optional[str] = Query(None, description="Cryptographic invitation token"),
    code: Optional[str] = Query(None, description="Invitation code"),
    db: Session = Depends(get_db)
):
    """Inspect and validate an invitation token or code before accepting."""
    target = token or code
    if not target:
        raise HTTPException(status_code=400, detail="Invitation token or code is required.")
    client_ip = get_client_identifier(request)
    return _validate_invitation_common(db, target, client_ip)


# ==============================================================================
# Joining Organization via Invitation Code or Token
# ==============================================================================

def _process_join_invitation(
    identifier: str,
    requested_role: Optional[UserRole],
    current_user: User,
    response: Response,
    request: Request,
    db: Session,
) -> JoinInvitationResponse:
    """Core transactional handler for accepting an invitation or joining via code."""
    client_id = get_client_identifier(request, current_user.id)
    invite_join_limiter.check(client_id)

    raw = identifier.strip()
    token_hash = hash_invitation_token(raw)

    # Use row-level locking where supported to prevent race conditions on use limits
    query = db.query(OrganizationInvitation).filter(
        or_(
            OrganizationInvitation.token_hash == token_hash,
            OrganizationInvitation.invitation_code == raw.upper(),
            OrganizationInvitation.invitation_code == raw,
        )
    )
    if db.bind and db.bind.dialect.name != "sqlite":
        query = query.with_for_update()
    inv = query.first()

    target_org_id = None
    allowed_roles = [UserRole.CREATOR.value]
    default_role = UserRole.CREATOR.value
    requires_approval = False
    invited_by_uid = None

    if inv:
        if inv.status == InvitationStatus.REVOKED.value:
            raise HTTPException(status_code=400, detail="This invitation has been revoked.")
        if inv.is_expired:
            inv.status = InvitationStatus.EXPIRED.value
            db.commit()
            raise HTTPException(status_code=400, detail="This invitation code has expired.")
        if inv.is_exhausted:
            inv.status = InvitationStatus.EXHAUSTED.value
            db.commit()
            raise HTTPException(status_code=400, detail="This invitation code has reached its maximum usage limit.")
        if inv.status == InvitationStatus.ACCEPTED.value and inv.max_uses == 1:
            raise HTTPException(status_code=400, detail="This single-use invitation has already been used.")

        # Email restriction validation
        if inv.invited_email and inv.invited_email.lower() != current_user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This invitation was issued for {inv.invited_email}. You are signed in as {current_user.email}.",
            )

        target_org_id = inv.organization_id
        allowed_roles = inv.get_allowed_roles_list()
        default_role = inv.assigned_role or allowed_roles[0]
        requires_approval = inv.requires_approval
        invited_by_uid = inv.invited_by_id
    else:
        # Check code variants
        clean = raw.upper().replace("-", "").replace(" ", "")
        variants = {raw, raw.upper(), clean}
        if clean.startswith("BP") and len(clean) == 10:
            variants.add(f"BP-{clean[2:6]}-{clean[6:]}")
        elif not clean.startswith("BP") and len(clean) == 8:
            variants.add(f"BP-{clean[:4]}-{clean[4:]}")

        query = db.query(OrganizationInvitation).filter(
            OrganizationInvitation.invitation_code.in_(list(variants))
        )
        if db.bind and db.bind.dialect.name != "sqlite":
            query = query.with_for_update()
        inv = query.first()

        if inv:
            if inv.status == InvitationStatus.REVOKED.value:
                raise HTTPException(status_code=400, detail="This invitation has been revoked.")
            if inv.is_expired:
                inv.status = InvitationStatus.EXPIRED.value
                db.commit()
                raise HTTPException(status_code=400, detail="This invitation code has expired.")
            if inv.is_exhausted:
                inv.status = InvitationStatus.EXHAUSTED.value
                db.commit()
                raise HTTPException(status_code=400, detail="This invitation code has reached its maximum usage limit.")
            if inv.status == InvitationStatus.ACCEPTED.value and inv.max_uses == 1:
                raise HTTPException(status_code=400, detail="This single-use invitation has already been used.")

            if inv.invited_email and inv.invited_email.lower() != current_user.email.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"This invitation was issued for {inv.invited_email}. You are signed in as {current_user.email}.",
                )

            target_org_id = inv.organization_id
            allowed_roles = inv.get_allowed_roles_list()
            default_role = inv.assigned_role or allowed_roles[0]
            requires_approval = inv.requires_approval
            invited_by_uid = inv.invited_by_id
        else:
            # Fallback: legacy JWT invite token
            jwt_payload, err = decode_invite_token(raw)
            if not jwt_payload:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=err or "Invalid or expired invitation code / token.",
                )
            if jwt_payload.get("email") and jwt_payload.get("email").lower() != current_user.email.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"This invitation was issued for {jwt_payload.get('email')}. You are signed in as {current_user.email}.",
                )
            target_org_id = jwt_payload.get("org_id")

    org = db.query(Organization).filter(
        Organization.id == target_org_id,
        Organization.is_active.is_(True)
    ).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found or inactive.")

    # Role validation against permitted roles
    if requested_role:
        sel_role = requested_role.value if isinstance(requested_role, UserRole) else str(requested_role)
        if sel_role == UserRole.OWNER.value:
            raise HTTPException(status_code=403, detail="Owner role cannot be assigned via invitation.")
        if sel_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{sel_role}' is not permitted by this invitation. Permitted roles: {', '.join(allowed_roles)}.",
            )
        assigned_role = sel_role
    else:
        assigned_role = default_role

    # Check existing membership
    existing_mem = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == current_user.id,
        OrganizationMembership.organization_id == org.id
    ).first()

    if existing_mem:
        if existing_mem.status == MembershipStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You are already an active member of {org.name}.",
            )
        elif existing_mem.status == MembershipStatus.PENDING_APPROVAL.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You already have a pending membership request for {org.name}. Please wait for administrator approval.",
            )

    now = datetime.now(timezone.utc)

    # Branch: requires approval vs automatic join
    if requires_approval:
        if existing_mem:
            existing_mem.status = MembershipStatus.PENDING_APPROVAL.value
            existing_mem.role = assigned_role
            membership = existing_mem
        else:
            membership = OrganizationMembership(
                user_id=current_user.id,
                organization_id=org.id,
                role=assigned_role,
                status=MembershipStatus.PENDING_APPROVAL.value,
                joined_at=now,
                invited_by_id=invited_by_uid,
            )
            db.add(membership)

        if inv:
            inv.use_count += 1
            if inv.max_uses > 0 and inv.use_count >= inv.max_uses:
                inv.status = InvitationStatus.EXHAUSTED.value

        db.commit()

        record_audit_event(
            db=db,
            organization_id=org.id,
            actor_id=current_user.id,
            action="MEMBERSHIP_REQUESTED",
            entity_type="OrganizationMembership",
            entity_id=membership.id,
            metadata={"user": current_user.email, "role": assigned_role, "org_name": org.name}
        )

        return JoinInvitationResponse(
            status="pending_approval",
            message=f"Your request to join {org.name} as {assigned_role} has been submitted for administrator approval.",
            access_token=None,
            user=UserOut.model_validate(current_user),
            organization=OrganizationOut.model_validate(org),
            role=assigned_role,
        )

    # Automatic join
    if existing_mem:
        existing_mem.status = MembershipStatus.ACTIVE.value
        existing_mem.role = assigned_role
        membership = existing_mem
    else:
        membership = OrganizationMembership(
            user_id=current_user.id,
            organization_id=org.id,
            role=assigned_role,
            status=MembershipStatus.ACTIVE.value,
            joined_at=now,
            invited_by_id=invited_by_uid,
        )
        db.add(membership)

    if inv:
        inv.use_count += 1
        inv.accepted_by_id = current_user.id
        if inv.max_uses > 0 and inv.use_count >= inv.max_uses:
            inv.status = InvitationStatus.EXHAUSTED.value
        elif inv.max_uses == 1:
            inv.status = InvitationStatus.ACCEPTED.value

    # Switch active organization
    current_user.organization_id = org.id
    current_user.role = assigned_role
    db.commit()
    db.refresh(current_user)

    access_token = create_access_token(
        subject=current_user.id,
        extra_claims={
            "role": assigned_role,
            "org_id": org.id,
            "email": current_user.email,
        }
    )

    _set_auth_cookie(response, access_token)

    record_audit_event(
        db=db,
        organization_id=org.id,
        actor_id=current_user.id,
        action="USER_JOINED_ORGANIZATION",
        entity_type="Organization",
        entity_id=org.id,
        metadata={"user": current_user.email, "role": assigned_role, "org_name": org.name}
    )

    return JoinInvitationResponse(
        status="active",
        message=f"Successfully joined {org.name} as {assigned_role}.",
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(current_user),
        organization=OrganizationOut.model_validate(org),
        role=assigned_role,
    )


@router.post("/invitations/join", response_model=JoinInvitationResponse)
def join_organization_with_code(
    payload: JoinInvitationRequest,
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Authenticated endpoint for a user to join an organization using an invitation code or token.
    Supports role selection if multiple roles are permitted by the invitation.
    Handles automatic joining or pending approval according to invitation policy.
    """
    return _process_join_invitation(
        identifier=payload.code,
        requested_role=payload.role,
        current_user=current_user,
        response=response,
        request=request,
        db=db,
    )


@router.post("/invitations/accept", response_model=SwitchOrganizationResponse)
def accept_invitation(
    payload: AcceptInvitationRequest,
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Authenticated endpoint to accept an invitation token (backward-compatible).
    """
    join_res = _process_join_invitation(
        identifier=payload.token,
        requested_role=payload.role,
        current_user=current_user,
        response=response,
        request=request,
        db=db,
    )

    if join_res.status == "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail=join_res.message,
        )

    return SwitchOrganizationResponse(
        access_token=join_res.access_token or "",
        token_type="bearer",
        user=join_res.user or UserOut.model_validate(current_user),
        organization=join_res.organization or OrganizationOut.model_validate(
            db.query(Organization).filter(Organization.id == current_user.organization_id).first()
        ),
        role=join_res.role or current_user.role or "Creator",
    )


# ==============================================================================
# Membership Requests Management (Admin / Owner)
# ==============================================================================

@router.get("/current/membership-requests", response_model=List[OrganizationMembershipOut])
def list_membership_requests(
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OWNER])),
    db: Session = Depends(get_db)
):
    """List all pending membership requests waiting for administrator approval."""
    requests = db.query(OrganizationMembership).join(
        User, OrganizationMembership.user_id == User.id
    ).filter(
        OrganizationMembership.organization_id == current_user.organization_id,
        OrganizationMembership.status == MembershipStatus.PENDING_APPROVAL.value
    ).order_by(OrganizationMembership.joined_at.asc()).all()

    results = []
    for m in requests:
        u = m.user
        results.append(
            OrganizationMembershipOut(
                id=m.id,
                user_id=u.id,
                full_name=u.full_name,
                email=u.email,
                role=m.role,
                title=u.title,
                avatar_url=u.avatar_url,
                status=m.status,
                joined_at=m.joined_at.isoformat() if m.joined_at else m.created_at.isoformat(),
                is_owner=False,
            )
        )
    return results


@router.post("/current/membership-requests/{membership_id}/approve", response_model=OrganizationMembershipOut)
def approve_membership_request(
    membership_id: str,
    payload: Optional[MembershipRequestApprovalRequest] = None,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OWNER])),
    db: Session = Depends(get_db)
):
    """
    Approve a pending membership request (Admin or Owner).
    Optionally adjust the granted role upon approval.
    """
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.id == membership_id,
        OrganizationMembership.organization_id == current_user.organization_id,
        OrganizationMembership.status == MembershipStatus.PENDING_APPROVAL.value
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Pending membership request not found.")

    is_actor_owner = (current_user.role == UserRole.OWNER.value)

    if payload and payload.role:
        new_role = payload.role.value if isinstance(payload.role, UserRole) else str(payload.role)
        if new_role == UserRole.OWNER.value:
            raise HTTPException(status_code=403, detail="Cannot assign Owner role during membership approval.")
        if not is_actor_owner and new_role == UserRole.ADMIN.value:
            raise HTTPException(status_code=403, detail="Only Organization Owners can approve Administrator memberships.")
        membership.role = new_role

    membership.status = MembershipStatus.ACTIVE.value
    u = membership.user

    # If user currently has no active organization, set this organization as default
    if not u.organization_id:
        u.organization_id = membership.organization_id
        u.role = membership.role

    db.commit()
    db.refresh(membership)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="MEMBERSHIP_REQUEST_APPROVED",
        entity_type="OrganizationMembership",
        entity_id=membership.id,
        metadata={"user": u.email, "role": membership.role, "approved_by": current_user.email}
    )

    return OrganizationMembershipOut(
        id=membership.id,
        user_id=u.id,
        full_name=u.full_name,
        email=u.email,
        role=membership.role,
        title=u.title,
        avatar_url=u.avatar_url,
        status=membership.status,
        joined_at=membership.joined_at.isoformat() if membership.joined_at else membership.created_at.isoformat(),
        is_owner=False,
    )


@router.post("/current/membership-requests/{membership_id}/reject")
def reject_membership_request(
    membership_id: str,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OWNER])),
    db: Session = Depends(get_db)
):
    """
    Reject a pending membership request (Admin or Owner).
    Removes the pending request from the queue.
    """
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.id == membership_id,
        OrganizationMembership.organization_id == current_user.organization_id,
        OrganizationMembership.status == MembershipStatus.PENDING_APPROVAL.value
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Pending membership request not found.")

    user_email = membership.user.email if membership.user else "unknown"
    db.delete(membership)
    db.commit()

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="MEMBERSHIP_REQUEST_REJECTED",
        entity_type="OrganizationMembership",
        entity_id=membership_id,
        metadata={"user": user_email, "rejected_by": current_user.email}
    )

    return {"success": True, "message": f"Membership request for {user_email} has been rejected."}


# ==============================================================================
# User Pending Invitations
# ==============================================================================

@router.get("/my-invitations", response_model=List[OrganizationInvitationOut])
def list_my_pending_invitations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all pending invitations received for the authenticated user's email address
    across any organizations in BrandProof.
    """
    now = datetime.now(timezone.utc)
    invites = db.query(OrganizationInvitation).join(
        Organization, OrganizationInvitation.organization_id == Organization.id
    ).filter(
        OrganizationInvitation.invited_email == current_user.email.lower(),
        OrganizationInvitation.status == InvitationStatus.PENDING.value,
        OrganizationInvitation.expires_at > now,
        Organization.is_active.is_(True)
    ).order_by(OrganizationInvitation.created_at.desc()).all()

    results = []
    for inv in invites:
        results.append(
            OrganizationInvitationOut(
                id=inv.id,
                organization_id=inv.organization_id,
                organization_name=inv.organization.name if inv.organization else None,
                organization_slug=inv.organization.slug if inv.organization else None,
                invited_email=inv.invited_email,
                assigned_role=inv.assigned_role,
                allowed_roles=inv.get_allowed_roles_list(),
                invitation_code=inv.invitation_code,
                status=inv.status,
                expires_at=inv.expires_at.isoformat() if inv.expires_at else "",
                created_at=inv.created_at.isoformat() if inv.created_at else "",
                max_uses=inv.max_uses,
                use_count=inv.use_count,
                requires_approval=inv.requires_approval,
                inviter_name=inv.invited_by.full_name if inv.invited_by else None,
            )
        )
    return results
