from datetime import datetime, timezone
import enum
from typing import Optional
from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import BaseModelMixin


class EvidenceStatus(str, enum.Enum):
    UPLOADED = "Uploaded"
    PROCESSING = "Processing"
    VALIDATED = "Validated"
    INVALID = "Invalid"
    EXPIRED = "Expired"
    REJECTED = "Rejected"
    UNAVAILABLE = "Unavailable"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            mapping = {
                "uploaded": cls.UPLOADED,
                "processing": cls.PROCESSING,
                "validated": cls.VALIDATED,
                "valid": cls.VALIDATED,
                "invalid": cls.INVALID,
                "expired": cls.EXPIRED,
                "rejected": cls.REJECTED,
                "unavailable": cls.UNAVAILABLE,
            }
            mapped = mapping.get(value.strip().lower())
            if mapped:
                return mapped
        return super()._missing_(value)


class Evidence(Base, BaseModelMixin):
    __tablename__ = "evidence"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(255), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=False)
    file_extension = Column(String(20), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0, nullable=False)
    file_hash = Column(String(64), nullable=True)

    status = Column(String(50), default=EvidenceStatus.UPLOADED.value, nullable=False, index=True)
    validation_errors = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    source_reference = Column(String(500), nullable=True)

    product_scope = Column(String(100), default="All", nullable=False, index=True)
    region_scope = Column(String(100), default="Global", nullable=False, index=True)
    channel_scope = Column(String(100), default="All", nullable=False, index=True)

    valid_from = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    organization = relationship("Organization", back_populates="evidence")
    uploaded_by = relationship("User", back_populates="uploaded_evidence", foreign_keys=[uploaded_by_id])
    review_associations = relationship("ReviewEvidence", back_populates="evidence", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="evidence")

    @property
    def is_expired(self) -> bool:
        if self.expires_at:
            now = datetime.now(timezone.utc)
            exp = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
            return exp < now
        return False

    @property
    def mime_type(self) -> str:
        return self.file_type

    @property
    def storage_path(self) -> str:
        return self.file_path

    @property
    def sha256_checksum(self) -> Optional[str]:
        return self.file_hash

    @property
    def effective_status(self) -> str:
        """Dynamic resolution of evidence status."""
        if self.status in [EvidenceStatus.INVALID.value, EvidenceStatus.REJECTED.value, EvidenceStatus.UNAVAILABLE.value]:
            return self.status
        if self.is_expired:
            return EvidenceStatus.EXPIRED.value
        return self.status


class ReviewEvidence(Base, BaseModelMixin):
    __tablename__ = "review_evidence"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(String(36), ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    relevance_notes = Column(Text, nullable=True)

    # Relationships
    review = relationship("Review", back_populates="evidence_associations")
    evidence = relationship("Evidence", back_populates="review_associations")
