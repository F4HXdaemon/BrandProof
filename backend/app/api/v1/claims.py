from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.review import Review, Claim, ClaimStatus
from app.models.evidence import Evidence, ReviewEvidence
from app.models.knowledge import Fact
from app.schemas.document_and_review import ClaimCreate, ClaimUpdate, ClaimOut
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/claims", tags=["Claims"])


class LinkEvidencePayload(BaseModel):
    evidence_id: str
    status: Optional[str] = None
    reasoning: Optional[str] = None


@router.get("/review/{review_id}", response_model=List[ClaimOut])
def list_claims_for_review(
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

    claims = db.query(Claim).filter(Claim.review_id == review_id).all()
    return [ClaimOut.model_validate(c) for c in claims]


@router.post("", response_model=ClaimOut)
def create_claim(
    claim_in: ClaimCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    review = db.query(Review).filter(
        Review.id == claim_in.review_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    claim = Claim(
        organization_id=review.organization_id,
        review_id=claim_in.review_id,
        document_id=claim_in.document_id,
        text=claim_in.text,
        claim_text=claim_in.text,
        location_metadata=claim_in.location_metadata,
        confidence=claim_in.confidence,
        status=claim_in.status.value if isinstance(claim_in.status, ClaimStatus) else str(claim_in.status),
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="CLAIM_RECORDED",
        entity_type="Claim",
        entity_id=claim.id,
        metadata={"text": claim.text[:80]}
    )

    return ClaimOut.model_validate(claim)


@router.patch("/{claim_id}", response_model=ClaimOut)
def update_claim(
    claim_id: str,
    payload: ClaimUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Updates claim details, verification status, and links or unlinks supporting evidence or facts.
    Enforces organization isolation.
    """
    claim = db.query(Claim).join(Review, Review.id == Claim.review_id).filter(
        Claim.id == claim_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found or unauthorized access.")

    # 1. Evidence linking/unlinking
    if payload.evidence_id is not None:
        if payload.evidence_id.strip() == "":
            claim.evidence_id = None
        else:
            evidence = db.query(Evidence).filter(
                Evidence.id == payload.evidence_id.strip(),
                Evidence.organization_id == current_user.organization_id
            ).first()
            if not evidence:
                raise HTTPException(status_code=404, detail="Evidence document not found in your organization.")

            claim.evidence_id = evidence.id

            # Automatically ensure review is associated with this evidence
            assoc = db.query(ReviewEvidence).filter(
                ReviewEvidence.review_id == claim.review_id,
                ReviewEvidence.evidence_id == evidence.id
            ).first()
            if not assoc:
                assoc = ReviewEvidence(
                    organization_id=current_user.organization_id,
                    review_id=claim.review_id,
                    evidence_id=evidence.id,
                    relevance_notes=f"Linked to claim: {(claim.claim_text or claim.text)[:100]}",
                )
                db.add(assoc)

            # Auto-upgrade status to SUPPORTED if evidence is Validated and no explicit status was sent
            if not payload.status and evidence.effective_status == "Validated":
                claim.status = ClaimStatus.SUPPORTED.value
                if not payload.reasoning:
                    claim.reasoning = f"Verified by corporate evidence: {evidence.title} ({evidence.filename})"

    # 2. Fact linking/unlinking
    if payload.matched_fact_id is not None:
        if payload.matched_fact_id.strip() == "":
            claim.matched_fact_id = None
        else:
            fact = db.query(Fact).filter(
                Fact.id == payload.matched_fact_id.strip(),
                Fact.organization_id == current_user.organization_id
            ).first()
            if not fact:
                raise HTTPException(status_code=404, detail="Approved fact not found in your organization.")
            claim.matched_fact_id = fact.id

    # 3. Status update
    if payload.status:
        try:
            enum_status = ClaimStatus(payload.status)
            claim.status = enum_status.value
        except Exception:
            claim.status = payload.status

    # 4. Audit Reasoning update
    if payload.reasoning is not None:
        claim.reasoning = payload.reasoning

    db.commit()
    db.refresh(claim)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="CLAIM_UPDATED",
        entity_type="Claim",
        entity_id=claim.id,
        metadata={
            "evidence_id": claim.evidence_id,
            "status": claim.status,
            "matched_fact_id": claim.matched_fact_id,
        }
    )

    return ClaimOut.model_validate(claim)


@router.post("/{claim_id}/link-evidence", response_model=ClaimOut)
def link_evidence_to_claim(
    claim_id: str,
    payload: LinkEvidencePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Links an evidence document to a claim and updates verification status."""
    return update_claim(
        claim_id=claim_id,
        payload=ClaimUpdate(
            evidence_id=payload.evidence_id,
            status=payload.status,
            reasoning=payload.reasoning,
        ),
        current_user=current_user,
        db=db,
    )


@router.post("/{claim_id}/unlink-evidence", response_model=ClaimOut)
def unlink_evidence_from_claim(
    claim_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unlinks supporting evidence from a claim."""
    return update_claim(
        claim_id=claim_id,
        payload=ClaimUpdate(evidence_id=""),
        current_user=current_user,
        db=db,
    )
