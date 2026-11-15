import enum
from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import BaseModelMixin


class UserRole(str, enum.Enum):
    CREATOR = "Creator"
    REVIEWER = "Reviewer"
    BRAND_MANAGER = "Brand Manager"
    FACT_OWNER = "Fact Owner"
    ADMIN = "Admin"


class User(Base, BaseModelMixin):
    __tablename__ = "users"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default=UserRole.CREATOR.value, nullable=False, index=True)
    title = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="users")
    owned_facts = relationship("Fact", back_populates="owner", foreign_keys="Fact.owner_id")
    created_documents = relationship("Document", back_populates="creator", foreign_keys="Document.creator_id")
    conducted_reviews = relationship("Review", back_populates="reviewer", foreign_keys="Review.reviewer_id")
    approvals = relationship("Approval", back_populates="approver", foreign_keys="Approval.approver_id")
    audit_events = relationship("AuditEvent", back_populates="actor", foreign_keys="AuditEvent.actor_id")
