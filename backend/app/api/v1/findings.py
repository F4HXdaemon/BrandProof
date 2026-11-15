from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.review import Review, Finding, FindingStatus
from app.models.knowledge import SeverityLevel
from app.schemas.document_and_review import FindingCreate, FindingOut
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/findings", tags=["Findings"])


@router.get("/review/{review_id}", response_model=List[FindingOut])
def list_findings_for_review(
    review_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    findings = db.query(Finding).filter(Finding.review_id == review_id).all()
    results = []
    for f in findings:
        out = FindingOut.model_validate(f)
        if f.claim:
            out.claim_text = f.claim.text
        results.append(out)
    return results


@router.post("", response_model=FindingOut)
def create_finding(
    finding_in: FindingCreate,
    current_user: User = Depends(require_roles([UserRole.REVIEWER, UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    # Enforce cardinal principle: NO VALID SOURCE = NO FINDING
    if not finding_in.source_reference or not finding_in.source_reference.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="BrandProof Governance Policy: 'NO VALID SOURCE = NO FINDING'. Every finding must trace strictly to an approved source of truth. Please specify source_reference."
        )

    review = db.query(Review).filter(
        Review.id == finding_in.review_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    finding = Finding(
        organization_id=review.organization_id,
        review_id=finding_in.review_id,
        claim_id=finding_in.claim_id,
        rule_id=finding_in.rule_id,
        guideline_id=finding_in.guideline_id,
        fact_id=finding_in.fact_id,
        severity=finding_in.severity.value if isinstance(finding_in.severity, SeverityLevel) else str(finding_in.severity),
        message=finding_in.message,
        suggestion=finding_in.suggestion,
        status=finding_in.status.value if isinstance(finding_in.status, FindingStatus) else str(finding_in.status),
        source_reference=finding_in.source_reference.strip(),
        source_id=finding_in.rule_id or finding_in.fact_id or finding_in.guideline_id,
        source_type="rule" if finding_in.rule_id else ("fact" if finding_in.fact_id else ("guideline" if finding_in.guideline_id else "rule")),
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="FINDING_RECORDED",
        entity_type="Finding",
        entity_id=finding.id,
        metadata={"severity": finding.severity, "source": finding.source_reference}
    )

    out = FindingOut.model_validate(finding)
    if finding.claim:
        out.claim_text = finding.claim.text
    return out


@router.put("/{finding_id}/status", response_model=FindingOut)
def update_finding_status(
    finding_id: str,
    status: FindingStatus,
    current_user: User = Depends(require_roles([UserRole.REVIEWER, UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    finding = db.query(Finding).join(Review).filter(
        Finding.id == finding_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    finding.status = status.value
    db.commit()
    db.refresh(finding)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="FINDING_STATUS_UPDATED",
        entity_type="Finding",
        entity_id=finding.id,
        metadata={"new_status": status.value}
    )

    out = FindingOut.model_validate(finding)
    if finding.claim:
        out.claim_text = finding.claim.text
    return out
