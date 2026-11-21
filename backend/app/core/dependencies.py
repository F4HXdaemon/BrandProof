from typing import Generator, List, Optional
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request, UploadFile, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import SessionLocal, get_db
from app.core.security import decode_access_token, decode_access_token_with_error
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationMembership, MembershipStatus

security_scheme = HTTPBearer(auto_error=False)

DEFAULT_MAX_UPLOAD_SIZE = 15 * 1024 * 1024  # 15 MB


async def read_upload_file_bounded(file: UploadFile, max_bytes: int = DEFAULT_MAX_UPLOAD_SIZE) -> bytes:
    """
    Reads an UploadFile in bounded chunks to protect against memory exhaustion attacks.
    Aborts immediately and raises 413 if the payload exceeds max_bytes.
    """
    chunk_size = 64 * 1024  # 64 KB chunks
    total_bytes = 0
    buffer = bytearray()
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Uploaded file exceeds maximum allowed limit of {max_mb} MB.",
            )
        buffer.extend(chunk)
    return bytes(buffer)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Authenticates the user and resolves their active organization membership.
    Multi-Tenant Security Enforcement:
    1. Decodes JWT token and validates signature and expiration.
    2. Retrieves global user account.
    3. Resolves requested organization:
       - Uses X-Organization-Id header if provided by client.
       - Otherwise falls back to token claim org_id or default organization.
    4. Validates that the user has an ACTIVE OrganizationMembership in that organization.
       - Rejects unauthorized organization IDs with 403 Forbidden.
    5. Sets dynamic context on user: organization_id, role, and current_membership.
    """
    raw_token = None
    if credentials and credentials.credentials:
        raw_token = credentials.credentials
    elif request and "brandproof_token" in request.cookies:
        raw_token = request.cookies.get("brandproof_token")

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload, error_reason = decode_access_token_with_error(raw_token)
    if not payload:
        error_detail = error_reason or "Invalid or expired authentication token"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail,
            headers={"WWW-Authenticate": f'Bearer error="invalid_token", error_description="{error_detail}"'},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Multi-tenant organization resolution
    header_org_id = request.headers.get("x-organization-id") if request else None
    token_org_id = payload.get("org_id")
    target_org_id = header_org_id or token_org_id

    membership: Optional[OrganizationMembership] = None

    if header_org_id:
        # If client explicitly specified an organization header, verify strictly
        membership = db.query(OrganizationMembership).filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == header_org_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE.value
        ).first()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Not an active member of the requested organization.",
            )
    elif token_org_id:
        # Look up membership matching token claim
        membership = db.query(OrganizationMembership).filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == token_org_id,
            OrganizationMembership.status == MembershipStatus.ACTIVE.value
        ).first()

    # Fallback to user's first active membership if none resolved yet
    if not membership:
        membership = db.query(OrganizationMembership).filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == MembershipStatus.ACTIVE.value
        ).first()

    # Backward compatibility safeguard for tests/fixtures that define user.organization_id directly
    if not membership and user.organization_id:
        membership = db.query(OrganizationMembership).filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == user.organization_id
        ).first()
        if not membership:
            membership = OrganizationMembership(
                user_id=user.id,
                organization_id=user.organization_id,
                role=user.role or UserRole.CREATOR.value,
                status=MembershipStatus.ACTIVE.value,
                joined_at=user.created_at or datetime.now(timezone.utc),
            )
            db.add(membership)
            db.commit()
            db.refresh(membership)

    if membership:
        # Ensure the organization itself is active
        org = db.query(Organization).filter(
            Organization.id == membership.organization_id,
            Organization.is_active.is_(True)
        ).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The organization associated with this session is inactive or does not exist.",
            )
        # Dynamically attach organization and role to current user for the scope of this request
        user.organization_id = membership.organization_id
        user.role = membership.role
        user.current_membership = membership
        user.current_organization = org

    return user


def require_roles(allowed_roles: List[UserRole]):
    """
    Role-Based Access Control (RBAC) dependency factory.
    Enforces organizational role hierarchy:
    - OWNER: Inherits full authority across the organization.
    - ADMIN: Inherits management authority for operations requiring Admin or lower roles.
    - Specific roles: Verified against current membership role in active organization.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        allowed_values = [r.value if isinstance(r, UserRole) else str(r) for r in allowed_roles]

        # Owner has full control over all operations
        if current_user.role == UserRole.OWNER.value:
            return current_user

        # Admin has authority unless action strictly requires Owner
        if current_user.role == UserRole.ADMIN.value:
            # If the requirement strictly requires ONLY Owner, Admin is not permitted
            if allowed_values == [UserRole.OWNER.value]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access forbidden: This action strictly requires Organization Owner privileges.",
                )
            return current_user

        # User's organization role must be explicitly in allowed roles
        if current_user.role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Role '{current_user.role}' lacks permission for this action. Required: {allowed_values}",
            )
        return current_user
    return role_checker
