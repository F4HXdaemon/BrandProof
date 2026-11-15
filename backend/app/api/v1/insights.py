from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Dict, Any, List
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.review import Review, Finding, Claim
from app.models.knowledge import Rule, Term, Guideline, Fact
from app.models.audit import AuditEvent

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("", response_model=Dict[str, Any])
def get_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Computes real, live database aggregations and analytics for governance insights.
    All data is computed dynamically against the active organization.
    """
    org_id = current_user.organization_id

    # 1. High-level counts
    total_reviews = db.query(func.count(Review.id)).filter(Review.organization_id == org_id).scalar() or 0
    total_findings = db.query(func.count(Finding.id)).filter(Finding.organization_id == org_id).scalar() or 0
    open_blockers = db.query(func.count(Finding.id)).filter(
        Finding.organization_id == org_id,
        Finding.severity.in_(["Blocker", "Critical"]),
        Finding.status.in_(["Open", "OPEN", "open"])
    ).scalar() or 0

    resolved_findings = db.query(func.count(Finding.id)).filter(
        Finding.organization_id == org_id,
        Finding.status.in_(["Fixed", "Resolved", "Dismissed"])
    ).scalar() or 0

    resolution_rate = round((resolved_findings / total_findings * 100), 1) if total_findings > 0 else 100.0

    avg_risk = db.query(func.avg(Review.risk_score)).filter(Review.organization_id == org_id).scalar() or 0.0

    # 2. Findings by Severity
    severity_rows = db.query(Finding.severity, func.count(Finding.id)).filter(
        Finding.organization_id == org_id
    ).group_by(Finding.severity).all()
    severity_breakdown = {"Blocker": 0, "High": 0, "Warning": 0, "Info": 0}
    for sev, cnt in severity_rows:
        sev_clean = str(sev).capitalize()
        if sev_clean in ["Critical", "Blocker"]:
            severity_breakdown["Blocker"] += cnt
        elif sev_clean == "High":
            severity_breakdown["High"] += cnt
        elif sev_clean in ["Warning", "Medium"]:
            severity_breakdown["Warning"] += cnt
        else:
            severity_breakdown["Info"] += cnt

    # 3. Findings by Status
    status_rows = db.query(Finding.status, func.count(Finding.id)).filter(
        Finding.organization_id == org_id
    ).group_by(Finding.status).all()
    status_breakdown = {"Open": 0, "Fixed": 0, "Dismissed": 0}
    for st, cnt in status_rows:
        st_clean = str(st).capitalize()
        if st_clean in ["Fixed", "Resolved"]:
            status_breakdown["Fixed"] += cnt
        elif st_clean in ["Dismissed", "Waived"]:
            status_breakdown["Dismissed"] += cnt
        else:
            status_breakdown["Open"] += cnt

    # 4. Reviews by Risk Level
    risk_rows = db.query(Review.risk_level, func.count(Review.id)).filter(
        Review.organization_id == org_id
    ).group_by(Review.risk_level).all()
    risk_distribution = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    for r_lvl, cnt in risk_rows:
        r_clean = str(r_lvl).capitalize()
        if r_clean in risk_distribution:
            risk_distribution[r_clean] += cnt
        else:
            risk_distribution["Low"] += cnt

    # 5. Top Violated Rules
    top_rules_query = db.query(Rule.name, func.count(Finding.id).label("count")).join(
        Finding, Finding.rule_id == Rule.id
    ).filter(
        Rule.organization_id == org_id
    ).group_by(Rule.name).order_by(desc("count")).limit(5).all()

    top_violated_rules = [{"name": r[0], "count": r[1]} for r in top_rules_query]

    # 6. Top Violated Terms
    top_terms_query = db.query(Finding.quoted_text, func.count(Finding.id).label("count")).filter(
        Finding.organization_id == org_id,
        Finding.finding_type == "terminology"
    ).group_by(Finding.quoted_text).order_by(desc("count")).limit(5).all()

    top_violated_terms = [{"term": t[0] or "Unknown", "count": t[1]} for t in top_terms_query]

    # 7. Reviews by Channel & Product
    channel_rows = db.query(Review.channel, func.count(Review.id)).filter(
        Review.organization_id == org_id
    ).group_by(Review.channel).all()
    channel_distribution = {c[0] or "All": c[1] for c in channel_rows}

    product_rows = db.query(Review.product, func.count(Review.id)).filter(
        Review.organization_id == org_id
    ).group_by(Review.product).all()
    product_distribution = {p[0] or "All": p[1] for p in product_rows}

    # 8. Claims verification status breakdown
    claim_rows = db.query(Claim.status, func.count(Claim.id)).filter(
        Claim.organization_id == org_id
    ).group_by(Claim.status).all()
    claims_breakdown = {cr[0] or "Unknown": cr[1] for cr in claim_rows}

    return {
        "metrics": {
            "total_reviews": total_reviews,
            "total_findings": total_findings,
            "open_blockers": open_blockers,
            "resolved_findings": resolved_findings,
            "resolution_rate_percent": resolution_rate,
            "average_risk_score": round(float(avg_risk), 1),
        },
        "severity_breakdown": severity_breakdown,
        "status_breakdown": status_breakdown,
        "risk_distribution": risk_distribution,
        "top_violated_rules": top_violated_rules,
        "top_violated_terms": top_violated_terms,
        "channel_distribution": channel_distribution,
        "product_distribution": product_distribution,
        "claims_breakdown": claims_breakdown,
    }
