from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import model_validator
from app.schemas.common import BaseSchema, TimestampedSchema
from app.models.document import DocumentStatus
from app.models.review import (
    ReviewStatus, ClaimStatus, FindingStatus, ApprovalDecision
)
from app.models.knowledge import SeverityLevel


class DocumentChunkOut(TimestampedSchema):
    id: str
    document_version_id: str
    sequence: int
    chunk_type: str = "paragraph"
    text: str
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = {}

    @model_validator(mode="before")
    @classmethod
    def resolve_metadata(cls, data: Any):
        if hasattr(data, "chunk_metadata"):
            return {
                "id": str(data.id),
                "document_version_id": str(data.document_version_id),
                "sequence": data.sequence,
                "chunk_type": data.chunk_type,
                "text": data.text,
                "page_number": data.page_number,
                "metadata": data.chunk_metadata if isinstance(data.chunk_metadata, dict) else {},
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        elif isinstance(data, dict):
            if "chunk_metadata" in data and "metadata" not in data:
                data["metadata"] = data["chunk_metadata"]
        return data


class DocumentBase(BaseSchema):
    title: str
    filename: str
    file_type: str
    product: str = "All Products"
    region: str = "Global"
    channel: str = "Marketing"
    status: DocumentStatus = DocumentStatus.DRAFT
    processing_status: str = "Ready"
    error_message: Optional[str] = None


class DocumentCreate(BaseSchema):
    title: str
    product: Optional[str] = "All Products"
    region: Optional[str] = "Global"
    channel: Optional[str] = "Marketing"


class DocumentVersionOut(TimestampedSchema):
    id: str
    document_id: str
    version_number: int
    file_path: str
    file_size: int
    extracted_text: Optional[str] = None
    error_message: Optional[str] = None
    created_by_id: Optional[str] = None
    chunks: List[DocumentChunkOut] = []


class DocumentOut(DocumentBase, TimestampedSchema):
    organization_id: str
    creator_id: Optional[str] = None
    creator_name: Optional[str] = None
    file_path: str
    file_size: int
    versions: List[DocumentVersionOut] = []


class ClaimBase(BaseSchema):
    text: Optional[str] = None
    claim_text: Optional[str] = None
    claim_type: str = "General factual"
    location_metadata: Dict[str, Any] = {}
    page_number: Optional[int] = 1
    paragraph_number: Optional[int] = 1
    confidence: float = 1.0
    status: ClaimStatus = ClaimStatus.UNSUPPORTED
    matched_fact_id: Optional[str] = None
    reasoning: Optional[str] = None


class ClaimCreate(ClaimBase):
    review_id: str
    document_id: str


class ClaimOut(ClaimBase, TimestampedSchema):
    review_id: str
    document_id: str


class FindingBase(BaseSchema):
    finding_type: Optional[str] = "rule_violation"
    severity: SeverityLevel
    title: Optional[str] = None
    message: str
    suggestion: Optional[str] = None
    suggested_replacement: Optional[str] = None
    quoted_text: Optional[str] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    page_number: Optional[int] = 1
    source_type: Optional[str] = "rule"
    source_id: Optional[str] = None
    source_reference: str  # Critical requirement: NO VALID SOURCE = NO FINDING
    checker: Optional[str] = "RuleEngine"
    confidence: float = 1.0
    dismissal_reason: Optional[str] = None
    status: FindingStatus = FindingStatus.OPEN


class FindingCreate(FindingBase):
    review_id: str
    claim_id: Optional[str] = None
    rule_id: Optional[str] = None
    guideline_id: Optional[str] = None
    fact_id: Optional[str] = None


class FindingOut(FindingBase, TimestampedSchema):
    review_id: str
    claim_id: Optional[str] = None
    rule_id: Optional[str] = None
    guideline_id: Optional[str] = None
    fact_id: Optional[str] = None
    claim_text: Optional[str] = None


class ApprovalCreate(BaseSchema):
    status: ApprovalDecision
    comments: Optional[str] = None
    is_override: bool = False
    override_reason: Optional[str] = None


class ApprovalOut(TimestampedSchema):
    review_id: str
    document_id: str
    approver_id: Optional[str] = None
    approver_name: Optional[str] = None
    status: ApprovalDecision
    comments: Optional[str] = None
    is_override: bool = False
    override_reason: Optional[str] = None
    override_finding_ids: List[str] = []
    decided_at: datetime


class CommentCreate(BaseSchema):
    text: str
    finding_id: Optional[str] = None


class CommentOut(TimestampedSchema):
    organization_id: str
    review_id: str
    finding_id: Optional[str] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    text: str
    resolved: bool = False


class ReviewBase(BaseSchema):
    title: Optional[str] = None
    status: ReviewStatus = ReviewStatus.PENDING
    summary: Optional[str] = None
    product: Optional[str] = None
    region: Optional[str] = None
    channel: Optional[str] = None
    content_type: Optional[str] = None
    intended_audience: Optional[str] = None
    purpose: Optional[str] = None
    intent_card: Dict[str, Any] = {}
    risk_score: float = 0.0
    risk_level: str = "Low"
    processing_status: str = "Ready"
    error_message: Optional[str] = None


class ReviewCreate(BaseSchema):
    document_id: str
    version_id: Optional[str] = None
    reviewer_id: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    product: Optional[str] = "All"
    region: Optional[str] = "Global"
    channel: Optional[str] = "All"
    content_type: Optional[str] = "General"
    intended_audience: Optional[str] = "General"
    purpose: Optional[str] = None
    intent_card: Optional[Dict[str, Any]] = None


class ReviewOut(ReviewBase, TimestampedSchema):
    organization_id: str
    document_id: str
    version_id: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = None
    creator_name: Optional[str] = None
    document_title: Optional[str] = None
    document_status: Optional[str] = None
    claims_count: float = 0
    findings_count: float = 0


class ReviewDetailOut(ReviewOut):
    document: Optional[DocumentOut] = None
    version: Optional[DocumentVersionOut] = None
    claims: List[ClaimOut] = []
    findings: List[FindingOut] = []
    approvals: List[ApprovalOut] = []
    comments: List[CommentOut] = []


class AcceptFixRequest(BaseSchema):
    finding_id: str
    replacement_text: Optional[str] = None


class DismissFindingRequest(BaseSchema):
    finding_id: str
    dismissal_reason: str



class AuditEventOut(BaseSchema):
    id: str
    organization_id: str
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    metadata: Dict[str, Any]
    timestamp: datetime
