import io
import uuid
import pytest
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.document import Document, DocumentVersion, DocumentChunk
from app.models.review import Review, ReviewStatus, Claim, ClaimStatus, Finding, FindingStatus, Approval
from app.models.knowledge import Fact, FactStatus, Rule, SeverityLevel
from app.core.security import hash_password, create_access_token
from app.services.risk_scoring import calculate_risk_score, SEVERITY_WEIGHTS


def create_token_for(user: User) -> str:
    return create_access_token(
        subject=user.id,
        extra_claims={"role": user.role, "org_id": user.organization_id}
    )


def test_evaluation_weights_adherence():
    """Verify CitationGate and Risk Scoring strictly use the established severity weights."""
    assert SEVERITY_WEIGHTS["Info"] == 1.0
    assert SEVERITY_WEIGHTS["Warning"] == 3.0
    assert SEVERITY_WEIGHTS["High"] == 7.0
    assert SEVERITY_WEIGHTS["Blocker"] == 15.0

    class MockFinding:
        def __init__(self, severity, status="Open"):
            self.severity = severity
            self.status = status

    findings = [
        MockFinding("Info"),
        MockFinding("Warning"),
        MockFinding("High"),
        MockFinding("Blocker"),
    ]
    score_data = calculate_risk_score(findings)
    # 1.0 + 3.0 + 7.0 + 15.0 = 26.0
    assert score_data["risk_score"] == 26.0
    assert score_data["risk_level"] == "High"


def test_evaluation_creation_with_pasted_text(client, db_session, test_org, creator_user):
    """Test full creation and persistence of brand evaluation using pasted advertisement copy."""
    token = create_token_for(creator_user)
    headers = {"Authorization": f"Bearer {token}"}

    form_data = {
        "title": "Apex Cloud Q3 Launch Ad",
        "product": "Northstar Pro",
        "region": "India",
        "channel": "Advertisement",
        "content_type": "Ad Copy",
        "intended_audience": "Enterprise IT Decision Makers",
        "purpose": "Promote verified cloud uptime and speed",
        "supporting_evidence": "Doc Ref #CERT-2026-99",
        "pasted_text": "Apex Cloud delivers 99.9% uptime with automated compliance guardrails active from day one.",
    }

    res = client.post("/api/v1/evaluation/new", data=form_data, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    eval_id = data["id"]
    assert eval_id is not None
    assert data["title"] == "Apex Cloud Q3 Launch Ad"
    assert data["status"] == "Needs Review"
    assert data["product"] == "Northstar Pro"
    assert data["region"] == "India"
    assert data["channel"] == "Advertisement"
    assert data["content_type"] == "Ad Copy"
    assert data["intent_card"]["supporting_evidence"] == "Doc Ref #CERT-2026-99"

    # Verify real DB persistence
    review_db = db_session.query(Review).filter(Review.id == eval_id).first()
    assert review_db is not None
    assert review_db.organization_id == test_org.id
    assert review_db.document_id is not None

    doc_db = db_session.query(Document).filter(Document.id == review_db.document_id).first()
    assert doc_db is not None
    assert doc_db.organization_id == test_org.id
    assert doc_db.processing_status == "Ready"

    ver_db = db_session.query(DocumentVersion).filter(DocumentVersion.id == review_db.version_id).first()
    assert ver_db is not None
    assert "99.9% uptime" in ver_db.extracted_text

    chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_version_id == ver_db.id).all()
    assert len(chunks) > 0


def test_evaluation_creation_with_file_upload(client, db_session, test_org, creator_user):
    """Test full creation and persistence of brand evaluation using uploaded file."""
    token = create_token_for(creator_user)
    headers = {"Authorization": f"Bearer {token}"}

    file_content = b"# Q3 Brand Campaign\n\nGuaranteed deployment in under 15 minutes across multi-cloud regions."
    files = {
        "file": ("campaign_draft.md", io.BytesIO(file_content), "text/markdown"),
    }
    form_data = {
        "title": "Multi-Cloud Campaign File Upload",
        "product": "Northstar Sovereign Cloud",
        "region": "Global",
        "channel": "Website & Landing Page",
        "content_type": "Landing Page Copy",
        "intended_audience": "DevOps Engineers",
        "purpose": "Showcase fast deployment",
    }

    res = client.post("/api/v1/evaluation/new", data=form_data, files=files, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["title"] == "Multi-Cloud Campaign File Upload"
    assert data["document"]["filename"] == "campaign_draft.md"
    assert data["document"]["file_type"] == "text/markdown"
    assert data["version"]["extracted_text"] is not None
    assert "15 minutes" in data["version"]["extracted_text"]


def test_evaluation_json_submission_endpoint(client, db_session, test_org, creator_user):
    """Test POST /api/v1/evaluation JSON endpoint."""
    token = create_token_for(creator_user)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {
        "title": "JSON Evaluation Submission",
        "content": "Northstar Pro cuts onboarding time by 60% with enterprise security.",
        "product": "Northstar Pro",
        "region": "Global",
        "channel": "Advertisement",
        "content_type": "Ad Copy",
        "intended_audience": "HR and IT Directors",
        "purpose": "Announce onboarding benchmark",
        "supporting_evidence": "Benchmark Whitepaper § 4.2",
    }

    res = client.post("/api/v1/evaluation", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["title"] == "JSON Evaluation Submission"
    assert data["intent_card"]["supporting_evidence"] == "Benchmark Whitepaper § 4.2"
    assert data["processing_status"] in ["Completed", "Requires attention", "Ready"]


def test_evaluation_validation_errors(client, creator_user):
    """Test validation errors for empty submissions or missing title."""
    token = create_token_for(creator_user)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Missing title
    res = client.post(
        "/api/v1/evaluation/new",
        data={"title": "", "pasted_text": "Valid body copy"},
        headers=headers
    )
    assert res.status_code in [400, 422]

    # 2. Missing content and file
    res = client.post(
        "/api/v1/evaluation/new",
        data={"title": "Campaign Title", "pasted_text": "   "},
        headers=headers
    )
    assert res.status_code == 400
    assert "Either marketing content / text or an uploaded document" in res.json()["detail"]

    # 3. JSON endpoint with empty content
    res = client.post(
        "/api/v1/evaluation",
        json={"title": "Test Title", "content": "  "},
        headers=headers
    )
    assert res.status_code == 400
    assert "Marketing content / advertisement text must be provided" in res.json()["detail"]


def test_evaluation_listing_and_detail_retrieval(client, db_session, test_org, creator_user):
    """Test listing evaluations and retrieving single evaluation detail."""
    token = create_token_for(creator_user)
    headers = {"Authorization": f"Bearer {token}"}

    # Submit an evaluation
    res = client.post(
        "/api/v1/evaluation",
        json={
            "title": "Retrieve Test Evaluation",
            "content": "Certified ISO 27001 compliant infrastructure.",
            "product": "Northstar Pro",
        },
        headers=headers
    )
    assert res.status_code == 200
    eval_id = res.json()["id"]

    # List evaluations
    res_list = client.get("/api/v1/evaluation", headers=headers)
    assert res_list.status_code == 200
    evals = res_list.json()
    assert len(evals) >= 1
    found = next((e for e in evals if e["id"] == eval_id), None)
    assert found is not None
    assert found["title"] == "Retrieve Test Evaluation"

    # Filter evaluations by product
    res_filtered = client.get("/api/v1/evaluation?product=Northstar%20Pro", headers=headers)
    assert res_filtered.status_code == 200
    assert any(e["id"] == eval_id for e in res_filtered.json())

    # Get single evaluation detail
    res_get = client.get(f"/api/v1/evaluation/{eval_id}", headers=headers)
    assert res_get.status_code == 200
    eval_detail = res_get.json()
    assert eval_detail["id"] == eval_id
    assert eval_detail["title"] == "Retrieve Test Evaluation"
    assert "claims" in eval_detail
    assert "findings" in eval_detail


def test_evaluation_cross_organization_isolation(client, db_session, test_org, creator_user):
    """Verify strict tenant isolation: Org B user cannot access Org A's evaluation."""
    token_a = create_token_for(creator_user)

    # Org A creates an evaluation
    res = client.post(
        "/api/v1/evaluation",
        json={
            "title": "Org A Private Evaluation",
            "content": "Secret strategic roadmap copy.",
        },
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res.status_code == 200
    eval_id_a = res.json()["id"]

    # Create Org B and User B
    org_b = Organization(name="Competitor Org", slug="comp-org-sec", domain="competitor.com")
    db_session.add(org_b)
    db_session.commit()
    db_session.refresh(org_b)

    user_b = User(
        organization_id=org_b.id,
        email="attacker@competitor.com",
        hashed_password=hash_password("Pass1234!"),
        full_name="Attacker B",
        role=UserRole.ADMIN.value
    )
    db_session.add(user_b)
    db_session.commit()
    db_session.refresh(user_b)

    token_b = create_token_for(user_b)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Org B user tries to access Org A's evaluation -> 404
    res_blocked = client.get(f"/api/v1/evaluation/{eval_id_a}", headers=headers_b)
    assert res_blocked.status_code == 404

    # Org B user listing evaluations does not see Org A's evaluation
    res_list_b = client.get("/api/v1/evaluation", headers=headers_b)
    assert res_list_b.status_code == 200
    eval_ids_b = [e["id"] for e in res_list_b.json()]
    assert eval_id_a not in eval_ids_b


def test_citation_gate_and_claim_verification(client, db_session, test_org, creator_user):
    """
    Test CitationGate core rule: 'NO VALID SOURCE = NO FINDING'.
    Conflict with an approved fact creates a Blocker finding.
    Unsupported claim with no approved fact creates NO unauthorized finding.
    """
    token = create_token_for(creator_user)
    headers = {"Authorization": f"Bearer {token}"}

    # Seed an approved fact in Org
    fact = Fact(
        organization_id=test_org.id,
        title="Enterprise SLA Uptime",
        canonical_value="99.9%",
        source_reference="Customer Contract SLA § 3.1",
        status=FactStatus.APPROVED.value,
        product_scope="Northstar Pro",
        region_scope="Global",
        channel_scope="All",
    )
    db_session.add(fact)
    db_session.commit()
    db_session.refresh(fact)

    # Submit content with conflicting uptime claim
    content = "Northstar Pro guarantees 100% uptime with zero downtime under any circumstances."
    res = client.post(
        "/api/v1/evaluation",
        json={
            "title": "SLA Verification Test",
            "content": content,
            "product": "Northstar Pro",
        },
        headers=headers
    )
    assert res.status_code == 200
    data = res.json()

    # Claims must be extracted
    claims = data.get("claims", [])
    assert len(claims) > 0

    # Conflict finding must be generated with source pointing to fact
    findings = data.get("findings", [])
    conflict_findings = [f for f in findings if f["source_type"] == "fact"]
    assert len(conflict_findings) >= 1
    cf = conflict_findings[0]
    assert cf["source_id"] == fact.id
    assert cf["source_reference"] == fact.source_reference
    assert cf["severity"] in ["Blocker", "High"]


def test_human_approval_workflow_and_blocker_enforcement(client, db_session, test_org, creator_user, reviewer_user, admin_user):
    """
    Test Human-in-the-loop review workflow:
    1. Ordinary reviewer cannot approve if an open Blocker exists.
    2. Ordinary reviewer cannot execute override.
    3. Brand Manager/Admin can override open Blocker with valid rationale (>= 10 chars).
    """
    creator_token = create_token_for(creator_user)
    reviewer_token = create_token_for(reviewer_user)
    admin_token = create_token_for(admin_user)

    # Create an evaluation that generates an open Blocker
    rule = Rule(
        organization_id=test_org.id,
        name="Mandatory Security Disclaimer",
        description="Requires security disclaimer on enterprise copy",
        rule_type="REQUIRED_DISCLAIMER",
        severity=SeverityLevel.BLOCKER.value,
        configuration={"required_substring": "ISO 27001 Certified"},
        source_reference="Brand Safety Policy § 1.1",
        active=True,
    )
    db_session.add(rule)
    db_session.commit()

    res = client.post(
        "/api/v1/evaluation",
        json={
            "title": "Blocker Governance Test",
            "content": "Enterprise Cloud Platform for mission critical workloads.",
            "product": "Northstar Pro",
        },
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res.status_code == 200
    eval_id = res.json()["id"]

    # Verify open blocker exists
    eval_detail = client.get(f"/api/v1/evaluation/{eval_id}", headers={"Authorization": f"Bearer {creator_token}"}).json()
    open_blockers = [f for f in eval_detail["findings"] if f["severity"] == "Blocker" and f["status"] == "Open"]
    assert len(open_blockers) >= 1

    # 1. Reviewer tries to approve directly -> 400 Bad Request
    res_appr_fail = client.post(
        f"/api/v1/approvals/review/{eval_id}",
        json={"status": "Approved", "comments": "Looks fine to me", "is_override": False},
        headers={"Authorization": f"Bearer {reviewer_token}"}
    )
    assert res_appr_fail.status_code == 400
    assert "Approval Blocked" in res_appr_fail.json()["detail"]

    # 2. Reviewer tries to override -> 403 Forbidden
    res_appr_forbidden = client.post(
        f"/api/v1/approvals/review/{eval_id}",
        json={
            "status": "Approved",
            "comments": "Overriding blocker",
            "is_override": True,
            "override_reason": "I think it is fine to override"
        },
        headers={"Authorization": f"Bearer {reviewer_token}"}
    )
    assert res_appr_forbidden.status_code == 403
    assert "Only Brand Managers or Administrators" in res_appr_forbidden.json()["detail"]

    # 3. Admin overrides with valid rationale -> 200 OK
    res_appr_success = client.post(
        f"/api/v1/approvals/review/{eval_id}",
        json={
            "status": "Approved",
            "comments": "Approved under executive exception",
            "is_override": True,
            "override_reason": "Executive approved exception for Q3 campaign launch deadline."
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_appr_success.status_code == 200
    appr_data = res_appr_success.json()
    assert appr_data["status"] == "Approved"
    assert appr_data["is_override"] is True

    # Check that evaluation status changed to Approved
    eval_after = client.get(f"/api/v1/evaluation/{eval_id}", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert eval_after["status"] == "Approved"


def test_remediation_accept_fix_and_dismissal(client, db_session, test_org, creator_user, reviewer_user):
    """Test remediating findings by accepting suggested fix (creates v2) and dismissing findings with rationale."""
    creator_token = create_token_for(creator_user)
    reviewer_token = create_token_for(reviewer_user)

    # Seed a rule with suggested replacement
    rule = Rule(
        organization_id=test_org.id,
        name="Avoid Unverified Claims",
        description="Forbidden phrase test",
        rule_type="FORBIDDEN_PHRASE",
        severity=SeverityLevel.HIGH.value,
        configuration={"forbidden_phrases": ["guaranteed 100%"], "suggested_fix": "industry-leading"},
        source_reference="Marketing Guidelines § 4",
        active=True,
    )
    db_session.add(rule)
    db_session.commit()

    res = client.post(
        "/api/v1/evaluation",
        json={
            "title": "Remediation Workflow Test",
            "content": "We offer guaranteed 100% performance on all servers.",
            "product": "Northstar Pro",
        },
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res.status_code == 200
    eval_id = res.json()["id"]

    eval_detail = client.get(f"/api/v1/evaluation/{eval_id}", headers={"Authorization": f"Bearer {creator_token}"}).json()
    assert len(eval_detail["findings"]) >= 1
    target_finding = eval_detail["findings"][0]

    # 1. Accept Fix -> creates DocumentVersion 2 and marks finding Fixed
    res_fix = client.post(
        f"/api/v1/reviews/{eval_id}/accept-fix",
        json={
            "finding_id": target_finding["id"],
            "replacement_text": "industry-leading"
        },
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res_fix.status_code == 200
    fixed_eval = res_fix.json()
    assert fixed_eval["version"]["version_number"] == 2
    assert "industry-leading" in fixed_eval["version"]["extracted_text"]

    # 2. Test Dismiss Finding with rationale
    # Create another evaluation to dismiss
    res2 = client.post(
        "/api/v1/evaluation",
        json={
            "title": "Dismiss Finding Test",
            "content": "Another draft with guaranteed 100% phrasing.",
            "product": "Northstar Pro",
        },
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    eval2_id = res2.json()["id"]
    finding2 = res2.json()["findings"][0]

    # Dismiss without reason -> 422
    res_dismiss_fail = client.post(
        f"/api/v1/reviews/{eval2_id}/dismiss-finding",
        json={"finding_id": finding2["id"], "dismissal_reason": "bad"},
        headers={"Authorization": f"Bearer {reviewer_token}"}
    )
    assert res_dismiss_fail.status_code == 422

    # Dismiss with valid business reason (>= 5 chars) -> 200
    res_dismiss_ok = client.post(
        f"/api/v1/reviews/{eval2_id}/dismiss-finding",
        json={
            "finding_id": finding2["id"],
            "dismissal_reason": "Contextually permitted under internal executive exception."
        },
        headers={"Authorization": f"Bearer {reviewer_token}"}
    )
    assert res_dismiss_ok.status_code == 200
    dismissed_eval = res_dismiss_ok.json()
    df = next(f for f in dismissed_eval["findings"] if f["id"] == finding2["id"])
    assert df["status"] == "Dismissed"


def test_evaluation_rename_and_patch(client, db_session, creator_user):
    """Test PATCH /api/v1/evaluation/{id} to rename evaluation and update intent scopes."""
    token = create_token_for(creator_user)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/api/v1/evaluation",
        json={
            "title": "Initial Evaluation Title",
            "content": "Northstar Pro offers enterprise cloud solutions with 99.9% uptime.",
            "product": "Northstar Pro",
            "region": "India",
            "channel": "Advertisement",
            "purpose": "Original campaign goal",
        },
        headers=headers
    )
    assert create_res.status_code == 200
    eval_id = create_res.json()["id"]

    patch_res = client.patch(
        f"/api/v1/evaluation/{eval_id}",
        json={
            "title": "Renamed Enterprise Cloud Campaign 2026",
            "purpose": "Updated executive purpose",
            "channel": "Social Media",
        },
        headers=headers
    )
    assert patch_res.status_code == 200, patch_res.text
    patched = patch_res.json()
    assert patched["title"] == "Renamed Enterprise Cloud Campaign 2026"
    assert patched["document"]["title"] == "Renamed Enterprise Cloud Campaign 2026"
    assert patched["intent_card"]["purpose"] == "Updated executive purpose"
    assert patched["channel"] == "Social Media"

    # Verify DB state
    db_review = db_session.query(Review).filter(Review.id == eval_id).first()
    assert db_review.title == "Renamed Enterprise Cloud Campaign 2026"
    assert db_review.document.title == "Renamed Enterprise Cloud Campaign 2026"


def test_evaluation_delete_and_cascade(client, db_session, creator_user):
    """Test DELETE /api/v1/evaluation/{id} cascades deletion of review, claims, findings, and document."""
    token = create_token_for(creator_user)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/api/v1/evaluation",
        json={
            "title": "Evaluation To Be Deleted",
            "content": "Guaranteed deployment in 10 minutes with Northstar Sovereign Cloud.",
            "product": "Northstar Sovereign Cloud",
        },
        headers=headers
    )
    assert create_res.status_code == 200
    eval_id = create_res.json()["id"]
    doc_id = create_res.json()["document_id"]

    delete_res = client.delete(f"/api/v1/evaluation/{eval_id}", headers=headers)
    assert delete_res.status_code == 200
    data = delete_res.json()
    assert data["status"] == "success"
    assert data["id"] == eval_id

    # Verify review and document are gone from DB
    assert db_session.query(Review).filter(Review.id == eval_id).first() is None
    assert db_session.query(Document).filter(Document.id == doc_id).first() is None
    assert db_session.query(Claim).filter(Claim.review_id == eval_id).count() == 0
    assert db_session.query(Finding).filter(Finding.review_id == eval_id).count() == 0


def test_evaluation_re_evaluate_endpoint(client, creator_user):
    """Test POST /api/v1/evaluation/{id}/re-evaluate re-executes brand governance scan."""
    token = create_token_for(creator_user)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/api/v1/evaluation",
        json={
            "title": "Re-evaluation Target Campaign",
            "content": "Northstar Pro delivers verified 99.9% availability across all nodes.",
            "product": "Northstar Pro",
        },
        headers=headers
    )
    assert create_res.status_code == 200
    eval_id = create_res.json()["id"]

    re_eval_res = client.post(f"/api/v1/evaluation/{eval_id}/re-evaluate", headers=headers)
    assert re_eval_res.status_code == 200, re_eval_res.text
    re_eval_data = re_eval_res.json()
    assert re_eval_data["id"] == eval_id
    assert re_eval_data["processing_status"] in ["Completed", "Requires attention"]


def test_review_patch_and_delete_endpoints(client, db_session, creator_user):
    """Test parity for PATCH and DELETE /api/v1/reviews/{id}."""
    token = create_token_for(creator_user)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/api/v1/reviews/new",
        data={
            "title": "Review Parity Test",
            "product": "Northstar Pro",
            "pasted_text": "Sample text for review parity testing.",
        },
        headers=headers
    )
    assert create_res.status_code == 200
    review_id = create_res.json()["id"]

    # Patch
    patch_res = client.patch(
        f"/api/v1/reviews/{review_id}",
        json={"title": "Renamed Via Reviews Endpoint"},
        headers=headers
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Renamed Via Reviews Endpoint"

    # Delete
    del_res = client.delete(f"/api/v1/reviews/{review_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"
    assert db_session.query(Review).filter(Review.id == review_id).first() is None

