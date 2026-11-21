from typing import Optional, List
from datetime import datetime
from pydantic import EmailStr, field_validator
from app.schemas.common import BaseSchema, TimestampedSchema
from app.models.user import UserRole


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str

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
    expires_in_days: int = 7


class InviteResponse(BaseSchema):
    invite_token: str
    organization_id: str
    organization_name: str
    organization_slug: str
    email: Optional[str] = None
    role: Optional[str] = None
    expires_at: str
    invite_url: Optional[str] = None


class InviteVerifyResponse(BaseSchema):
    organization_id: str
    organization_name: str
    organization_slug: str
    email: Optional[str] = None
    role: Optional[str] = None
    expires_at: Optional[str] = None
    inviter_name: Optional[str] = None
    valid: bool = True


class AcceptInvitationRequest(BaseSchema):
    token: str


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
    invited_email: str
    assigned_role: str
    status: str
    expires_at: str
    created_at: str
    inviter_name: Optional[str] = None
    invite_url: Optional[str] = None
    invite_token: Optional[str] = None


class UserBase(BaseSchema):
    email: EmailStr
    full_name: str
    role: UserRole
    title: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str
    organization_id: str

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


class UserOut(UserBase, TimestampedSchema):
    organization_id: str


class OrganizationBase(BaseSchema):
    name: str
    slug: str
    domain: Optional[str] = None
    is_active: bool = True
    owner_id: Optional[str] = None


class OrganizationCreate(BaseSchema):
    name: str
    slug: Optional[str] = None
    domain: Optional[str] = None


class OrganizationUpdate(BaseSchema):
    name: Optional[str] = None
    domain: Optional[str] = None
    is_active: Optional[bool] = None


class OrganizationOut(OrganizationBase, TimestampedSchema):
    pass


TokenResponse.model_rebuild()
SwitchOrganizationResponse.model_rebuild()
