from typing import Optional, List
from datetime import datetime
from pydantic import EmailStr, field_validator
from app.schemas.common import BaseSchema, TimestampedSchema
from app.models.user import UserRole


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str
    remember_me: bool = False

    @field_validator("password")
    @classmethod
    def validate_password_limit(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 bytes.")
        return v


class TokenResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class RegisterRequest(BaseSchema):
    organization_name: Optional[str] = None
    organization_slug: Optional[str] = None
    email: EmailStr
    password: str
    full_name: str
    role: Optional[UserRole] = None
    invite_token: Optional[str] = None
    remember_me: bool = False

    @field_validator("organization_name")
    @classmethod
    def validate_org_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if len(s) < 2:
                raise ValueError("Organization name must be at least 2 characters long.")
            return s
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 2:
            raise ValueError("Full name must be at least 2 characters long.")
        return s

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 bytes.")
        return v


class InviteCreateRequest(BaseSchema):
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = UserRole.CREATOR
    allowed_roles: Optional[List[UserRole]] = None
    expires_in_days: int = 7
    max_uses: int = 1
    requires_approval: bool = False


class InviteResponse(BaseSchema):
    invite_token: str
    invitation_code: Optional[str] = None
    organization_id: str
    organization_name: str
    organization_slug: str
    email: Optional[str] = None
    role: Optional[str] = None
    allowed_roles: List[str] = []
    expires_at: str
    max_uses: int = 1
    use_count: int = 0
    requires_approval: bool = False
    invite_url: Optional[str] = None


class InviteVerifyResponse(BaseSchema):
    organization_id: str
    organization_name: str
    organization_slug: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    allowed_roles: List[str] = []
    expires_at: Optional[str] = None
    max_uses: int = 1
    use_count: int = 0
    requires_approval: bool = False
    inviter_name: Optional[str] = None
    valid: bool = True


class AcceptInvitationRequest(BaseSchema):
    token: str
    role: Optional[UserRole] = None


class ValidateInvitationRequest(BaseSchema):
    code: str


class JoinInvitationRequest(BaseSchema):
    code: str
    role: Optional[UserRole] = None


class JoinInvitationResponse(BaseSchema):
    status: str  # "active" | "pending_approval"
    message: str
    access_token: Optional[str] = None
    token_type: Optional[str] = "bearer"
    user: Optional["UserOut"] = None
    organization: Optional["OrganizationOut"] = None
    role: Optional[str] = None


class MembershipRequestApprovalRequest(BaseSchema):
    role: Optional[UserRole] = None


class SwitchOrganizationRequest(BaseSchema):
    organization_id: str


class SwitchOrganizationResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"
    organization: "OrganizationOut"
    role: str


class UserOrganizationOut(BaseSchema):
    id: str
    name: str
    slug: str
    domain: Optional[str] = None
    role: str
    is_current: bool = False
    is_owner: bool = False
    joined_at: str


class OrganizationMembershipOut(BaseSchema):
    id: str
    user_id: str
    full_name: str
    email: str
    role: str
    title: Optional[str] = None
    avatar_url: Optional[str] = None
    status: str
    joined_at: str
    is_owner: bool = False


class MemberRoleUpdateRequest(BaseSchema):
    role: UserRole


class TransferOwnershipRequest(BaseSchema):
    new_owner_user_id: str


class OrganizationInvitationOut(BaseSchema):
    id: str
    organization_id: str
    organization_name: Optional[str] = None
    organization_slug: Optional[str] = None
    invited_email: Optional[str] = None
    assigned_role: str
    allowed_roles: List[str] = []
    invitation_code: Optional[str] = None
    status: str
    expires_at: str
    created_at: str
    max_uses: int = 1
    use_count: int = 0
    requires_approval: bool = False
    inviter_name: Optional[str] = None
    invite_url: Optional[str] = None
    invite_token: Optional[str] = None


class UserBase(BaseSchema):
    email: EmailStr
    full_name: str
    role: Optional[UserRole] = None
    title: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    onboarding_completed: bool = False


class OnboardingUpdatePayload(BaseSchema):
    onboarding_completed: bool = True


class UserCreate(UserBase):
    password: str
    organization_id: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 bytes.")
        return v


class UserUpdate(BaseSchema):
    full_name: Optional[str] = None
    title: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    avatar_url: Optional[str] = None
    onboarding_completed: Optional[bool] = None


class UserOut(UserBase, TimestampedSchema):
    organization_id: Optional[str] = None


class OrganizationBase(BaseSchema):
    name: str
    slug: str
    domain: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: bool = True
    owner_id: Optional[str] = None


class OrganizationCreate(BaseSchema):
    name: str
    slug: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None


class OrganizationUpdate(BaseSchema):
    name: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None


class OrganizationOut(OrganizationBase, TimestampedSchema):
    pass


TokenResponse.model_rebuild()
SwitchOrganizationResponse.model_rebuild()
JoinInvitationResponse.model_rebuild()
