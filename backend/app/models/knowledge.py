from datetime import datetime, timezone
import enum
from typing import Optional
from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime, JSON, Float, Integer
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import BaseModelMixin, utc_now


class FactStatus(str, enum.Enum):
    APPROVED = "Approved"
    DRAFT = "Draft"
    EXPIRED = "Expired"
    ARCHIVED = "Archived"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            mapping = {
                "approved": cls.APPROVED,
                "active": cls.APPROVED,
                "draft": cls.DRAFT,
                "expired": cls.EXPIRED,
                "archived": cls.ARCHIVED,
                "deprecated": cls.ARCHIVED,
                "expiring": cls.APPROVED,
            }
            mapped = mapping.get(value.strip().lower())
            if mapped:
                return mapped
        return super()._missing_(value)


class SeverityLevel(str, enum.Enum):
    BLOCKER = "Blocker"
    HIGH = "High"
    WARNING = "Warning"
    INFO = "Info"
    # Legacy attribute aliases
    CRITICAL = "Blocker"
    MEDIUM = "Warning"
    LOW = "Info"
    ADVISORY = "Info"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            mapping = {
                "blocker": cls.BLOCKER,
                "critical": cls.BLOCKER,
                "high": cls.HIGH,
                "warning": cls.WARNING,
                "medium": cls.WARNING,
                "info": cls.INFO,
                "low": cls.INFO,
                "advisory": cls.INFO,
            }
            mapped = mapping.get(value.strip().lower())
            if mapped:
                return mapped
        return super()._missing_(value)


class RuleType(str, enum.Enum):
    TERM_CHECK = "TERM_CHECK"
    REQUIRED_DISCLAIMER = "REQUIRED_DISCLAIMER"
    FORBIDDEN_PHRASE = "FORBIDDEN_PHRASE"
    EXACT_VALUE = "EXACT_VALUE"
    EXPIRY_CHECK = "EXPIRY_CHECK"
    REGEX = "REGEX"
    ACCESSIBILITY = "ACCESSIBILITY"
    CUSTOM = "CUSTOM"


class Fact(Base, BaseModelMixin):
    __tablename__ = "facts"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(255), nullable=False, index=True)
    canonical_value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    source_reference = Column(String(500), nullable=False)  # Every claim, traced to its source

    product_scope = Column(String(100), default="All", nullable=False, index=True)
    region_scope = Column(String(100), default="Global", nullable=False, index=True)
    channel_scope = Column(String(100), default="All", nullable=False, index=True)

    valid_from = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    status = Column(String(50), default=FactStatus.APPROVED.value, nullable=False, index=True)

    # Relationships
    organization = relationship("Organization", back_populates="facts")
    owner = relationship("User", back_populates="owned_facts", foreign_keys=[owner_id])
    findings = relationship("Finding", back_populates="fact")

    @property
    def is_expired(self) -> bool:
        if self.expires_at:
            now = datetime.now(timezone.utc)
            exp = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
            return exp < now
        return False

    @property
    def effective_status(self) -> str:
        """Dynamic resolution of fact status based on expiration date."""
        if self.status == FactStatus.ARCHIVED.value:
            return FactStatus.ARCHIVED.value
        if self.status == FactStatus.DRAFT.value:
            return FactStatus.DRAFT.value
        if self.is_expired:
            return FactStatus.EXPIRED.value
        return FactStatus.APPROVED.value


class Guideline(Base, BaseModelMixin):
    __tablename__ = "guidelines"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)  # Brand Voice, Claims, Legal, Product, Accessibility, Visual, Regional
    severity = Column(String(50), default=SeverityLevel.HIGH.value, nullable=False)

    product_scope = Column(String(100), default="All", nullable=False, index=True)
    region_scope = Column(String(100), default="Global", nullable=False, index=True)
    channel_scope = Column(String(100), default="All", nullable=False, index=True)

    principle = Column(String(255), nullable=True)
    do_examples = Column(JSON, default=list, nullable=False)
    dont_examples = Column(JSON, default=list, nullable=False)

    source_reference = Column(String(500), nullable=True)
    status = Column(String(50), default="Approved", nullable=False, index=True)
    active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    organization = relationship("Organization", back_populates="guidelines")
    findings = relationship("Finding", back_populates="guideline")

    @property
    def name(self) -> str:
        return self.title


class Term(Base, BaseModelMixin):
    __tablename__ = "terms"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    approved_term = Column(String(255), nullable=False, index=True)
    disallowed_variants = Column(JSON, default=list, nullable=False)  # JSON list of unacceptable variants
    replacement = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    product_scope = Column(String(100), default="All", nullable=False, index=True)
    region_scope = Column(String(100), default="Global", nullable=False, index=True)
    channel_scope = Column(String(100), default="All", nullable=False, index=True)

    status = Column(String(50), default="Approved", nullable=False, index=True)
    active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    organization = relationship("Organization", back_populates="terms")

    @property
    def term(self) -> str:
        return self.approved_term

    @property
    def case_sensitive(self) -> bool:
        return True

    @property
    def source_reference(self) -> str:
        return self.notes or f"Brand Terminology: {self.approved_term}"


class Rule(Base, BaseModelMixin):
    __tablename__ = "rules"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    rule_type = Column(String(100), default=RuleType.TERM_CHECK.value, nullable=False, index=True)
    severity = Column(String(50), default=SeverityLevel.BLOCKER.value, nullable=False)
    configuration = Column(JSON, default=dict, nullable=False)  # Config specs for rule validator
    source_reference = Column(String(500), nullable=True)

    product_scope = Column(String(100), default="All", nullable=False, index=True)
    region_scope = Column(String(100), default="Global", nullable=False, index=True)
    channel_scope = Column(String(100), default="All", nullable=False, index=True)

    status = Column(String(50), default="Approved", nullable=False, index=True)
    active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    organization = relationship("Organization", back_populates="rules")
    findings = relationship("Finding", back_populates="rule")

    @property
    def config(self) -> dict:
        return self.configuration or {}


class ApprovedAsset(Base, BaseModelMixin):
    __tablename__ = "approved_assets"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    asset_type = Column(String(50), default="logo", nullable=False)  # logo, badge, watermark
    file_path = Column(String(500), nullable=True)
    expected_width = Column(Float, nullable=True)
    expected_height = Column(Float, nullable=True)
    aspect_ratio = Column(Float, nullable=True)  # width / height
    allowed_ratio_deviation = Column(Float, default=0.05, nullable=False)  # 5% margin
    source_reference = Column(String(500), nullable=True)

    product_scope = Column(String(100), default="All", nullable=False, index=True)
    region_scope = Column(String(100), default="Global", nullable=False, index=True)
    channel_scope = Column(String(100), default="All", nullable=False, index=True)

    status = Column(String(50), default="Approved", nullable=False, index=True)
    active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    organization = relationship("Organization")
