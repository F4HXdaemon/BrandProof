import io
import pytest
from PIL import Image
from app.models.evidence import Evidence
from app.models.review import Review, ReviewStatus
from app.models.document import Document, DocumentVersion
from app.services.knowledge_extractor import parse_knowledge_proposals


def test_extract_knowledge_from_text_document(client, db_session, test_org, admin_user, admin_token):
    """Test extracting knowledge from a text document with complete evidence traceability."""
    sample_text = (
        "BrandProof delivers automated enterprise compliance.\n"
        "Fact: BrandProof reduces review turnaround by 80% across enterprise workflows.\n"
        "Guideline: Ensure all visual assets include the official high-resolution logo.\n"
        "Rule: Claims citing performance metrics must provide certified benchmark references.\n"
    )
    file_bytes = io.BytesIO(sample_text.encode("utf-8"))

    response = client.post(
        "/api/v1/knowledge/extract",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"target_category": "fact"},
        files={"file": ("brand_specs.txt", file_bytes, "text/plain")},
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["filename"] == "brand_specs.txt"
    assert data["file_type"] == "text/plain"
    assert data["evidence_id"] is not None
    assert len(data["file_hash"]) == 64
    assert "80%" in data["extracted_text"]
    assert len(data["suggested_facts"]) > 0

    # Verify candidates structure
    candidate = data["suggested_facts"][0]
    assert "title" in candidate
    assert "canonical_value" in candidate
    assert "brand_specs.txt" in candidate["source_reference"]

    # Verify Evidence record in database
    evidence = db_session.query(Evidence).filter(Evidence.id == data["evidence_id"]).first()
    assert evidence is not None
    assert evidence.filename == "brand_specs.txt"
    assert evidence.organization_id == test_org.id
    assert evidence.uploaded_by_id == admin_user.id
    assert evidence.file_hash == data["file_hash"]
    assert evidence.status == "Validated"


def test_extract_knowledge_from_image_png(client, db_session, test_org, admin_token):
    """Test uploading a PNG image for knowledge extraction and OCR inspection."""
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    response = client.post(
        "/api/v1/knowledge/extract",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"target_category": "guideline"},
        files={"file": ("product_card.png", buf, "image/png")},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["filename"] == "product_card.png"
    assert data["evidence_id"] is not None
    assert len(data["file_hash"]) == 64
    assert len(data["suggested_guidelines"]) > 0


def test_extract_knowledge_from_image_webp(client, db_session, test_org, admin_token):
    """Test uploading a WEBP image for knowledge extraction and OCR inspection."""
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="WEBP")
    buf.seek(0)

    response = client.post(
        "/api/v1/knowledge/extract",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"target_category": "term"},
        files={"file": ("trademark_badge.webp", buf, "image/webp")},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["filename"] == "trademark_badge.webp"
    assert data["evidence_id"] is not None
    assert len(data["suggested_terms"]) > 0


def test_file_size_limit_rejection(client, admin_token):
    """Test 15MB file size limit is strictly enforced."""
    # 15MB + 1 byte
    large_payload = b"0" * (15 * 1024 * 1024 + 1)
    buf = io.BytesIO(large_payload)

    response = client.post(
        "/api/v1/knowledge/extract",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"target_category": "fact"},
        files={"file": ("too_large.txt", buf, "text/plain")},
    )

    assert response.status_code in [400, 413]
    if response.status_code == 400:
        assert "exceeds 15MB" in response.json()["detail"]


def test_disallowed_file_extension_rejection(client, admin_token):
    """Test invalid or unapproved file extensions are rejected."""
    buf = io.BytesIO(b"executable payload")

    response = client.post(
        "/api/v1/knowledge/extract",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"target_category": "fact"},
        files={"file": ("malicious.exe", buf, "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


def test_candidate_parser_all_categories():
    """Test knowledge_extractor candidate parser accurately segments each category."""
    raw_text = (
        "Apex Engine achieves 99.99% availability in SLA benchmarks.\n"
        "Never use outdated competitor terminology in marketing copy.\n"
        "Northstar Pro is our primary enterprise product brand with 'BrandProof'.\n"
        "Every pricing claim must display tax disclaimer in footnote.\n"
    )

    # Facts
    fact_res = parse_knowledge_proposals(raw_text, "sla_guide.pdf", "ev-123", "fact")
    assert len(fact_res["suggested_facts"]) >= 1
    assert any("canonical_value" in c for c in fact_res["suggested_facts"])

    # Guidelines
    guideline_res = parse_knowledge_proposals(raw_text, "sla_guide.pdf", "ev-123", "guideline")
    assert len(guideline_res["suggested_guidelines"]) >= 1
    assert any("principle" in c for c in guideline_res["suggested_guidelines"])

    # Terms
    term_res = parse_knowledge_proposals(raw_text, "sla_guide.pdf", "ev-123", "term")
    assert len(term_res["suggested_terms"]) >= 1
    assert any("approved_term" in c for c in term_res["suggested_terms"])

    # Rules
    rule_res = parse_knowledge_proposals(raw_text, "sla_guide.pdf", "ev-123", "rule")
    assert len(rule_res["suggested_rules"]) >= 1
    assert any("rule_type" in c for c in rule_res["suggested_rules"])


def test_review_re_evaluate_endpoint(client, db_session, test_org, admin_user, admin_token):
    """Test re-evaluating a review refreshes audit findings, risk score, and status."""
    # Create Document and DocumentVersion
    doc = Document(
        organization_id=test_org.id,
        creator_id=admin_user.id,
        title="Spring Campaign Launch",
        filename="spring_campaign.txt",
        file_type="text/plain",
        file_path="documents/spring_campaign.txt",
        file_size=120,
        product="All Products",
        region="Global",
        channel="Marketing",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    doc_version = DocumentVersion(
        document_id=doc.id,
        created_by_id=admin_user.id,
        version_number=1,
        file_path="documents/spring_campaign_v1.txt",
        file_size=120,
        extracted_text="BrandProof delivers 99.9% uptime with automated governance active across all cloud channels.",
    )
    db_session.add(doc_version)
    db_session.commit()
    db_session.refresh(doc_version)

    # Create Review
    review = Review(
        document_id=doc.id,
        version_id=doc_version.id,
        organization_id=test_org.id,
        title="Spring Campaign Evaluation",
        status=ReviewStatus.PROCESSING.value,
        processing_status="Processing",
        risk_score=0.0,
        risk_level="Low",
    )
    db_session.add(review)
    db_session.commit()
    db_session.refresh(review)

    # Trigger re-evaluation
    response = client.post(
        f"/api/v1/reviews/{review.id}/re-evaluate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == review.id
    assert data["processing_status"] in ["Completed", "Requires attention"]

    # Verify database state refreshed
    refreshed_review = db_session.query(Review).filter(Review.id == review.id).first()
    assert refreshed_review.processing_status in ["Completed", "Requires attention"]
