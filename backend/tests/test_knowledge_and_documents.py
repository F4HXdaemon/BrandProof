import io


def test_guideline_crud(client, admin_token):
    # 1. Create Guideline
    res = client.post(
        "/api/v1/guidelines",
        json={
            "title": "Mandatory Disclaimers for Beta Features",
            "description": "Beta features must include standard experimental disclaimer.",
            "category": "Product Guidelines",
            "severity": "Medium",
            "source_reference": "Legal Guidelines 2026 §1.2",
            "active": True
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    guideline_id = res.json()["id"]

    # 2. List Guidelines
    res_list = client.get(
        "/api/v1/guidelines",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_list.status_code == 200
    assert any(g["id"] == guideline_id for g in res_list.json())

    # 3. Update Guideline
    res_update = client.put(
        f"/api/v1/guidelines/{guideline_id}",
        json={"title": "Updated Beta Feature Disclaimer"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_update.status_code == 200
    assert res_update.json()["title"] == "Updated Beta Feature Disclaimer"


def test_terminology_crud(client, admin_token):
    res = client.post(
        "/api/v1/terms",
        json={
            "approved_term": "BrandProof Engine",
            "disallowed_variants": ["BP Engine", "Brand Proof Tool"],
            "replacement": "BrandProof Engine",
            "notes": "Official brand tool naming",
            "active": True
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    term_id = res.json()["id"]

    res_get = client.get(
        f"/api/v1/terms/{term_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_get.status_code == 200
    assert res_get.json()["approved_term"] == "BrandProof Engine"


def test_document_upload_and_review_flow(client, creator_token, reviewer_token):
    # Upload document as Creator
    file_content = b"# Launch Announcement\n\nGuarantees 99.999% SLA uptime."
    res_upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("launch.md", io.BytesIO(file_content), "text/markdown")},
        data={"title": "Launch Memo", "product": "Core Cloud"},
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res_upload.status_code == 200
    doc_id = res_upload.json()["id"]
    assert res_upload.json()["title"] == "Launch Memo"

    # Initiate Review
    res_review = client.post(
        "/api/v1/reviews",
        json={"document_id": doc_id, "summary": "Pre-launch compliance scan"},
        headers={"Authorization": f"Bearer {reviewer_token}"}
    )
    assert res_review.status_code == 200
    review_id = res_review.json()["id"]
    assert res_review.json()["status"] == "Needs Review"

    # Human Approval Decision (People Approve)
    res_approval = client.post(
        f"/api/v1/approvals/review/{review_id}",
        json={"status": "Approved", "comments": "Compliance check passed successfully."},
        headers={"Authorization": f"Bearer {reviewer_token}"}
    )
    assert res_approval.status_code == 200
    assert res_approval.json()["status"] == "Approved"

    # Check that Document is now Approved
    res_doc = client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {reviewer_token}"}
    )
    assert res_doc.status_code == 200
    assert res_doc.json()["status"] == "Approved"
