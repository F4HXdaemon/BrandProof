import os
import json
import csv
import io
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Response, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import or_
from app.database import get_db
from app.core.dependencies import get_current_user, read_upload_file_bounded
from app.models.user import User
from app.models.document import Document
from app.models.review import Review, ReviewStatus, ClaimStatus
from app.schemas.document_and_review import (
    ReviewOut, ReviewDetailOut, EvaluationCreate, EvaluationUpdate
)
from app.services.audit_service import record_audit_event
from app.services.scoping_service import get_applicable_knowledge
from app.services.rule_engine import DeterministicRuleEngine
from app.services.citation_gate import CitationGate
from app.services.llm import get_llm_provider
from app.services.review_orchestrator import ReviewOrchestrator
from app.models.knowledge import ApprovedAsset
from app.api.v1.reviews import _map_review_out, get_review_detail


router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

BENCHMARK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "evaluation",
    "benchmark_dataset.json"
)


def _load_benchmark_dataset() -> List[Dict[str, Any]]:
    if not os.path.exists(BENCHMARK_PATH):
        return []
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("", response_model=List[ReviewOut])
def list_evaluations(
    status: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists persisted brand evaluations scoped to the authenticated user's organization.
    Supports filtering by evaluation/review status, product, region, channel, and query.
    """
    query = db.query(Review).filter(Review.organization_id == current_user.organization_id)
    if status and status != "All":
        query = query.filter(Review.status == status)
    if product and product != "All":
        query = query.filter(Review.product == product)
    if region and region != "All":
        query = query.filter(Review.region == region)
    if channel and channel != "All":
        query = query.filter(Review.channel == channel)

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.outerjoin(Document, Review.document_id == Document.id).filter(
            or_(
                Review.title.ilike(term),
                Review.summary.ilike(term),
                Document.title.ilike(term),
            )
        )

    evaluations = query.order_by(Review.created_at.desc()).all()
    return [_map_review_out(r) for r in evaluations]


@router.get("/run", response_model=Dict[str, Any])
def run_evaluation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Executes automated evaluation of the BrandProof governance pipeline
    against the ground truth benchmark dataset.
    Calculates TP, FP, FN, Precision, Recall, and F1 Score.
    """
    cases = _load_benchmark_dataset()
    engine = DeterministicRuleEngine()
    llm = get_llm_provider()

    total_tp = 0
    total_fp = 0
    total_fn = 0
    detailed_cases = []

    for case in cases:
        text = case.get("text", "")
        ctx = case.get("context", {})
        expected_list = case.get("expected_findings", [])

        # Fetch knowledge scoped to case context
        knowledge = get_applicable_knowledge(
            db=db,
            organization_id=current_user.organization_id,
            product=ctx.get("product"),
            region=ctx.get("region"),
            channel=ctx.get("channel"),
        )
        approved_assets = db.query(ApprovedAsset).filter(
            ApprovedAsset.organization_id == current_user.organization_id,
            ApprovedAsset.active == True
        ).all()
        knowledge["assets"] = approved_assets

        # Run Rule Engine
        candidates = engine.run_all(
            text=text,
            chunks=[],
            context=ctx,
            knowledge=knowledge,
        )

        # Run Claims Analysis
        all_facts = knowledge.get("facts", []) + knowledge.get("expired_facts_excluded", [])
        proposals = llm.extract_claims(text)
        for p in proposals:
            analysis = llm.analyze_claim_against_facts(p.claim_text, all_facts, ctx)
            if analysis.status in [ClaimStatus.CONFLICTS.value, ClaimStatus.EXPIRED.value] and analysis.matched_fact_id:
                matched_f = next((f for f in all_facts if f.id == analysis.matched_fact_id), None)
                if matched_f:
                    f_type = "numeric_conflict" if analysis.status == ClaimStatus.CONFLICTS.value else "expired_fact"
                    from app.services.rule_engine.base import FindingCandidate
                    candidates.append(
                        FindingCandidate(
                            finding_type=f_type,
                            severity="Blocker" if f_type == "numeric_conflict" else "High",
                            title=f"Conflict: {matched_f.title}",
                            message=analysis.reasoning or "Conflict detected",
                            quoted_text=p.claim_text,
                            source_type="fact",
                            source_id=matched_f.id,
                            source_reference=matched_f.source_reference,
                            checker="ClaimLedger"
                        )
                    )

        # Citation Gate Validation
        gate = CitationGate(db, current_user.organization_id)
        valid_findings, quarantined = gate.validate_and_filter(candidates, ctx)

        # Calculate TP, FP, FN for this test case
        detected_types = [f.finding_type.lower() for f in valid_findings]
        tp = 0
        fn = 0
        missed = []

        for exp in expected_list:
            exp_type = exp.get("finding_type", "").lower()
            if exp_type in detected_types:
                tp += 1
            else:
                fn += 1
                missed.append(exp)

        fp = max(0, len(valid_findings) - tp)

        total_tp += tp
        total_fp += fp
        total_fn += fn

        detailed_cases.append({
            "case_id": case.get("id"),
            "title": case.get("title"),
            "text": text,
            "expected_count": len(expected_list),
            "detected_count": len(valid_findings),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "missed_expected": missed,
            "detected_findings": [
                {
                    "title": f.title,
                    "type": f.finding_type,
                    "severity": f.severity,
                    "quoted": f.quoted_text,
                    "source": f.source_reference,
                }
                for f in valid_findings
            ]
        })

    # Global precision, recall, F1
    precision = round(total_tp / (total_tp + total_fp), 3) if (total_tp + total_fp) > 0 else 1.0
    recall = round(total_tp / (total_tp + total_fn), 3) if (total_tp + total_fn) > 0 else 1.0
    f1 = round(2 * (precision * recall) / (precision + recall), 3) if (precision + recall) > 0 else 0.0

    return {
        "metrics": {
            "total_benchmark_cases": len(cases),
            "true_positives": total_tp,
            "false_positives": total_fp,
            "false_negatives": total_fn,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "accuracy_percent": round(f1 * 100, 1),
        },
        "cases": detailed_cases,
    }


@router.get("/export")
def export_evaluation_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Exports benchmark evaluation results to downloadable CSV."""
    results = run_evaluation(current_user=current_user, db=db)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Case ID", "Title", "Text", "Expected Count", "Detected Count", "TP", "FP", "FN", "Status"])
    for c in results["cases"]:
        status = "PASSED" if c["false_negatives"] == 0 and c["false_positives"] == 0 else "PARTIAL"
        writer.writerow([
            c["case_id"],
            c["title"],
            c["text"],
            c["expected_count"],
            c["detected_count"],
            c["true_positives"],
            c["false_positives"],
            c["false_negatives"],
            status
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=brandproof_evaluation_results.csv"}
    )


@router.post("/new", response_model=ReviewDetailOut)
async def submit_new_evaluation(
    title: str = Form(...),
    product: str = Form("All"),
    region: str = Form("Global"),
    channel: str = Form("All"),
    content_type: str = Form("General Marketing"),
    intended_audience: str = Form("All Audiences"),
    purpose: Optional[str] = Form(None),
    supporting_evidence: Optional[str] = Form(None),
    pasted_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submits marketing content / advertisement text for brand evaluation (via multipart/form-data).
    Accepts campaign title, content text or file upload, category, context scopes, and supporting evidence.
    Executes Document Ingestion, text extraction & chunking, and the full BrandProof governance
    audit pipeline (Rule engine, Claim extraction, CitationGate, Risk scoring).
    Persists all records to the database scoped to current user's organization.
    """
    if not title or not title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evaluation name / campaign title is required."
        )

    if not file and (not pasted_text or not pasted_text.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either marketing content / text or an uploaded document (.txt, .docx, .pdf, .md) must be provided."
        )

    intent_card = {
        "title": title.strip(),
        "product": product.strip() if product else "All",
        "region": region.strip() if region else "Global",
        "channel": channel.strip() if channel else "All",
        "content_type": content_type.strip() if content_type else "General Marketing",
        "intended_audience": intended_audience.strip() if intended_audience else "All Audiences",
        "purpose": purpose.strip() if purpose else "",
        "supporting_evidence": supporting_evidence.strip() if supporting_evidence else "",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation processing failed: {str(e)}"
        )

    return get_review_detail(review.id, current_user, db)


@router.post("", response_model=ReviewDetailOut)
def create_evaluation_json(
    payload: EvaluationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submits marketing content / advertisement text for brand evaluation (via JSON).
    Accepts campaign title, content or pasted_text, category, context scopes, and supporting evidence.
    Executes Document Ingestion, text extraction & chunking, and the full BrandProof governance
    audit pipeline (Rule engine, Claim extraction, CitationGate, Risk scoring).
    Persists all records to the database scoped to current user's organization.
    """
    if not payload.title or not payload.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evaluation name / campaign title is required."
        )

    raw_content = payload.content or payload.pasted_text
    if not raw_content or not raw_content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Marketing content / advertisement text must be provided in 'content' or 'pasted_text'."
        )

    intent_card = {
        "title": payload.title.strip(),
        "product": (payload.product or "All").strip(),
        "region": (payload.region or "Global").strip(),
        "channel": (payload.channel or "All").strip(),
        "content_type": (payload.content_type or "General Marketing").strip(),
        "intended_audience": (payload.intended_audience or "All Audiences").strip(),
        "purpose": (payload.purpose or "").strip(),
        "supporting_evidence": (payload.supporting_evidence or "").strip(),
    }

    orchestrator = ReviewOrchestrator(db)
    try:
        review, doc, ver = orchestrator.ingest_pasted_text(
            text_content=raw_content.strip(),
            title=payload.title.strip(),
            creator_id=current_user.id,
            organization_id=current_user.organization_id,
            intent_card=intent_card,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation processing failed: {str(e)}"
        )

    return get_review_detail(review.id, current_user, db)


@router.get("/{evaluation_id}/report")
def get_evaluation_report(
    evaluation_id: str,
    format: Optional[str] = Query("pdf"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates and downloads an official BrandProof evaluation audit report.
    Supports downloadable PDF (default) and structured JSON telemetry.
    Includes full branding, claims ledger, CitationGate findings, risk telemetry,
    associated evidence documents, human approvals/overrides, and legal limitation disclaimers.
    """
    review = db.query(Review).filter(
        Review.id == evaluation_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found or unauthorized access"
        )

    from app.services.report_service import ReportGenerator
    generator = ReportGenerator(review, db)

    if (format or "pdf").lower() == "json":
        return generator.get_report_json()

    pdf_bytes = generator.generate_pdf()
    safe_filename = f"BrandProof_Report_{review.id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
        }
    )


@router.get("/{evaluation_id}", response_model=ReviewDetailOut)
def get_evaluation(
    evaluation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves full evaluation details including risk score, claims ledger, and findings.
    Ensures strict organization isolation.
    """
    review = db.query(Review).filter(
        Review.id == evaluation_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found or unauthorized access"
        )

    return get_review_detail(review.id, current_user, db)


@router.patch("/{evaluation_id}", response_model=ReviewDetailOut)
def update_evaluation(
    evaluation_id: str,
    payload: EvaluationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Updates evaluation metadata (title, summary, purpose, context scopes).
    Updates linked document title if evaluation title is renamed.
    """
    review = db.query(Review).filter(
        Review.id == evaluation_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found or unauthorized access"
        )

    if payload.title is not None and payload.title.strip():
        review.title = payload.title.strip()
        if review.document:
            review.document.title = payload.title.strip()
    if payload.summary is not None:
        review.summary = payload.summary.strip()
    if payload.purpose is not None:
        review.purpose = payload.purpose.strip()
    if payload.product is not None:
        review.product = payload.product.strip()
    if payload.region is not None:
        review.region = payload.region.strip()
    if payload.channel is not None:
        review.channel = payload.channel.strip()
    if payload.content_type is not None:
        review.content_type = payload.content_type.strip()
    if payload.intended_audience is not None:
        review.intended_audience = payload.intended_audience.strip()

    intent = dict(review.intent_card or {})
    if payload.title:
        intent["title"] = review.title
    if payload.product:
        intent["product"] = review.product
    if payload.region:
        intent["region"] = review.region
    if payload.channel:
        intent["channel"] = review.channel
    if payload.purpose:
        intent["purpose"] = review.purpose
    review.intent_card = intent
    flag_modified(review, "intent_card")

    db.commit()
    db.refresh(review)

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="EVALUATION_UPDATED",
        entity_type="Review",
        entity_id=review.id,
        metadata={"title": review.title}
    )

    return get_review_detail(review.id, current_user, db)


@router.delete("/{evaluation_id}", response_model=Dict[str, Any])
def delete_evaluation(
    evaluation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes an evaluation and cascades cleanup of findings, claims, comments, approvals.
    Cleans up associated document if no other evaluations reference it.
    """
    review = db.query(Review).filter(
        Review.id == evaluation_id,
        Review.organization_id == current_user.organization_id
    ).first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found or unauthorized access"
        )

    doc_id = review.document_id
    eval_id = review.id
    eval_title = review.title or "Evaluation"

    db.delete(review)
    db.commit()

    if doc_id:
        remaining = db.query(Review).filter(Review.document_id == doc_id).count()
        if remaining == 0:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                db.delete(doc)
                db.commit()

    record_audit_event(
        db=db,
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        action="EVALUATION_DELETED",
        entity_type="Review",
        entity_id=eval_id,
        metadata={"title": eval_title}
    )

    return {
        "status": "success",
        "message": f"Evaluation '{eval_title}' deleted successfully.",
        "id": eval_id
    }


@router.post("/{evaluation_id}/re-evaluate", response_model=ReviewDetailOut)
@router.post("/{evaluation_id}/retry", response_model=ReviewDetailOut)
def re_evaluate_evaluation(
    evaluation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Re-executes the brand evaluation scan for an existing evaluation ID.
    """
    from app.api.v1.reviews import re_evaluate_review
    return re_evaluate_review(review_id=evaluation_id, current_user=current_user, db=db)

