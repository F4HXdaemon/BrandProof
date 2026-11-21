import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.security import (
    generate_invitation_token,
    hash_invitation_token,
    decode_invite_token,
    create_access_token,
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
    OrganizationInvitationOut,
    AcceptInvitationRequest,
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
# Organization Invitations Management
# ==============================================================================

@router.post("/current/invitations", response_model=InviteResponse)
@router.post("/current/invites", response_model=InviteResponse)
def create_organization_invitation(
    payload: InviteCreateRequest,
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OWNER])),
    db: Session = Depends(get_db)
):
    """
    Generate a cryptographically secure invitation to join this organization with a designated role.
    Only Organization Admins and Owners can invite members.
    """
    target_email = str(payload.email).lower().strip() if payload.email else None
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if user is already an active member
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

    # Generate token
    raw_token, token_hash = generate_invitation_token()
    days = payload.expires_in_days or 7
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    assigned_role = payload.role.value if isinstance(payload.role, UserRole) else str(payload.role or UserRole.CREATOR.value)

    # Admins cannot invite as Owner
    if assigned_role == UserRole.OWNER.value:
        raise HTTPException(status_code=400, detail="Cannot invite members directly as Owner. Transfer ownership instead.")

    invitation = OrganizationInvitation(
        organization_id=org.id,
        invited_email=target_email,
        assigned_role=assigned_role,
        token_hash=token_hash,
        expires_at=expires_at,
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
        metadata={"email": target_email, "role": assigned_role, "expires_at": expires_at.isoformat()}
    )

    return InviteResponse(
        invite_token=raw_token,
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        email=target_email,
        role=assigned_role,
        expires_at=expires_at.isoformat(),
        invite_url=f"/invite/{raw_token}",
    )


@router.get("/current/invitations", response_model=List[OrganizationInvitationOut])
def list_current_invitations(
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.OWNER])),
    db: Session = Depends(get_db)
):
    """List pending invitations issued for the currently active organization."""
    now = datetime.now(timezone.utc)
    invites = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.organization_id == current_user.organization_id,
        OrganizationInvitation.status == InvitationStatus.PENDING.value,
        OrganizationInvitation.expires_at > now
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
                status=inv.status,
                expires_at=inv.expires_at.isoformat(),
                created_at=inv.created_at.isoformat(),
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
        metadata={"email": invite.invited_email}
    )

    return {"success": True, "message": f"Invitation for {invite.invited_email} has been revoked."}


@router.get("/invitations/verify", response_model=InviteVerifyResponse)
@router.get("/invites/verify", response_model=InviteVerifyResponse)
def verify_invitation_token(
    token: str = Query(..., description="Cryptographic invitation token"),
    db: Session = Depends(get_db)
):
    """
    Public verification endpoint to inspect and validate an invitation token before accepting.
    Returns organization details and inviter identity.
    """
    raw_token = token.strip()
    token_hash = hash_invitation_token(raw_token)

    # 1. Check database-backed invitation
    inv = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.token_hash == token_hash
    ).first()

    if inv:
        if inv.status != InvitationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invitation is no longer valid (already accepted or revoked)."
            )
        if inv.is_expired:
            inv.status = InvitationStatus.EXPIRED.value
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation link has expired. Please request a new invitation."
            )
        org = db.query(Organization).filter(
            Organization.id == inv.organization_id,
            Organization.is_active.is_(True)
        ).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The organization associated with this invite does not exist or has been deactivated."
            )
        return InviteVerifyResponse(
            organization_id=org.id,
            organization_name=org.name,
            organization_slug=org.slug,
            email=inv.invited_email,
            role=inv.assigned_role,
            expires_at=inv.expires_at.isoformat(),
            inviter_name=inv.invited_by.full_name if inv.invited_by else None,
            valid=True,
        )

    # 2. Check legacy JWT invite token
    payload, error_reason = decode_invite_token(raw_token)
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
        role="Creator",
        valid=True,
    )


@router.post("/invitations/accept", response_model=SwitchOrganizationResponse)
def accept_invitation(
    payload: AcceptInvitationRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Authenticated endpoint for an existing user to accept an invitation and join an organization.
    Security Invariants:
    - Verifies token validity, expiration, and status.
    - Strictly verifies that the invitation email matches the authenticated user's email.
    - Prevents duplicate memberships.
    - Switches the user's active session to the joined organization.
    """
    raw_token = payload.token.strip()
    token_hash = hash_invitation_token(raw_token)

    inv = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.token_hash == token_hash
    ).first()

    assigned_role = UserRole.CREATOR.value
    target_org_id = None
    invited_by_uid = None

    if inv:
        if inv.status != InvitationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invitation is no longer pending (already accepted or revoked)."
            )
        if inv.is_expired:
            inv.status = InvitationStatus.EXPIRED.value
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invitation link has expired."
            )
        if inv.invited_email and inv.invited_email.lower() != current_user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This invitation was issued for {inv.invited_email}. You are currently signed in as {current_user.email}.",
            )
        target_org_id = inv.organization_id
        assigned_role = inv.assigned_role
        invited_by_uid = inv.invited_by_id
    else:
        # Fallback to legacy JWT invite token
        jwt_payload, err = decode_invite_token(raw_token)
        if not jwt_payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err or "Invalid or expired invitation token."
            )
        if jwt_payload.get("email") and jwt_payload.get("email").lower() != current_user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This invitation was issued for {jwt_payload.get('email')}. You are currently signed in as {current_user.email}.",
            )
        target_org_id = jwt_payload.get("org_id")

    org = db.query(Organization).filter(
        Organization.id == target_org_id,
        Organization.is_active.is_(True)
    ).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found or inactive.")

    # Check for existing membership
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
        else:
            # Reactivate suspended membership
            existing_mem.status = MembershipStatus.ACTIVE.value
            existing_mem.role = assigned_role
            membership = existing_mem
    else:
        # Create new membership
        now = datetime.now(timezone.utc)
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
        inv.status = InvitationStatus.ACCEPTED.value
        inv.accepted_by_id = current_user.id

    # Switch user's active organization
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

    return SwitchOrganizationResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(current_user),
        organization=OrganizationOut.model_validate(org),
        role=assigned_role,
    )


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
                status=inv.status,
                expires_at=inv.expires_at.isoformat(),
                created_at=inv.created_at.isoformat(),
                inviter_name=inv.invited_by.full_name if inv.invited_by else None,
            )
        )
    return results
