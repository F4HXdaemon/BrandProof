import enum
from sqlalchemy import Column, String, Text, Float, Integer, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import BaseModelMixin, utc_now
from app.models.knowledge import SeverityLevel


class ReviewStatus(str, enum.Enum):
    DRAFT = "Draft"
    PENDING = "Pending"
    PROCESSING = "Processing"
    IN_PROGRESS = "In Progress"
    NEEDS_REVIEW = "Needs Review"
    CHANGES_REQUESTED = "Changes Requested"
    READY_FOR_APPROVAL = "Ready for Approval"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    FAILED = "Failed"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            mapping = {
                "draft": cls.DRAFT,
                "pending": cls.PENDING,
                "processing": cls.PROCESSING,
                "in progress": cls.IN_PROGRESS,
                "in_progress": cls.IN_PROGRESS,
                "needs review": cls.NEEDS_REVIEW,
                "needs_review": cls.NEEDS_REVIEW,
                "changes requested": cls.CHANGES_REQUESTED,
                "changes_requested": cls.CHANGES_REQUESTED,
                "ready for approval": cls.READY_FOR_APPROVAL,
                "ready_for_approval": cls.READY_FOR_APPROVAL,
                "approved": cls.APPROVED,
                "rejected": cls.REJECTED,
                "failed": cls.FAILED,
            }
            mapped = mapping.get(value.strip().lower())
            if mapped:
                return mapped
        return super()._missing_(value)


class ClaimStatus(str, enum.Enum):
    SUPPORTED = "SUPPORTED"
    CONFLICTS = "CONFLICTS"
    EXPIRED = "EXPIRED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UNSUPPORTED = "UNSUPPORTED"
    # Legacy aliases
    PROPOSED = "UNSUPPORTED"
    VERIFIED = "SUPPORTED"
    UNVERIFIED = "UNSUPPORTED"
    DISPUTED = "CONFLICTS"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            mapping = {
                "supported": cls.SUPPORTED,
                "conflicts": cls.CONFLICTS,
                "conflict": cls.CONFLICTS,
                "expired": cls.EXPIRED,
                "out_of_scope": cls.OUT_OF_SCOPE,
                "out of scope": cls.OUT_OF_SCOPE,
                "unsupported": cls.UNSUPPORTED,
                "proposed": cls.UNSUPPORTED,
                "verified": cls.SUPPORTED,
                "unverified": cls.UNSUPPORTED,
                "disputed": cls.CONFLICTS,
            }
            mapped = mapping.get(value.strip().lower())
            if mapped:
                return mapped
        return super()._missing_(value)


class FindingStatus(str, enum.Enum):
    OPEN = "Open"
    ACCEPTED = "Accepted"
    DISMISSED = "Dismissed"
    FIXED = "Fixed"
    RESOLVED = "Resolved"
    WAIVED = "Waived"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            mapping = {
                "open": cls.OPEN,
                "accepted": cls.ACCEPTED,
                "dismissed": cls.DISMISSED,
                "fixed": cls.FIXED,
                "resolved": cls.RESOLVED,
                "waived": cls.WAIVED,
            }
            mapped = mapping.get(value.strip().lower())
            if mapped:
                return mapped
        return super()._missing_(value)


class ApprovalDecision(str, enum.Enum):
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CHANGES_REQUESTED = "Changes Requested"


class Review(Base, BaseModelMixin):
    __tablename__ = "reviews"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id = Column(String(36), ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True)
    reviewer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    status = Column(String(50), default=ReviewStatus.NEEDS_REVIEW.value, nullable=False, index=True)
    title = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    intent_card = Column(JSON, default=dict, nullable=False)

    product = Column(String(100), nullable=True, index=True)
    region = Column(String(100), nullable=True, index=True)
    channel = Column(String(100), nullable=True, index=True)
    content_type = Column(String(100), nullable=True)
    intended_audience = Column(String(255), nullable=True)
    purpose = Column(Text, nullable=True)

    risk_score = Column(Float, default=0.0, nullable=False)
    risk_level = Column(String(50), default="Low", nullable=False)
    processing_status = Column(String(50), default="Ready", nullable=False, index=True)
    error_message = Column(Text, nullable=True)

    claims_count = Column(Float, default=0)
    findings_count = Column(Float, default=0)

    # Relationships
    organization = relationship("Organization", back_populates="reviews")
    document = relationship("Document", back_populates="reviews")
    version = relationship("DocumentVersion", back_populates="reviews")
    reviewer = relationship("User", back_populates="conducted_reviews", foreign_keys=[reviewer_id])
    claims = relationship("Claim", back_populates="review", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="review", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="review", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="review", cascade="all, delete-orphan")


class Claim(Base, BaseModelMixin):
    __tablename__ = "claims"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    document_version_id = Column(String(36), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=True, index=True)

    text = Column(Text, nullable=False)
    claim_text = Column(Text, nullable=True)
    normalized_claim = Column(Text, nullable=True)
    location_metadata = Column(JSON, default=dict, nullable=False)  # paragraph, page, sentence index
    page_number = Column(Integer, nullable=True)
    paragraph_number = Column(Integer, nullable=True)
    claim_type = Column(String(50), default="General factual", nullable=False)  # Numeric, Certification, Product capability, Comparative, Superlative, Guarantee, General factual
    confidence = Column(Float, default=1.0, nullable=False)
    status = Column(String(50), default=ClaimStatus.UNSUPPORTED.value, nullable=False, index=True)
    matched_fact_id = Column(String(36), ForeignKey("facts.id", ondelete="SET NULL"), nullable=True)
    reasoning = Column(Text, nullable=True)

    def __init__(self, **kwargs):
        if "claim_text" in kwargs and "text" not in kwargs:
            kwargs["text"] = kwargs["claim_text"]
        elif "text" in kwargs and "claim_text" not in kwargs:
            kwargs["claim_text"] = kwargs["text"]
        super().__init__(**kwargs)

    # Relationships
    review = relationship("Review", back_populates="claims")
    document = relationship("Document")
    version = relationship("DocumentVersion")
    matched_fact = relationship("Fact", foreign_keys=[matched_fact_id])
    findings = relationship("Finding", back_populates="claim", cascade="all, delete-orphan")


class Finding(Base, BaseModelMixin):
    __tablename__ = "findings"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    document_version_id = Column(String(36), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=True, index=True)
    claim_id = Column(String(36), ForeignKey("claims.id", ondelete="SET NULL"), nullable=True, index=True)

    rule_id = Column(String(36), ForeignKey("rules.id", ondelete="SET NULL"), nullable=True, index=True)
    guideline_id = Column(String(36), ForeignKey("guidelines.id", ondelete="SET NULL"), nullable=True, index=True)
    fact_id = Column(String(36), ForeignKey("facts.id", ondelete="SET NULL"), nullable=True, index=True)

    finding_type = Column(String(50), default="rule_violation", nullable=True)  # terminology, disclaimer, forbidden_phrase, numeric_conflict, expired_fact, regex, tone, accessibility, asset
    severity = Column(String(50), default=SeverityLevel.HIGH.value, nullable=False)
    status = Column(String(50), default=FindingStatus.OPEN.value, nullable=False, index=True)

    title = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)
    quoted_text = Column(Text, nullable=True)
    start_offset = Column(Integer, nullable=True)
    end_offset = Column(Integer, nullable=True)
    page_number = Column(Integer, nullable=True)

    source_type = Column(String(50), default="rule", nullable=True)  # fact, rule, term, guideline, asset
    source_id = Column(String(36), nullable=True, index=True)
    source_reference = Column(String(500), nullable=False)  # CRITICAL RULE: NO VALID SOURCE = NO FINDING

    suggestion = Column(Text, nullable=True)
    suggested_replacement = Column(Text, nullable=True)
    checker = Column(String(100), default="RuleEngine", nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    dismissal_reason = Column(String(255), nullable=True)

    def __init__(self, **kwargs):
        if "suggested_replacement" in kwargs and "suggestion" not in kwargs:
            kwargs["suggestion"] = kwargs["suggested_replacement"]
        elif "suggestion" in kwargs and "suggested_replacement" not in kwargs:
            kwargs["suggested_replacement"] = kwargs["suggestion"]
        super().__init__(**kwargs)

    # Relationships
    review = relationship("Review", back_populates="findings")
    claim = relationship("Claim", back_populates="findings")
    rule = relationship("Rule", back_populates="findings")
    guideline = relationship("Guideline", back_populates="findings")
    fact = relationship("Fact", back_populates="findings")
    comments = relationship("Comment", back_populates="finding", cascade="all, delete-orphan")

    @property
    def suggestion(self) -> str:
        return self.suggested_replacement

    @suggestion.setter
    def suggestion(self, val: str) -> None:
        self.suggested_replacement = val


class Approval(Base, BaseModelMixin):
    __tablename__ = "approvals"

    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    document_version_id = Column(String(36), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=True, index=True)
    approver_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    status = Column(String(50), default=ApprovalDecision.APPROVED.value, nullable=False)
    comments = Column(Text, nullable=True)
    is_override = Column(Boolean, default=False, nullable=False)
    override_reason = Column(Text, nullable=True)
    override_finding_ids = Column(JSON, default=list, nullable=False)
    decided_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    review = relationship("Review", back_populates="approvals")
    document = relationship("Document", back_populates="approvals")
    approver = relationship("User", back_populates="approvals", foreign_keys=[approver_id])


class Comment(Base, BaseModelMixin):
    __tablename__ = "comments"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id = Column(String(36), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True, index=True)
    author_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    text = Column(Text, nullable=False)
    resolved = Column(Boolean, default=False, nullable=False)

    # Relationships
    review = relationship("Review", back_populates="comments")
    finding = relationship("Finding", back_populates="comments")
    author = relationship("User", foreign_keys=[author_id])
