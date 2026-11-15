from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.document import Document, DocumentStatus
from app.models.knowledge import Fact, FactStatus, SeverityLevel
from app.models.review import (
    Review, ReviewStatus,
    Claim,
    Finding, FindingStatus,
    Approval, ApprovalDecision,
)
from app.models.audit import AuditEvent
from app.schemas.dashboard import (
    DashboardResponse, SummaryCardsOut, RiskOverview, RiskDistribution
)
from app.schemas.document_and_review import ReviewOut, AuditEventOut

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org_id = current_user.organization_id
    now = datetime.now(timezone.utc)
    one_week_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    thirty_days_future = now + timedelta(days=30)

    # 1. Open Reviews
    open_reviews_count = db.query(func.count(Review.id)).filter(
        Review.organization_id == org_id,
        Review.status.in_([ReviewStatus.PENDING.value, ReviewStatus.IN_PROGRESS.value, ReviewStatus.NEEDS_REVIEW.value])
    ).scalar() or 0

    # 2. Blocked Content
    blocked_docs_count = db.query(func.count(Document.id)).filter(
        Document.organization_id == org_id,
        Document.status.in_([DocumentStatus.CHANGES_REQUESTED.value, DocumentStatus.REJECTED.value])
    ).scalar() or 0

    # 3. Approved This Week
    approved_this_week_count = db.query(func.count(Review.id)).filter(
        Review.organization_id == org_id,
        Review.status == ReviewStatus.APPROVED.value,
        Review.updated_at >= one_week_ago
    ).scalar() or 0

    # 4. Active Facts (Approved and not expired)
    active_facts_count = db.query(func.count(Fact.id)).filter(
        Fact.organization_id == org_id,
        Fact.status.in_([FactStatus.APPROVED.value, "Approved", "Active"]),
        (Fact.expires_at.is_(None) | (Fact.expires_at >= now))
    ).scalar() or 0

    # 5. Expiring Facts (within next 30 days)
    expiring_facts_count = db.query(func.count(Fact.id)).filter(
        Fact.organization_id == org_id,
        Fact.expires_at.isnot(None),
        Fact.expires_at <= thirty_days_future,
        Fact.expires_at >= now
    ).scalar() or 0

    # 6. Findings This Month
    findings_this_month_count = db.query(func.count(Finding.id)).join(Review).filter(
        Review.organization_id == org_id,
        Finding.created_at >= thirty_days_ago
    ).scalar() or 0

    # Severity distribution
    findings = db.query(Finding.severity, func.count(Finding.id)).join(Review).filter(
        Review.organization_id == org_id,
        Finding.status == FindingStatus.OPEN.value
    ).group_by(Finding.severity).all()

    dist_map = {row[0]: row[1] for row in findings}
    crit = dist_map.get(SeverityLevel.BLOCKER.value, 0) + dist_map.get("Critical", 0)
    high = dist_map.get(SeverityLevel.HIGH.value, 0)
    med = dist_map.get(SeverityLevel.WARNING.value, 0) + dist_map.get("Medium", 0)
    low = dist_map.get("Low", 0)
    adv = dist_map.get(SeverityLevel.INFO.value, 0) + dist_map.get("Advisory", 0)

    # Compute overall safety score: 100 base score
    deductions = (crit * 15) + (high * 8) + (med * 4) + (low * 1)
    overall_score = max(0, min(100, 100 - deductions))
    if overall_score >= 85:
        risk_status = "Optimal"
    elif overall_score >= 65:
        risk_status = "Moderate Risk"
    else:
        risk_status = "High Brand Risk"

    # Total claims and unverified claims rate
    total_claims = db.query(func.count(Claim.id)).join(Review).filter(Review.organization_id == org_id).scalar() or 0
    unverified_claims = db.query(func.count(Claim.id)).join(Review).filter(
        Review.organization_id == org_id,
        Claim.status.in_(["Unverified", "Disputed", "Proposed"])
    ).scalar() or 0
    unverified_rate = round((unverified_claims / total_claims * 100), 1) if total_claims > 0 else 0.0

    # Recent reviews (latest 5)
    recent_reviews_db = db.query(Review).filter(
        Review.organization_id == org_id
    ).order_by(Review.created_at.desc()).limit(5).all()

    recent_reviews = []
    for r in recent_reviews_db:
        r_out = ReviewOut.model_validate(r)
        if r.reviewer:
            r_out.reviewer_name = r.reviewer.full_name
        if r.document:
            r_out.document_title = r.document.title
            r_out.document_status = r.document.status
        r_out.claims_count = len(r.claims) if r.claims else 0
        r_out.findings_count = len(r.findings) if r.findings else 0
        recent_reviews.append(r_out)

    # Recent activity (latest 8)
    recent_activity_db = db.query(AuditEvent).filter(
        AuditEvent.organization_id == org_id
    ).order_by(AuditEvent.timestamp.desc()).limit(8).all()

    recent_activity = [
        AuditEventOut(
            id=a.id,
            organization_id=a.organization_id,
            actor_id=a.actor_id,
            actor_name=a.actor.full_name if a.actor else "System Governance",
            action=a.action,
            entity_type=a.entity_type,
            entity_id=a.entity_id,
            metadata=a.event_metadata or {},
            timestamp=a.timestamp,
        )
        for a in recent_activity_db
    ]

    return DashboardResponse(
        metrics=SummaryCardsOut(
            open_reviews=open_reviews_count,
            blocked_content=blocked_docs_count,
            approved_this_week=approved_this_week_count,
            active_facts=active_facts_count,
            expiring_facts=expiring_facts_count,
            findings_this_month=findings_this_month_count,
        ),
        risk_overview=RiskOverview(
            overall_score=overall_score,
            status=risk_status,
            findings_by_severity=RiskDistribution(
                critical=crit,
                high=high,
                medium=med,
                low=low,
                advisory=adv,
            ),
            unverified_claims_rate=unverified_rate,
        ),
        recent_reviews=recent_reviews,
        recent_activity=recent_activity,
    )
