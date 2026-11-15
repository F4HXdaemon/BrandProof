from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    action = Column(String(100), nullable=False, index=True)  # e.g., FACT_CREATED, DOCUMENT_UPLOADED, REVIEW_DECISION
    entity_type = Column(String(100), nullable=False, index=True)  # Fact, Document, Review, Approval, User, etc.
    entity_id = Column(String(36), nullable=False, index=True)
    event_metadata = Column("metadata", JSON, default=dict, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # Relationships
    organization = relationship("Organization", back_populates="audit_events")
    actor = relationship("User", back_populates="audit_events", foreign_keys=[actor_id])
