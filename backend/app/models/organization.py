import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import BaseModelMixin, utc_now
from app.models.user import UserRole


class MembershipStatus(str, enum.Enum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"


class InvitationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class Organization(Base, BaseModelMixin):
    __tablename__ = "organizations"

    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    domain = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL", use_alter=True), nullable=True, index=True)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    users = relationship("User", back_populates="organization", foreign_keys="User.organization_id", cascade="all, delete-orphan")
    memberships = relationship("OrganizationMembership", back_populates="organization", cascade="all, delete-orphan", foreign_keys="OrganizationMembership.organization_id")
    invitations = relationship("OrganizationInvitation", back_populates="organization", cascade="all, delete-orphan", foreign_keys="OrganizationInvitation.organization_id")
    facts = relationship("Fact", back_populates="organization", cascade="all, delete-orphan")
    guidelines = relationship("Guideline", back_populates="organization", cascade="all, delete-orphan")
    terms = relationship("Term", back_populates="organization", cascade="all, delete-orphan")
    rules = relationship("Rule", back_populates="organization", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="organization", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="organization", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="organization", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="organization", cascade="all, delete-orphan")


class OrganizationMembership(Base, BaseModelMixin):
    """
    Organization-specific membership mapping a global User account to an Organization
    with a distinct role, status, and joined timestamp.
    """
    __tablename__ = "organization_memberships"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default=UserRole.CREATOR.value, nullable=False, index=True)
    status = Column(String(50), default=MembershipStatus.ACTIVE.value, nullable=False, index=True)
    joined_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    invited_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_user_organization"),
    )

    # Relationships
    user = relationship("User", back_populates="memberships", foreign_keys=[user_id])
    organization = relationship("Organization", back_populates="memberships", foreign_keys=[organization_id])
    invited_by = relationship("User", foreign_keys=[invited_by_id])


class OrganizationInvitation(Base, BaseModelMixin):
    """
    Cryptographically secure invitations allowing existing or new users to join
    an organization with a pre-assigned role.
    """
    __tablename__ = "organization_invitations"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    invited_email = Column(String(255), nullable=True, index=True)
    assigned_role = Column(String(50), default=UserRole.CREATOR.value, nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(50), default=InvitationStatus.PENDING.value, nullable=False, index=True)
    invited_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    accepted_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    organization = relationship("Organization", back_populates="invitations", foreign_keys=[organization_id])
    invited_by = relationship("User", foreign_keys=[invited_by_id], overlaps="invitations_sent")
    accepted_by = relationship("User", foreign_keys=[accepted_by_id], overlaps="invitations_accepted")

    @property
    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        exp = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        return exp < now
