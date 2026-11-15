from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.review import Review, Claim, ClaimStatus
from app.schemas.document_and_review import ClaimCreate, ClaimOut
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/claims", tags=["Claims"])


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
