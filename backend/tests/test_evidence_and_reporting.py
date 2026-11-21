import io
import os
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from PIL import Image
import pytest
from reportlab.pdfgen import canvas

from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.document import Document, DocumentVersion
from app.models.review import Review, ReviewStatus, Claim, ClaimStatus, Finding, FindingStatus, Approval
from app.models.evidence import Evidence, EvidenceStatus, ReviewEvidence
from app.core.security import hash_password, create_access_token
from app.services.evidence_service import EvidenceService
from app.services.rule_engine.base import FindingCandidate
from app.services.citation_gate import CitationGate
from app.services.report_service import ReportGenerator
from app.services.storage import get_storage


def create_token_for(user: User) -> str:
    return create_access_token(
        subject=user.id,
        extra_claims={"role": user.role, "org_id": user.organization_id}
    )


def make_minimal_pdf() -> bytes:
    """Generate a valid, parseable minimal PDF byte stream using ReportLab."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "BrandProof Verified Corporate Evidence")
    c.drawString(100, 700, "SOC-2 Type II Compliance & 99.99% SLA Certification.")
    c.save()
    return buf.getvalue()


def make_minimal_docx() -> bytes:
    """Generate a valid DOCX document using python-docx."""
    import docx
    doc = docx.Document()
    doc.add_paragraph("Corporate ISO-27001 Certification Benchmark")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_minimal_png() -> bytes:
    """Generate a valid PNG image byte stream."""
    buf = io.BytesIO()
    img = Image.new("RGB", (64, 64), color="blue")
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_minimal_jpeg() -> bytes:
    """Generate a valid JPEG image byte stream."""
    buf = io.BytesIO()
    img = Image.new("RGB", (64, 64), color="green")
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. Evidence Upload & Format Validation
# ---------------------------------------------------------------------------

def test_evidence_upload_valid_formats(client, db_session, test_org, admin_user):
    """Test uploading valid PDF, DOCX, TXT, PNG, and JPG files with deep content validation."""
    token = create_token_for(admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    formats = [
        ("soc2_cert.pdf", make_minimal_pdf(), "application/pdf"),
        ("sla_audit.docx", make_minimal_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("benchmark.txt", b"Enterprise Cloud benchmark report showing 99.99% uptime in 2026.", "text/plain"),
        ("chart.png", make_minimal_png(), "image/png"),
        ("stamp.jpg", make_minimal_jpeg(), "image/jpeg"),
    ]

    for filename, content, mime in formats:
        response = client.post(
            "/api/v1/evidence/upload",
            headers=headers,
            data={
                "title": f"Evidence for {filename}",
                "description": "Validated corporate claim documentation",
                "product_scope": "Northstar Cloud",
                "region_scope": "Global",
            },
            files={"file": (filename, content, mime)},
        )
        assert response.status_code == 201, f"Failed for {filename}: {response.text}"
        data = response.json()
        assert data["title"] == f"Evidence for {filename}"
        assert data["filename"] == filename
        assert data["status"] == "Validated"
        assert len(data["sha256_checksum"]) == 64
        assert data["file_size"] == len(content)
        assert data["is_expired"] is False


def test_evidence_upload_magic_byte_sniffing_rejects_spoofed_files(client, db_session, test_org, admin_user):
    """Test deep content inspection catches and marks invalid files with spoofed extensions."""
    token = create_token_for(admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    spoofed_cases = [
        # Spoofed PDF: plain text disguised as .pdf
        ("fake.pdf", b"This is just plain text, not a real PDF at all!", "application/pdf"),
        # Spoofed DOCX: corrupted non-zip binary disguised as .docx
        ("corrupt.docx", b"\x00\x01\x02\x03\x04\x05notazipfile", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        # Spoofed PNG: random noise disguised as .png
        ("fake.png", b"GIF89a spoofed image header that is not png", "image/png"),
        # Binary bytes disguised as .txt
        ("corrupt.txt", b"\x00\xff\xfe\x00\x12\x34\x56\x78\x00\x00\x00binarygarbage", "text/plain"),
    ]

    for filename, content, mime in spoofed_cases:
        response = client.post(
            "/api/v1/evidence/upload",
            headers=headers,
            data={"title": f"Spoofed {filename}"},
            files={"file": (filename, content, mime)},
        )
        assert response.status_code == 400
        error_detail = response.json()["detail"].lower()
        # Deep inspection detected invalid magic bytes / structure
        assert any(term in error_detail for term in ["validation", "signature", "magic", "corrupted", "cannot be identified", "invalid", "decode", "not a valid"])


def test_evidence_upload_size_limits_and_empty_file(client, db_session, test_org, admin_user):
    """Test rejection of empty files and oversized files > 15MB."""
    token = create_token_for(admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Empty file
    res_empty = client.post(
        "/api/v1/evidence/upload",
        headers=headers,
        data={"title": "Empty File"},
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert res_empty.status_code == 400
    assert "empty" in res_empty.json()["detail"].lower()

    # 2. Oversized file (> 15 MB)
    oversized_content = b"A" * (15 * 1024 * 1024 + 1024)
    res_oversized = client.post(
        "/api/v1/evidence/upload",
        headers=headers,
        data={"title": "Oversized Doc"},
        files={"file": ("huge.txt", oversized_content, "text/plain")},
    )
    assert res_oversized.status_code == 413
    assert "15 mb" in res_oversized.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 2. Evidence Listing, Details, and Authenticated Download
# ---------------------------------------------------------------------------

def test_evidence_listing_filtering_and_details(client, db_session, test_org, admin_user):
    """Test evidence listing with status, product, and search query filters, plus details view."""
    token = create_token_for(admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    # Upload test evidence
    pdf_bytes = make_minimal_pdf()
    res = client.post(
        "/api/v1/evidence/upload",
        headers=headers,
        data={
            "title": "SOC-2 Type II Compliance Report 2026",
            "description": "Annual independent third-party security audit",
            "product_scope": "Northstar Cloud",
            "region_scope": "North America",
        },
        files={"file": ("soc2_2026.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201
    ev_id = res.json()["id"]

    # Filter by search
    list_res = client.get("/api/v1/evidence?q=SOC-2", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(i["id"] == ev_id for i in items)

    # Filter by product
    list_prod = client.get("/api/v1/evidence?product=Northstar Cloud", headers=headers)
    assert list_prod.status_code == 200
    assert any(i["id"] == ev_id for i in list_prod.json())

    # Get details
    detail_res = client.get(f"/api/v1/evidence/{ev_id}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == ev_id
    assert detail["title"] == "SOC-2 Type II Compliance Report 2026"
    assert detail["status"] == "Validated"
    assert "associated_reviews" in detail
    assert "supported_claims" in detail


def test_evidence_authenticated_download_and_security_headers(client, db_session, test_org, admin_user):
    """Test authenticated download delivers safe headers and original file bytes."""
    token = create_token_for(admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    pdf_bytes = make_minimal_pdf()
    up_res = client.post(
        "/api/v1/evidence/upload",
        headers=headers,
        data={"title": "Download Test Document"},
        files={"file": ("download_test.pdf", pdf_bytes, "application/pdf")},
    )
    ev_id = up_res.json()["id"]

    # Download with token
    dl_res = client.get(f"/api/v1/evidence/{ev_id}/download", headers=headers)
    assert dl_res.status_code == 200
    assert dl_res.content == pdf_bytes
    assert "attachment" in dl_res.headers.get("Content-Disposition", "")
    assert dl_res.headers.get("X-Content-Type-Options") == "nosniff"

    # Download without token fails 401
    unauth_res = client.get(f"/api/v1/evidence/{ev_id}/download")
    assert unauth_res.status_code == 401


# ---------------------------------------------------------------------------
# 3. Association to Evaluation & CitationGate Validation
# ---------------------------------------------------------------------------

def test_evidence_evaluation_association_and_unlinking(client, db_session, test_org, admin_user, creator_user):
    """Test linking evidence to review, inspecting association, and unlinking."""
    token = create_token_for(admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a review with associated document
    doc = Document(
        organization_id=test_org.id,
        creator_id=creator_user.id,
        filename="ad_campaign.md",
        file_type="text/markdown",
        file_path="mock/path/ad_campaign.md",
        file_size=200,
        processing_status="Ready",
        title="Q3 Enterprise Ad Campaign",
        product="Northstar Cloud",
        region="Global",
        channel="Digital Web",
    )
    db_session.add(doc)
    db_session.flush()

    rev = Review(
        organization_id=test_org.id,
        document_id=doc.id,
        title="Q3 Enterprise Ad Campaign",
        status=ReviewStatus.NEEDS_REVIEW.value,
        product="Northstar Cloud",
        region="Global",
        channel="Digital Web",
    )
    db_session.add(rev)
    db_session.commit()
    db_session.refresh(rev)

    # 2. Upload evidence
    pdf_bytes = make_minimal_pdf()
    up_res = client.post(
        "/api/v1/evidence/upload",
        headers=headers,
        data={"title": "Campaign Evidence Doc"},
        files={"file": ("campaign_evidence.pdf", pdf_bytes, "application/pdf")},
    )
    ev_id = up_res.json()["id"]

    # 3. Associate evidence with review
    assoc_res = client.post(
        f"/api/v1/evidence/{ev_id}/associate",
        headers=headers,
        json={"review_id": rev.id, "citation_note": "Referenced in section 2"},
    )
    assert assoc_res.status_code == 200
    assert assoc_res.json()["status"] in ["associated", "success"]

    # Verify review detail includes evidence
    rev_res = client.get(f"/api/v1/reviews/{rev.id}", headers=headers)
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert any(e["id"] == ev_id for e in rev_data.get("evidence_documents", []))

    # 4. Unlink association
    del_assoc_res = client.delete(f"/api/v1/evidence/{ev_id}/associate/{rev.id}", headers=headers)
    assert del_assoc_res.status_code == 200
    assert del_assoc_res.json()["status"] in ["unlinked", "success"]

    # Verify review no longer includes evidence
    rev_res_after = client.get(f"/api/v1/reviews/{rev.id}", headers=headers)
    assert not any(e["id"] == ev_id for e in rev_res_after.json().get("evidence_documents", []))


def test_citation_gate_with_evidence_rules(client, db_session, test_org, admin_user):
    """Test CitationGate rule enforcement on corporate evidence documents:
    - Valid, in-scope evidence permits verification
    - Expired evidence is rejected
    - Invalid evidence is rejected
    - Out-of-scope evidence is rejected
    """
    now = datetime.now(timezone.utc)

    # 1. Valid Evidence
    valid_ev = Evidence(
        organization_id=test_org.id,
        uploaded_by_id=admin_user.id,
        title="Valid ESG Carbon Neutral Certification",
        filename="esg.pdf",
        file_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        file_path="mock/path/esg.pdf",
        file_hash="a" * 64,
        status=EvidenceStatus.VALIDATED.value,
        product_scope="Northstar Cloud",
        region_scope="Global",
        channel_scope="All",
        expires_at=now + timedelta(days=90),
    )
    db_session.add(valid_ev)

    # 2. Expired Evidence
    expired_ev = Evidence(
        organization_id=test_org.id,
        uploaded_by_id=admin_user.id,
        title="Expired 2024 SLA Certificate",
        filename="sla_expired.pdf",
        file_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        file_path="mock/path/expired.pdf",
        file_hash="b" * 64,
        status=EvidenceStatus.VALIDATED.value,
        product_scope="Northstar Cloud",
        region_scope="Global",
        channel_scope="All",
        expires_at=now - timedelta(days=10),  # expired 10 days ago
    )
    db_session.add(expired_ev)

    # 3. Invalid Evidence (failed magic bytes)
    invalid_ev = Evidence(
        organization_id=test_org.id,
        uploaded_by_id=admin_user.id,
        title="Corrupted Spec Sheet",
        filename="corrupted.pdf",
        file_type="application/pdf",
        file_extension=".pdf",
        file_size=512,
        file_path="mock/path/corrupted.pdf",
        file_hash="c" * 64,
        status=EvidenceStatus.INVALID.value,
        product_scope="Northstar Cloud",
        region_scope="Global",
    )
    db_session.add(invalid_ev)

    # 4. Out-of-scope Evidence
    scope_ev = Evidence(
        organization_id=test_org.id,
        uploaded_by_id=admin_user.id,
        title="GovCloud Specialized Defense Clearance",
        filename="defense.pdf",
        file_type="application/pdf",
        file_extension=".pdf",
        file_size=2048,
        file_path="mock/path/defense.pdf",
        file_hash="d" * 64,
        status=EvidenceStatus.VALIDATED.value,
        product_scope="GovCloud Only",
        region_scope="US Gov",
        channel_scope="Direct",
    )
    db_session.add(scope_ev)
    db_session.commit()

    gate = CitationGate(db=db_session, organization_id=test_org.id)

    context = {
        "product": "Northstar Cloud",
        "region": "Global",
        "channel": "Digital Web",
    }

    def make_candidate(ev_id: str, title: str) -> FindingCandidate:
        return FindingCandidate(
            finding_type="substantiation",
            severity="High",
            title=title,
            message="Evidence backed claim",
            source_type="evidence",
            source_id=ev_id,
            source_reference=f"Corporate Document #{ev_id}",
        )

    # Case A: Valid evidence passes CitationGate
    is_valid, reason = gate.validate_candidate(
        make_candidate(valid_ev.id, "Valid Claim"),
        context=context,
    )
    assert is_valid is True
    assert reason is None

    # Case B: Expired evidence is strictly rejected
    is_valid, reason = gate.validate_candidate(
        make_candidate(expired_ev.id, "Expired Support"),
        context=context,
    )
    assert is_valid is False
    assert "expired" in reason.lower()

    # Case C: Invalid status is strictly rejected
    is_valid, reason = gate.validate_candidate(
        make_candidate(invalid_ev.id, "Corrupt Doc"),
        context=context,
    )
    assert is_valid is False
    assert "invalid" in reason.lower()

    # Case D: Out of product/region scope is strictly rejected
    is_valid, reason = gate.validate_candidate(
        make_candidate(scope_ev.id, "Defense Scope"),
        context=context,
    )
    assert is_valid is False
    assert "scoped to product" in reason.lower()


# ---------------------------------------------------------------------------
# 4. Multi-Tenant Organization Isolation
# ---------------------------------------------------------------------------

def test_evidence_multi_tenant_isolation(client, db_session, test_org, admin_user):
    """Verify Org B cannot view, download, associate, or delete Org A's evidence."""
    # Org A uploads evidence
    token_a = create_token_for(admin_user)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    pdf_bytes = make_minimal_pdf()
    up_res = client.post(
        "/api/v1/evidence/upload",
        headers=headers_a,
        data={"title": "Org A Confidential Patent"},
        files={"file": ("patent_org_a.pdf", pdf_bytes, "application/pdf")},
    )
    ev_a_id = up_res.json()["id"]

    # Create Org B and user
    uid_b = uuid.uuid4().hex[:8]
    org_b = Organization(name=f"Org B {uid_b}", slug=f"org-b-{uid_b}", domain=f"orgb-{uid_b}.com")
    db_session.add(org_b)
    db_session.commit()
    user_b = User(
        organization_id=org_b.id,
        email=f"user-b-{uid_b}@orgb.com",
        hashed_password=hash_password("Pass1234!"),
        full_name="User B",
        role=UserRole.ADMIN.value,
    )
    db_session.add(user_b)
    db_session.commit()

    token_b = create_token_for(user_b)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. Org B listing does NOT contain Org A's document
    list_b = client.get("/api/v1/evidence", headers=headers_b)
    assert list_b.status_code == 200
    assert not any(i["id"] == ev_a_id for i in list_b.json())

    # 2. Org B cannot get Org A's document detail
    get_b = client.get(f"/api/v1/evidence/{ev_a_id}", headers=headers_b)
    assert get_b.status_code == 404

    # 3. Org B cannot download Org A's document
    dl_b = client.get(f"/api/v1/evidence/{ev_a_id}/download", headers=headers_b)
    assert dl_b.status_code == 404

    # 4. Org B cannot delete Org A's document
    del_b = client.delete(f"/api/v1/evidence/{ev_a_id}", headers=headers_b)
    assert del_b.status_code == 404


# ---------------------------------------------------------------------------
# 5. Safe Evidence Deletion (Storage First, DB Second)
# ---------------------------------------------------------------------------

def test_safe_evidence_deletion(client, db_session, test_org, admin_user):
    """Test safe evidence deletion: underlying file is removed from storage backend and DB records cleanly removed."""
    token = create_token_for(admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    pdf_bytes = make_minimal_pdf()
    up_res = client.post(
        "/api/v1/evidence/upload",
        headers=headers,
        data={"title": "To Be Deleted Document"},
        files={"file": ("delete_me.pdf", pdf_bytes, "application/pdf")},
    )
    assert up_res.status_code == 201
    ev_id = up_res.json()["id"]

    # Verify record in DB
    ev_model = db_session.query(Evidence).filter(Evidence.id == ev_id).first()
    assert ev_model is not None
    storage_path = ev_model.storage_path

    storage = get_storage()
    assert storage.exists(storage_path) is True

    # Delete evidence
    del_res = client.delete(f"/api/v1/evidence/{ev_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] in ["deleted", "success"]

    # Verify underlying file was deleted from storage
    assert storage.exists(storage_path) is False

    # Verify DB record is gone
    db_session.expire_all()
    ev_deleted = db_session.query(Evidence).filter(Evidence.id == ev_id).first()
    assert ev_deleted is None


# ---------------------------------------------------------------------------
# 6. Evaluation Audit Report Generation (PDF & JSON)
# ---------------------------------------------------------------------------

def test_evaluation_pdf_and_json_report_generation(client, db_session, test_org, admin_user, creator_user):
    """Test generating a publication-quality PDF audit report and structured JSON report."""
    token = create_token_for(admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a complete review with document, version, claims, findings, evidence, and approvals
    doc = Document(
        organization_id=test_org.id,
        creator_id=creator_user.id,
        filename="quantum_ad.md",
        file_type="text/markdown",
        file_path="mock/path/quantum_ad.md",
        file_size=350,
        processing_status="Ready",
        title="Enterprise Quantum Cloud Q4 Ad",
        product="Northstar Cloud",
        region="North America",
        channel="Digital Banner",
    )
    db_session.add(doc)
    db_session.flush()

    ver = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        file_path="mock/path/quantum_ad_v1.md",
        file_size=100,
        extracted_text="Enterprise Quantum Cloud delivers 99.99% uptime and zero latency across North America.",
    )
    db_session.add(ver)
    db_session.flush()

    rev = Review(
        organization_id=test_org.id,
        document_id=doc.id,
        version_id=ver.id,
        reviewer_id=admin_user.id,
        title="Enterprise Quantum Cloud Q4 Ad",
        status=ReviewStatus.APPROVED.value,
        product="Northstar Cloud",
        region="North America",
        channel="Digital Banner",
        risk_score=7.0,
        risk_level="High",
        purpose="Promote 99.99% uptime and zero-latency cloud tier",
    )
    db_session.add(rev)
    db_session.flush()

    # Claims
    c1 = Claim(
        review_id=rev.id,
        document_id=doc.id,
        claim_text="Guaranteed 99.99% uptime across all North American enterprise nodes.",
        status=ClaimStatus.SUPPORTED.value,
        reasoning="SOC-2 Type II Audit Report",
    )
    c2 = Claim(
        review_id=rev.id,
        document_id=doc.id,
        claim_text="Zero latency cloud execution with 100% data residency.",
        status=ClaimStatus.UNSUPPORTED.value,
    )
    db_session.add_all([c1, c2])

    # Finding
    f1 = Finding(
        review_id=rev.id,
        document_version_id=ver.id,
        severity="High",
        status=FindingStatus.OPEN.value,
        title="Unsubstantiated Zero Latency Claim",
        message="Zero latency claims require independent network benchmarking.",
        source_reference="CitationGate Principle: Substantiation Required",
        suggested_replacement="Replace 'zero latency' with 'sub-millisecond p99 latency'.",
    )
    db_session.add(f1)

    # Human Approval with Override
    appr = Approval(
        review_id=rev.id,
        document_id=doc.id,
        document_version_id=ver.id,
        approver_id=admin_user.id,
        status="Approved",
        is_override=True,
        override_reason="Executive Brand Manager waiver granted for limited beta program.",
        comments="Approved under waiver authorization #2026-881.",
    )
    db_session.add(appr)
    db_session.commit()

    # Attach an evidence document
    pdf_bytes = make_minimal_pdf()
    up_res = client.post(
        "/api/v1/evidence/upload",
        headers=headers,
        data={"title": "Q4 Performance Benchmarks", "review_id": rev.id},
        files={"file": ("q4_bench.pdf", pdf_bytes, "application/pdf")},
    )
    assert up_res.status_code == 201

    db_session.expire_all()

    # 2. Test PDF Report via Reviews Endpoint
    pdf_res = client.get(f"/api/v1/reviews/{rev.id}/report", headers=headers)
    assert pdf_res.status_code == 200
    assert pdf_res.headers["Content-Type"] == "application/pdf"
    assert "attachment" in pdf_res.headers["Content-Disposition"]
    assert pdf_res.content.startswith(b"%PDF-")
    assert len(pdf_res.content) > 5000  # Substantial PDF document

    # 3. Test PDF Report via Evaluation Endpoint
    eval_pdf_res = client.get(f"/api/v1/evaluation/{rev.id}/report", headers=headers)
    assert eval_pdf_res.status_code == 200
    assert eval_pdf_res.content.startswith(b"%PDF-")

    # 4. Test JSON Report
    json_res = client.get(f"/api/v1/evaluation/{rev.id}/report?format=json", headers=headers)
    assert json_res.status_code == 200
    report_data = json_res.json()
    assert report_data["evaluation_id"] == rev.id
    assert report_data["campaign_title"] == "Enterprise Quantum Cloud Q4 Ad"
    assert report_data["risk_score"] == 7.0
    assert report_data["risk_level"] == "High"
    assert len(report_data["claims"]) == 2
    assert len(report_data["findings"]) == 1
    assert len(report_data["evidence_documents"]) >= 1
    assert len(report_data["approvals"]) >= 1
    assert report_data["approvals"][0]["is_override"] is True
    assert "NOT constitute legal advice" in report_data["disclaimer"]
    assert len(report_data["report_version_fingerprint"]) > 0
