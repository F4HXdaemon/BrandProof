from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.document import Document, DocumentStatus
from app.models.review import (
    Review, ReviewStatus,
    Approval, ApprovalDecision,
    Finding, FindingStatus
)
from app.schemas.document_and_review import ApprovalCreate, ApprovalOut
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.post("/review/{review_id}", response_model=ApprovalOut)
def record_approval_decision(
    review_id: str,
    approval_in: ApprovalCreate,
    current_user: User = Depends(require_roles([UserRole.REVIEWER, UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Record human approval decision.
    Invariant: AI proposes. Evidence decides. People approve. AI must never be the final approver.
    """
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Enforce Blocker Protection Rule
    open_blockers = db.query(Finding).filter(
        Finding.review_id == review.id,
        Finding.severity.in_(["Blocker", "Critical"]),
        Finding.status.in_(["Open", FindingStatus.OPEN.value])
    ).all()

    is_override = False
    override_reason = None
    override_finding_ids = []

    if approval_in.status == ApprovalDecision.APPROVED and open_blockers:
        if not approval_in.is_override:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Approval Blocked: Review contains {len(open_blockers)} open Blocker finding(s). All Blockers must be resolved or explicitly overridden with business justification."
            )

        # Verify role permits override
        if current_user.role not in [UserRole.BRAND_MANAGER, UserRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Governance Policy: Only Brand Managers or Administrators are authorized to override Blocker findings."
            )

        if not approval_in.override_reason or len(approval_in.override_reason.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Governance Policy: An explicit business justification (minimum 10 characters) is mandatory to override Blocker findings."
            )

        is_override = True
        override_reason = approval_in.override_reason.strip()
        override_finding_ids = [b.id for b in open_blockers]

    approval = Approval(
        review_id=review.id,
        document_id=review.document_id,
        document_version_id=review.version_id,
        approver_id=current_user.id,
        status=approval_in.status.value if isinstance(approval_in.status, ApprovalDecision) else str(approval_in.status),
        comments=approval_in.comments,
        is_override=is_override,
        override_reason=override_reason,
        override_finding_ids=override_finding_ids,
    )
    db.add(approval)

    # Transition Review & Document status based on human decision
    if approval_in.status == ApprovalDecision.APPROVED:
        review.status = ReviewStatus.APPROVED.value
        if review.document:
            review.document.status = DocumentStatus.APPROVED.value
    elif approval_in.status == ApprovalDecision.CHANGES_REQUESTED:
        review.status = ReviewStatus.CHANGES_REQUESTED.value
        if review.document:
            review.document.status = DocumentStatus.CHANGES_REQUESTED.value
    elif approval_in.status == ApprovalDecision.REJECTED:
        review.status = ReviewStatus.REJECTED.value
        if review.document:
            review.document.status = DocumentStatus.REJECTED.value

    db.commit()
    db.refresh(approval)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action=f"HUMAN_APPROVAL_{approval.status.upper()}",
        entity_type="Approval",
        entity_id=approval.id,
        metadata={
            "review_id": review.id,
            "decision": approval.status,
            "approver_role": current_user.role,
            "comments": approval.comments
        }
    )

    out = ApprovalOut.model_validate(approval)
    out.approver_name = current_user.full_name
    return out
