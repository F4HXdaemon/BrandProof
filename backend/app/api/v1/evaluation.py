import os
import json
import csv
import io
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.scoping_service import get_applicable_knowledge
from app.services.rule_engine import DeterministicRuleEngine
from app.services.citation_gate import CitationGate
from app.services.llm import get_llm_provider
from app.models.knowledge import ApprovedAsset
from app.models.review import ClaimStatus


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
