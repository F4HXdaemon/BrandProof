from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import model_validator
from app.schemas.common import BaseSchema, TimestampedSchema
from app.models.knowledge import FactStatus, SeverityLevel, RuleType


class FactBase(BaseSchema):
    title: str
    canonical_value: str
    description: Optional[str] = None
    source_reference: str
    product_scope: str = "All"
    region_scope: str = "Global"
    channel_scope: str = "All"
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    status: FactStatus = FactStatus.APPROVED


class FactCreate(FactBase):
    owner_id: Optional[str] = None


class FactUpdate(BaseSchema):
    title: Optional[str] = None
    canonical_value: Optional[str] = None
    description: Optional[str] = None
    source_reference: Optional[str] = None
    owner_id: Optional[str] = None
    product_scope: Optional[str] = None
    region_scope: Optional[str] = None
    channel_scope: Optional[str] = None
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    status: Optional[FactStatus] = None


class FactOut(FactBase, TimestampedSchema):
    organization_id: str
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    is_expired: bool = False
    effective_status: str = "Approved"
    days_until_expiry: Optional[int] = None


class GuidelineBase(BaseSchema):
    title: str
    description: str
    category: str
    severity: SeverityLevel = SeverityLevel.HIGH
    product_scope: str = "All"
    region_scope: str = "Global"
    channel_scope: str = "All"
    source_reference: Optional[str] = None
    status: str = "Approved"
    active: bool = True


class GuidelineCreate(GuidelineBase):
    pass


class GuidelineUpdate(BaseSchema):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[SeverityLevel] = None
    product_scope: Optional[str] = None
    region_scope: Optional[str] = None
    channel_scope: Optional[str] = None
    source_reference: Optional[str] = None
    status: Optional[str] = None
    active: Optional[bool] = None


class GuidelineOut(GuidelineBase, TimestampedSchema):
    organization_id: str


class TermBase(BaseSchema):
    approved_term: str
    disallowed_variants: List[str] = []
    replacement: Optional[str] = None
    notes: Optional[str] = None
    product_scope: str = "All"
    region_scope: str = "Global"
    channel_scope: str = "All"
    status: str = "Approved"
    active: bool = True

    @model_validator(mode="before")
    @classmethod
    def handle_term_alias(cls, data: Any):
        if isinstance(data, dict):
            if "term" in data and "approved_term" not in data:
                data["approved_term"] = data["term"]
        return data


class TermCreate(TermBase):
    pass


class TermUpdate(BaseSchema):
    approved_term: Optional[str] = None
    disallowed_variants: Optional[List[str]] = None
    replacement: Optional[str] = None
    notes: Optional[str] = None
    product_scope: Optional[str] = None
    region_scope: Optional[str] = None
    channel_scope: Optional[str] = None
    status: Optional[str] = None
    active: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def handle_term_alias(cls, data: Any):
        if isinstance(data, dict):
            if "term" in data and "approved_term" not in data:
                data["approved_term"] = data["term"]
        return data


class TermOut(TermBase, TimestampedSchema):
    organization_id: str
    term: Optional[str] = None

    @model_validator(mode="after")
    def sync_term(self):
        self.term = self.approved_term
        return self


class RuleBase(BaseSchema):
    name: str
    description: str
    rule_type: RuleType = RuleType.TERM_CHECK
    severity: SeverityLevel = SeverityLevel.BLOCKER
    configuration: Dict[str, Any] = {}
    source_reference: Optional[str] = None
    product_scope: str = "All"
    region_scope: str = "Global"
    channel_scope: str = "All"
    status: str = "Approved"
    active: bool = True

    @model_validator(mode="before")
    @classmethod
    def handle_config_alias(cls, data: Any):
        if isinstance(data, dict):
            if "config" in data and "configuration" not in data:
                data["configuration"] = data["config"]
        return data


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseSchema):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[RuleType] = None
    severity: Optional[SeverityLevel] = None
    configuration: Optional[Dict[str, Any]] = None
    source_reference: Optional[str] = None
    product_scope: Optional[str] = None
    region_scope: Optional[str] = None
    channel_scope: Optional[str] = None
    status: Optional[str] = None
    active: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def handle_config_alias(cls, data: Any):
        if isinstance(data, dict):
            if "config" in data and "configuration" not in data:
                data["configuration"] = data["config"]
        return data


class RuleOut(RuleBase, TimestampedSchema):
    organization_id: str
    config: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def sync_config(self):
        self.config = self.configuration
        return self


class ApplicableKnowledgeResponse(BaseSchema):
    scopes: Dict[str, str]
    counts: Dict[str, int]
    facts: List[FactOut]
    guidelines: List[GuidelineOut]
    terms: List[TermOut]
    rules: List[RuleOut]
    expired_facts_excluded: List[FactOut] = []


class CsvImportResponse(BaseSchema):
    imported_count: int
    total_attempted: int
    errors: List[str] = []
    failed_count: int = 0
    imported_items: List[Dict[str, Any]] = []
