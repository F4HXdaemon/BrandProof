from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.core.dependencies import get_current_user, require_roles, read_upload_file_bounded
from app.models.user import User, UserRole
from app.models.document import Document, DocumentVersion, DocumentStatus, DocumentChunk
from app.models.review import (
    Review, ReviewStatus,
    Claim, ClaimStatus,
    Finding, FindingStatus,
    Approval,
    Comment,
)
from app.schemas.document_and_review import (
    ReviewCreate, ReviewOut, ReviewDetailOut,
    ClaimOut, FindingOut, ApprovalOut,
    DocumentOut, DocumentVersionOut, DocumentChunkOut,
    CommentCreate, CommentOut, AcceptFixRequest, DismissFindingRequest
)
from app.services.ai_engine import get_analysis_engine
from app.services.review_orchestrator import ReviewOrchestrator
from app.services.audit_service import record_audit_event
from app.services.llm import compute_word_diff, compute_diff_stats
from app.services.risk_scoring import calculate_risk_score

router = APIRouter(prefix="/reviews", tags=["Reviews"])


def _map_version_out(v: DocumentVersion) -> DocumentVersionOut:
    chunks_out = [
        DocumentChunkOut(
            id=c.id,
            document_version_id=c.document_version_id,
            sequence=c.sequence,
            chunk_type=c.chunk_type,
            text=c.text,
            page_number=c.page_number,
            metadata=c.chunk_metadata or {},
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in (v.chunks or [])
    ]
    return DocumentVersionOut(
        id=v.id,
        document_id=v.document_id,
        version_number=v.version_number,
        file_path=v.file_path,
        file_size=v.file_size,
        extracted_text=v.extracted_text,
        error_message=v.error_message,
        created_by_id=v.created_by_id,
        created_at=v.created_at,
        updated_at=v.updated_at,
        chunks=chunks_out,
    )


def _map_review_out(r: Review) -> ReviewOut:
    out = ReviewOut.model_validate(r)
    if r.reviewer:
        out.reviewer_name = r.reviewer.full_name
    if r.document:
        out.document_title = r.document.title
        out.document_status = r.document.status
        if r.document.creator:
            out.creator_name = r.document.creator.full_name
    out.title = r.title or (r.document.title if r.document else "Review")
    out.intent_card = r.intent_card or {}
    out.claims_count = len(r.claims) if r.claims else 0
    out.findings_count = len(r.findings) if r.findings else 0
    return out


@router.get("", response_model=List[ReviewOut])
def list_reviews(
    status: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    creator_id: Optional[str] = Query(None),
    document_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Review).filter(Review.organization_id == current_user.organization_id)
    if status and status != "All":
        query = query.filter(Review.status == status)
    if product and product != "All":
        query = query.filter(Review.product == product)
    if region and region != "All":
        query = query.filter(Review.region == region)
    if channel and channel != "All":
        query = query.filter(Review.channel == channel)
    if document_id:
        query = query.filter(Review.document_id == document_id)
    if creator_id:
        query = query.join(Document, Review.document_id == Document.id).filter(Document.creator_id == creator_id)

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.outerjoin(Document, Review.document_id == Document.id).filter(
            or_(
                Review.title.ilike(term),
                Review.summary.ilike(term),
                Document.title.ilike(term),
            )
        )

    reviews = query.order_by(Review.created_at.desc()).all()
    return [_map_review_out(r) for r in reviews]


@router.post("/new", response_model=ReviewDetailOut)
async def submit_new_review(
    title: str = Form(...),
    product: str = Form("All"),
    region: str = Form("Global"),
    channel: str = Form("All"),
    content_type: str = Form("General Marketing"),
    intended_audience: str = Form("All Audiences"),
    purpose: Optional[str] = Form(None),
    pasted_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submits content for review (either uploaded file or pasted text) with complete Intent Card context.
    Executes Document Ingestion, text extraction & chunking, and Review creation.
    """
    if not file and (not pasted_text or not pasted_text.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either an uploaded document (.txt, .docx, .pdf, .md) or pasted text must be provided."
        )

    intent_card = {
        "title": title.strip(),
        "product": product.strip(),
        "region": region.strip(),
        "channel": channel.strip(),
        "content_type": content_type.strip(),
        "intended_audience": intended_audience.strip(),
        "purpose": purpose.strip() if purpose else "",
    }

    orchestrator = ReviewOrchestrator(db)
    try:
        if file and file.filename:
            file_bytes = await read_upload_file_bounded(file)
            review, doc, ver = orchestrator.ingest_and_create_review(
                file_bytes=file_bytes,
                filename=file.filename,
                content_type=file.content_type,
                title=title,
                creator_id=current_user.id,
                organization_id=current_user.organization_id,
                intent_card=intent_card,
            )
        else:
            review, doc, ver = orchestrator.ingest_pasted_text(
                text_content=pasted_text or "",
                title=title,
                creator_id=current_user.id,
                organization_id=current_user.organization_id,
                intent_card=intent_card,
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ingestion failed: {str(e)}")

    return get_review_detail(review.id, current_user, db)


@router.post("", response_model=ReviewDetailOut)
def create_review(
    review_in: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify document belongs to organization
    doc = db.query(Document).filter(
        Document.id == review_in.document_id,
        Document.organization_id == current_user.organization_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    version_id = review_in.version_id
    if not version_id:
        latest_ver = db.query(DocumentVersion).filter(
            DocumentVersion.document_id == doc.id
        ).order_by(DocumentVersion.version_number.desc()).first()
        if latest_ver:
            version_id = latest_ver.id

    review = Review(
        organization_id=current_user.organization_id,
        document_id=doc.id,
        version_id=version_id,
        reviewer_id=review_in.reviewer_id or current_user.id,
        title=review_in.title or doc.title,
        status=ReviewStatus.NEEDS_REVIEW.value,
        summary=review_in.summary or f"Brand compliance audit for {doc.title}",
        intent_card=review_in.intent_card or {},
        product=review_in.product or doc.product,
        region=review_in.region or doc.region,
        channel=review_in.channel or doc.channel,
        content_type=review_in.content_type,
        intended_audience=review_in.intended_audience,
        purpose=review_in.purpose,
        processing_status="Ready",
    )
    db.add(review)
    db.flush()

    doc.status = DocumentStatus.NEEDS_REVIEW.value

    # Run placeholder claim extraction engine
    engine = get_analysis_engine()
    version = db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first() if version_id else None
    if version and version.extracted_text:
        extracted = engine.extract_claims(version.extracted_text)
        for claim_prop in extracted:
            db_claim = Claim(
                organization_id=current_user.organization_id,
                document_version_id=version_id,
                review_id=review.id,
                document_id=doc.id,
                text=claim_prop.text,
                location_metadata=claim_prop.location_metadata,
                confidence=claim_prop.confidence,
                status=ClaimStatus.PROPOSED.value,
            )
            db.add(db_claim)

    db.commit()
    db.refresh(review)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="REVIEW_INITIATED",
        entity_type="Review",
        entity_id=review.id,
        metadata={"document_id": doc.id, "document_title": doc.title}
    )

    return get_review_detail(review.id, current_user, db)


@router.get("/{review_id}", response_model=ReviewDetailOut)
def get_review_detail(
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

    # Map DocumentOut
    doc_out = None
    if review.document:
        doc_out = DocumentOut.model_validate(review.document)
        if review.document.creator:
            doc_out.creator_name = review.document.creator.full_name
        doc_out.versions = [_map_version_out(v) for v in review.document.versions]

    # Map DocumentVersionOut
    ver_out = None
    if review.version:
        ver_out = _map_version_out(review.version)

    out = ReviewDetailOut(
        id=review.id,
        organization_id=review.organization_id,
        document_id=review.document_id,
        version_id=review.version_id,
        reviewer_id=review.reviewer_id,
        reviewer_name=review.reviewer.full_name if review.reviewer else None,
        creator_name=review.document.creator.full_name if review.document and review.document.creator else None,
        title=review.title or (review.document.title if review.document else "Review"),
        document_title=review.document.title if review.document else None,
        document_status=review.document.status if review.document else None,
        status=ReviewStatus(review.status) if review.status in [s.value for s in ReviewStatus] else ReviewStatus.PENDING,
        summary=review.summary,
        intent_card=review.intent_card or {},
        product=review.product or (review.document.product if review.document else "All"),
        region=review.region or (review.document.region if review.document else "Global"),
        channel=review.channel or (review.document.channel if review.document else "All"),
        content_type=review.content_type,
        intended_audience=review.intended_audience,
        purpose=review.purpose,
        risk_score=review.risk_score,
        risk_level=review.risk_level,
        processing_status=review.processing_status,
        error_message=review.error_message,
        created_at=review.created_at,
        updated_at=review.updated_at,
        claims_count=len(review.claims),
        findings_count=len(review.findings),
        document=doc_out,
        version=ver_out,
        claims=[ClaimOut.model_validate(c) for c in review.claims],
        findings=[
            FindingOut(
                id=f.id,
                review_id=f.review_id,
                claim_id=f.claim_id,
                rule_id=f.rule_id,
                guideline_id=f.guideline_id,
                fact_id=f.fact_id,
                finding_type=f.finding_type,
                severity=f.severity,
                title=f.title,
                message=f.message,
                suggestion=f.suggested_replacement or f.suggestion,
                suggested_replacement=f.suggested_replacement,
                quoted_text=f.quoted_text,
                start_offset=f.start_offset,
                end_offset=f.end_offset,
                page_number=f.page_number or 1,
                source_type=f.source_type,
                source_id=f.source_id,
                source_reference=f.source_reference,
                checker=f.checker or "RuleEngine",
                confidence=f.confidence or 1.0,
                dismissal_reason=f.dismissal_reason,
                status=f.status,
                claim_text=f.claim.claim_text if f.claim else None,
                created_at=f.created_at,
                updated_at=f.updated_at,
            )
            for f in review.findings
        ],
        approvals=[
            ApprovalOut(
                id=a.id,
                review_id=a.review_id,
                document_id=a.document_id,
                approver_id=a.approver_id,
                approver_name=a.approver.full_name if a.approver else None,
                status=a.status,
                comments=a.comments,
                is_override=a.is_override,
                override_reason=a.override_reason,
                override_finding_ids=a.override_finding_ids or [],
                decided_at=a.decided_at,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in review.approvals
        ],
        comments=[
            CommentOut(
                id=c.id,
                organization_id=c.organization_id,
                review_id=c.review_id,
                finding_id=c.finding_id,
                author_id=c.author_id,
                author_name=c.author.full_name if c.author else None,
                text=c.text,
                resolved=c.resolved,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in (review.comments or [])
        ],
    )
    return out


@router.put("/{review_id}/status", response_model=ReviewOut)
def update_review_status(
    review_id: str,
    status: ReviewStatus,
    current_user: User = Depends(require_roles([UserRole.REVIEWER, UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Cardinal Invariant: Review cannot be directly marked Approved if unresolved blockers exist
    if status == ReviewStatus.APPROVED:
        open_blockers = db.query(Finding).filter(
            Finding.review_id == review.id,
            Finding.severity.in_(["Blocker", "Critical"]),
            Finding.status.in_(["Open", FindingStatus.OPEN.value])
        ).all()
        if open_blockers:
            raise HTTPException(
                status_code=400,
                detail=f"Approval Blocked: Review contains {len(open_blockers)} open Blocker finding(s). "
                       f"All Blockers must be resolved or formally overridden via the approval workflow."
            )

    review.status = status.value
    if status == ReviewStatus.APPROVED and review.document:
        review.document.status = DocumentStatus.APPROVED.value
    elif status == ReviewStatus.CHANGES_REQUESTED and review.document:
        review.document.status = DocumentStatus.CHANGES_REQUESTED.value
    elif status == ReviewStatus.REJECTED and review.document:
        review.document.status = DocumentStatus.REJECTED.value

    db.commit()
    db.refresh(review)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="REVIEW_STATUS_UPDATED",
        entity_type="Review",
        entity_id=review.id,
        metadata={"new_status": status.value}
    )

    return _map_review_out(review)


@router.post("/{review_id}/accept-fix", response_model=ReviewDetailOut)
def accept_finding_fix(
    review_id: str,
    fix_req: AcceptFixRequest,
    current_user: User = Depends(require_roles([UserRole.CREATOR, UserRole.REVIEWER, UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    finding = db.query(Finding).filter(
        Finding.id == fix_req.finding_id,
        Finding.review_id == review.id
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    current_version = db.query(DocumentVersion).filter(DocumentVersion.id == review.version_id).first()
    if not current_version or not current_version.extracted_text:
        raise HTTPException(status_code=400, detail="Current version has no text content to fix")

    replacement = fix_req.replacement_text or finding.suggested_replacement or finding.suggestion
    if not replacement:
        raise HTTPException(status_code=400, detail="No suggested replacement available for this finding")

    old_text = current_version.extracted_text
    new_text = old_text
    if finding.quoted_text and finding.quoted_text in old_text:
        new_text = old_text.replace(finding.quoted_text, replacement, 1)
    elif finding.finding_type == "disclaimer":
        new_text = f"{old_text}\n\n---\n**Disclaimer**: {replacement}"
    else:
        new_text = f"{old_text} ({replacement})"

    orchestrator = ReviewOrchestrator(db)
    reason = f"Accepted fix for '{finding.title or finding.message}' -> '{replacement}'"
    new_ver = orchestrator.create_new_version_with_fixes(
        review_id=review.id,
        new_text=new_text,
        change_reason=reason,
        user_id=current_user.id
    )

    finding.status = FindingStatus.FIXED.value
    db.commit()

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="FINDING_FIX_ACCEPTED",
        entity_type="Finding",
        entity_id=finding.id,
        metadata={"replacement": replacement, "new_version_id": new_ver.id}
    )

    return get_review_detail(review.id, current_user, db)


@router.post("/{review_id}/dismiss-finding", response_model=ReviewDetailOut)
def dismiss_finding(
    review_id: str,
    dismiss_req: DismissFindingRequest,
    current_user: User = Depends(require_roles([UserRole.REVIEWER, UserRole.BRAND_MANAGER, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    finding = db.query(Finding).filter(
        Finding.id == dismiss_req.finding_id,
        Finding.review_id == review.id
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    if not dismiss_req.dismissal_reason or len(dismiss_req.dismissal_reason.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A valid business rationale (min 5 characters) is required to dismiss a finding."
        )

    finding.status = FindingStatus.DISMISSED.value
    finding.dismissal_reason = dismiss_req.dismissal_reason.strip()

    # Recalculate risk score
    risk_data = calculate_risk_score(review.findings)
    review.risk_score = risk_data["risk_score"]
    review.risk_level = risk_data["risk_level"]

    db.commit()

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="FINDING_DISMISSED",
        entity_type="Finding",
        entity_id=finding.id,
        metadata={"reason": finding.dismissal_reason, "severity": finding.severity}
    )

    return get_review_detail(review.id, current_user, db)


@router.get("/{review_id}/diff")
def get_version_diff(
    review_id: str,
    base_version_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    current_ver = db.query(DocumentVersion).filter(DocumentVersion.id == review.version_id).first()
    if not current_ver:
        raise HTTPException(status_code=404, detail="Current document version not found")

    base_ver = None
    if base_version_id:
        base_ver = db.query(DocumentVersion).filter(DocumentVersion.id == base_version_id).first()
    elif current_ver.parent_version_id:
        base_ver = db.query(DocumentVersion).filter(DocumentVersion.id == current_ver.parent_version_id).first()
    elif review.document and len(review.document.versions) > 1:
        base_ver = review.document.versions[0]

    old_text = base_ver.extracted_text if base_ver and base_ver.extracted_text else (current_ver.extracted_text or "")
    new_text = current_ver.extracted_text or ""

    tokens = compute_word_diff(old_text, new_text)
    stats = compute_diff_stats(old_text, new_text)

    return {
        "review_id": review.id,
        "base_version": {
            "id": base_ver.id if base_ver else current_ver.id,
            "version_number": base_ver.version_number if base_ver else 1,
            "change_reason": base_ver.change_reason if base_ver else "Initial version",
        },
        "current_version": {
            "id": current_ver.id,
            "version_number": current_ver.version_number,
            "change_reason": current_ver.change_reason,
        },
        "stats": stats,
        "tokens": tokens,
    }


@router.get("/{review_id}/comments", response_model=List[CommentOut])
def list_comments(
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

    comments = db.query(Comment).filter(Comment.review_id == review.id).order_by(Comment.created_at.asc()).all()
    return [
        CommentOut(
            id=c.id,
            organization_id=c.organization_id,
            review_id=c.review_id,
            finding_id=c.finding_id,
            author_id=c.author_id,
            author_name=c.author.full_name if c.author else None,
            text=c.text,
            resolved=c.resolved,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in comments
    ]


@router.post("/{review_id}/comments", response_model=CommentOut)
def add_comment(
    review_id: str,
    comment_in: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if not comment_in.text or not comment_in.text.strip():
        raise HTTPException(status_code=400, detail="Comment text cannot be empty.")

    comment = Comment(
        organization_id=current_user.organization_id,
        review_id=review.id,
        finding_id=comment_in.finding_id,
        author_id=current_user.id,
        text=comment_in.text.strip(),
        resolved=False,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="COMMENT_ADDED",
        entity_type="Comment",
        entity_id=comment.id,
        metadata={"review_id": review.id, "finding_id": comment.finding_id}
    )

    out = CommentOut.model_validate(comment)
    out.author_name = current_user.full_name
    return out
