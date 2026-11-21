from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user, read_upload_file_bounded
from app.models.user import User
from app.schemas.knowledge import (
    ApplicableKnowledgeResponse,
    FactOut,
    GuidelineOut,
    TermOut,
    RuleOut,
    KnowledgeExtractionResponse,
)
from app.services.scoping_service import get_applicable_knowledge
from app.services.evidence_service import EvidenceService, validate_file_content, extract_evidence_text, EvidenceValidationError
from app.services.knowledge_extractor import parse_knowledge_proposals, count_words
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


def _format_fact_out(f) -> FactOut:
    now = datetime.now(timezone.utc)
    is_exp = f.is_expired
    eff_status = f.effective_status
    days_left = None
    if f.expires_at:
        exp = f.expires_at if f.expires_at.tzinfo else f.expires_at.replace(tzinfo=timezone.utc)
        diff = (exp - now).total_seconds()
        days_left = int(diff // 86400)

    out = FactOut.model_validate(f)
    out.is_expired = is_exp
    out.effective_status = eff_status
    out.days_until_expiry = days_left
    if f.owner:
        out.owner_name = f.owner.full_name
    return out


@router.get("/applicable", response_model=ApplicableKnowledgeResponse)
def get_scoped_applicable_knowledge(
    product: Optional[str] = Query(None, description="Target product (e.g. Starter, Pro, Enterprise, Sovereign Cloud)"),
    region: Optional[str] = Query(None, description="Target region (e.g. Global, India, US, EU)"),
    channel: Optional[str] = Query(None, description="Target publication channel (e.g. Website, Social, Email, Advertisement, Sales Deck)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve all approved facts, guidelines, terminology, and rules applicable to the given
    Product, Region, and Channel combination. Automatically filters out expired or archived information.
    """
    result = get_applicable_knowledge(
        db=db,
        organization_id=current_user.organization_id,
        product=product,
        region=region,
        channel=channel,
    )

    return ApplicableKnowledgeResponse(
        scopes=result["scopes"],
        counts=result["counts"],
        facts=[_format_fact_out(f) for f in result["facts"]],
        guidelines=[GuidelineOut.model_validate(g) for g in result["guidelines"]],
        terms=[TermOut.model_validate(t) for t in result["terms"]],
        rules=[RuleOut.model_validate(r) for r in result["rules"]],
        expired_facts_excluded=[_format_fact_out(f) for f in result["expired_facts_excluded"]],
    )


@router.post("/extract", response_model=KnowledgeExtractionResponse)
async def extract_knowledge_from_document_or_image(
    file: UploadFile = File(...),
    target_category: Optional[str] = Form("all"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Method B: Upload document or image (PDF, DOCX, TXT, MD, PNG, JPG, JPEG, WEBP),
    extract text via OCR / document parsers, and generate structured knowledge candidates
    (Facts, Guidelines, Terms, Rules) for human review and explicit approval.
    Enforces 15MB file size limit, deep content inspection, secure storage, and
    evidence traceability.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid document or image file must be uploaded."
        )

    try:
        file_bytes = await read_upload_file_bounded(file)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {str(e)}"
        )

    # 1. Deep magic byte validation & normalization
    try:
        content_type, ext = validate_file_content(file_bytes, file.filename, file.content_type)
    except EvidenceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 2. Persist evidence record and file in storage for evidence traceability
    evidence_svc = EvidenceService(db)
    try:
        evidence = evidence_svc.upload_evidence(
            file_bytes=file_bytes,
            filename=file.filename,
            organization_id=current_user.organization_id,
            uploaded_by_id=current_user.id,
            description=f"Uploaded for {target_category or 'knowledge'} extraction",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evidence storage failed: {str(e)}"
        )

    # 3. Extract text (OCR for images, parsing for PDF/DOCX/TXT)
    extracted_text = extract_evidence_text(file_bytes, ext) or ""
    if not extracted_text:
        extracted_text = f"Extracted from {file.filename} (Size: {len(file_bytes)} bytes, Type: {content_type})"

    # Update extracted text on the evidence record
    evidence.extracted_text = extracted_text
    db.commit()

    # 4. Generate structured proposals for human review
    proposals = parse_knowledge_proposals(
        text=extracted_text,
        filename=file.filename,
        evidence_id=evidence.id,
        target_category=target_category or "all",
    )

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="KNOWLEDGE_DOCUMENT_EXTRACTED",
        entity_type="Evidence",
        entity_id=evidence.id,
        metadata={
            "filename": file.filename,
            "target_category": target_category,
            "facts_proposed": len(proposals["suggested_facts"]),
            "guidelines_proposed": len(proposals["suggested_guidelines"]),
            "terms_proposed": len(proposals["suggested_terms"]),
            "rules_proposed": len(proposals["suggested_rules"]),
        }
    )

    return KnowledgeExtractionResponse(
        evidence_id=evidence.id,
        filename=evidence.filename,
        file_type=evidence.file_type,
        file_size=evidence.file_size,
        file_hash=evidence.file_hash,
        extracted_text=extracted_text,
        word_count=count_words(extracted_text),
        char_count=len(extracted_text),
        suggested_facts=proposals["suggested_facts"],
        suggested_guidelines=proposals["suggested_guidelines"],
        suggested_terms=proposals["suggested_terms"],
        suggested_rules=proposals["suggested_rules"],
    )

