from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.schemas.document_and_review import ReviewOut, AuditEventOut


class SummaryCardsOut(BaseModel):
    open_reviews: int
    blocked_content: int
    approved_this_week: int
    active_facts: int
    expiring_facts: int
    findings_this_month: int


class RiskDistribution(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    advisory: int = 0


class RiskOverview(BaseModel):
    overall_score: int  # 0 - 100 brand safety score
    status: str  # "Good", "Moderate Risk", "High Risk"
    findings_by_severity: RiskDistribution
    unverified_claims_rate: float  # Percentage


class DashboardResponse(BaseModel):
    metrics: SummaryCardsOut
    risk_overview: RiskOverview
    recent_reviews: List[ReviewOut]
    recent_activity: List[AuditEventOut]
