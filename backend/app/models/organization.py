from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import BaseModelMixin


class Organization(Base, BaseModelMixin):
    __tablename__ = "organizations"

    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    domain = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    facts = relationship("Fact", back_populates="organization", cascade="all, delete-orphan")
    guidelines = relationship("Guideline", back_populates="organization", cascade="all, delete-orphan")
    terms = relationship("Term", back_populates="organization", cascade="all, delete-orphan")
    rules = relationship("Rule", back_populates="organization", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="organization", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="organization", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="organization", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="organization", cascade="all, delete-orphan")
