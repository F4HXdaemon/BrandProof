import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.core.dependencies import get_current_user, require_roles, read_upload_file_bounded
from app.models.user import User, UserRole
from app.models.evidence import Evidence, EvidenceStatus, ReviewEvidence
from app.models.review import Review, Claim
from app.schemas.evidence import EvidenceOut, EvidenceDetailOut, AssociateEvidenceRequest
from app.services.evidence_service import EvidenceService, EvidenceValidationError
from app.services.storage import get_storage

router = APIRouter(prefix="/evidence", tags=["Evidence"])


def _map_evidence_out(e: Evidence) -> EvidenceOut:
    eff_status = e.effective_status
    reviews_count = len(e.review_associations) if e.review_associations else 0
    claims_count = len(e.claims) if e.claims else 0
    return EvidenceOut(
        id=e.id,
        organization_id=e.organization_id,
        uploaded_by_id=e.uploaded_by_id,
        uploader_name=e.uploaded_by.full_name if e.uploaded_by else None,
        title=e.title,
        filename=e.filename,
        file_type=e.file_type,
        file_extension=e.file_extension,
        file_size=e.file_size,
        file_hash=e.file_hash,
        sha256_checksum=e.file_hash,
        status=eff_status,
        is_expired=e.is_expired,
        validation_errors=e.validation_errors,
        description=e.description,
        source_reference=e.source_reference,
        product_scope=e.product_scope,
        region_scope=e.region_scope,
        channel_scope=e.channel_scope,
        valid_from=e.valid_from,
        expires_at=e.expires_at,
        associated_reviews_count=reviews_count,
        associated_claims_count=claims_count,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


@router.post("/upload", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    source_reference: Optional[str] = Form(None),
    product_scope: Optional[str] = Form("All"),
    region_scope: Optional[str] = Form("Global"),
    channel_scope: Optional[str] = Form("All"),
    expires_at: Optional[str] = Form(None),
    review_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Uploads supporting evidence document (PDF, DOCX, TXT, PNG, JPG).
    Enforces file size limit, content-type magic byte validation, safe filename handling,
    and organization-level access isolation.
    """
    parsed_expires_at = None
    if expires_at and expires_at.strip():
        try:
            parsed_expires_at = datetime.fromisoformat(expires_at.strip().replace("Z", "+00:00"))
        except Exception:
            pass

    file_bytes = await read_upload_file_bounded(file)
    service = EvidenceService(db)

    try:
        evidence = service.upload_evidence(
            file_bytes=file_bytes,
            filename=file.filename or "evidence_document.pdf",
            organization_id=current_user.organization_id,
            uploaded_by_id=current_user.id,
            title=title,
            description=description,
            source_reference=source_reference,
            product_scope=product_scope or "All",
            region_scope=region_scope or "Global",
            channel_scope=channel_scope or "All",
            expires_at=parsed_expires_at,
            review_id=review_id,
        )
    except EvidenceValidationError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evidence processing failed: {str(e)}"
        )

    return _map_evidence_out(evidence)


@router.get("", response_model=List[EvidenceOut])
def list_evidence(
    status: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    review_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists evidence documents scoped to current user's organization."""
    query = db.query(Evidence).filter(Evidence.organization_id == current_user.organization_id)

    if status and status != "All":
        query = query.filter(Evidence.status == status)

    if product and product != "All":
        query = query.filter(Evidence.product_scope == product)

    if review_id:
        query = query.join(ReviewEvidence, ReviewEvidence.evidence_id == Evidence.id).filter(
            ReviewEvidence.review_id == review_id
        )

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Evidence.title.ilike(term),
                Evidence.filename.ilike(term),
                Evidence.description.ilike(term),
                Evidence.source_reference.ilike(term),
            )
        )

    records = query.order_by(Evidence.created_at.desc()).all()
    return [_map_evidence_out(e) for e in records]


@router.get("/{evidence_id}", response_model=EvidenceDetailOut)
def get_evidence_detail(
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves full details for an evidence document including supported claims and evaluations."""
    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_id,
        Evidence.organization_id == current_user.organization_id
    ).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence document not found")

    base_out = _map_evidence_out(evidence)

    associated_reviews = [
        {
            "review_id": assoc.review.id,
            "title": assoc.review.title,
            "status": assoc.review.status,
            "risk_score": assoc.review.risk_score,
            "relevance_notes": assoc.relevance_notes,
            "associated_at": assoc.created_at.isoformat() if assoc.created_at else None,
        }
        for assoc in (evidence.review_associations or [])
        if assoc.review
    ]

    supported_claims = [
        {
            "claim_id": c.id,
            "review_id": c.review_id,
            "claim_text": c.claim_text or c.text,
            "claim_type": c.claim_type,
            "status": c.status,
            "confidence": c.confidence,
        }
        for c in (evidence.claims or [])
    ]

    return EvidenceDetailOut(
        **base_out.model_dump(),
        extracted_text=evidence.extracted_text,
        associated_reviews=associated_reviews,
        supported_claims=supported_claims,
    )


@router.post("/{evidence_id}/associate")
def associate_evidence(
    evidence_id: str,
    payload: AssociateEvidenceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Associates an evidence document with a brand evaluation / review."""
    service = EvidenceService(db)
    try:
        assoc = service.associate_evidence_with_review(
            evidence_id=evidence_id,
            review_id=payload.review_id,
            organization_id=current_user.organization_id,
            actor_id=current_user.id,
            notes=payload.relevance_notes,
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))

    return {
        "status": "success",
        "message": "Evidence document associated with evaluation successfully.",
        "association_id": assoc.id,
        "review_id": payload.review_id,
    }


@router.delete("/{evidence_id}/associate/{review_id}")
def remove_evidence_association(
    evidence_id: str,
    review_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Removes association between an evidence document and a review."""
    assoc = db.query(ReviewEvidence).filter(
        ReviewEvidence.evidence_id == evidence_id,
        ReviewEvidence.review_id == review_id,
        ReviewEvidence.organization_id == current_user.organization_id
    ).first()
    if not assoc:
        raise HTTPException(status_code=404, detail="Association between evidence and evaluation not found.")

    db.delete(assoc)
    db.commit()
    return {"status": "success", "message": "Evidence association removed."}


@router.get("/{evidence_id}/download")
def download_evidence(
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Downloads supporting evidence file securely with authentication and organization isolation.
    Serves with nosniff and attachment headers to prevent active browser execution.
    """
    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_id,
        Evidence.organization_id == current_user.organization_id
    ).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence document not found")

    storage = get_storage()
    file_bytes = storage.get_file(evidence.file_path)
    if not file_bytes:
        evidence.status = EvidenceStatus.UNAVAILABLE.value
        db.commit()
        raise HTTPException(status_code=404, detail="Underlying evidence file content is unavailable in storage.")

    safe_download_filename = evidence.filename or f"evidence_{evidence.id[:8]}{evidence.file_extension}"
    return Response(
        content=file_bytes,
        media_type=evidence.file_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_download_filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
        }
    )


@router.delete("/{evidence_id}")
def delete_evidence(
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes evidence document and underlying object storage file.
    Only creator, brand manager, or administrator is authorized to delete.
    """
    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_id,
        Evidence.organization_id == current_user.organization_id
    ).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence document not found")

    if current_user.role not in [UserRole.ADMIN.value, UserRole.BRAND_MANAGER.value] and evidence.uploaded_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to delete this evidence document")

    service = EvidenceService(db)
    try:
        service.delete_evidence(evidence_id, current_user.organization_id, actor_id=current_user.id)
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))

    return {"status": "success", "message": f"Evidence '{evidence.title}' deleted successfully."}
