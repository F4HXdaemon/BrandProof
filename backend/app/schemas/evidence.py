from datetime import datetime
from typing import Optional, List, Dict, Any
from app.schemas.common import BaseSchema, TimestampedSchema


class EvidenceBase(BaseSchema):
    title: str
    filename: str
    file_type: str
    file_extension: str
    file_size: int
    file_hash: Optional[str] = None
    sha256_checksum: Optional[str] = None
    status: str = "Uploaded"
    is_expired: bool = False
    validation_errors: Optional[str] = None
    description: Optional[str] = None
    source_reference: Optional[str] = None
    product_scope: str = "All"
    region_scope: str = "Global"
    channel_scope: str = "All"
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class EvidenceOut(EvidenceBase, TimestampedSchema):
    id: str
    organization_id: str
    uploaded_by_id: Optional[str] = None
    uploader_name: Optional[str] = None
    associated_reviews_count: int = 0
    associated_claims_count: int = 0


class EvidenceDetailOut(EvidenceOut):
    extracted_text: Optional[str] = None
    associated_reviews: List[Dict[str, Any]] = []
    supported_claims: List[Dict[str, Any]] = []


class AssociateEvidenceRequest(BaseSchema):
    review_id: str
    relevance_notes: Optional[str] = None
