def test_rbac_fact_creation(client, creator_token, admin_token, test_org):
    fact_payload = {
        "title": "SOC-2 Type II Certified",
        "canonical_value": "All services audited under AICPA SOC-2 Type II standards.",
        "source_reference": "Annual Audit Report #2026-01",
        "product_scope": "All Products",
        "region_scope": "Global",
        "channel_scope": "All Channels",
    }

    # 1. Creator role should be denied (403 Forbidden)
    res_creator = client.post(
        "/api/v1/facts",
        json=fact_payload,
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res_creator.status_code == 403
    assert "lacks permission" in res_creator.json()["detail"]

    # 2. Admin role should succeed (200 OK)
    res_admin = client.post(
        "/api/v1/facts",
        json=fact_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200
    fact_data = res_admin.json()
    assert fact_data["title"] == fact_payload["title"]
    assert fact_data["canonical_value"] == fact_payload["canonical_value"]


def test_no_valid_source_no_finding_rule(client, reviewer_token, test_org, db_session):
    from app.models.document import Document
    from app.models.review import Review

    doc = Document(
        organization_id=test_org.id,
        title="Test Document",
        filename="test.md",
        file_type="text/markdown",
        file_path="test.md",
        file_size=100,
    )
    db_session.add(doc)
    db_session.flush()

    review = Review(
        organization_id=test_org.id,
        document_id=doc.id,
        status="Needs Review",
    )
    db_session.add(review)
    db_session.commit()

    # Attempt to create a finding WITHOUT a source reference
    invalid_finding = {
        "review_id": review.id,
        "severity": "Critical",
        "message": "Unsubstantiated marketing claim detected",
        "suggestion": "Delete statement",
        "source_reference": ""  # BLANK SOURCE -> MUST BE REJECTED
    }

    res_invalid = client.post(
        "/api/v1/findings",
        json=invalid_finding,
        headers={"Authorization": f"Bearer {reviewer_token}"}
    )
    # Must enforce: NO VALID SOURCE = NO FINDING
    assert res_invalid.status_code == 422
    assert "NO VALID SOURCE = NO FINDING" in res_invalid.json()["detail"]

    # Now attempt with valid source reference
    valid_finding = {
        "review_id": review.id,
        "severity": "Critical",
        "message": "Unsubstantiated marketing claim detected",
        "suggestion": "Delete statement",
        "source_reference": "Brand Guidelines v2.0 §4.1"
    }
    res_valid = client.post(
        "/api/v1/findings",
        json=valid_finding,
        headers={"Authorization": f"Bearer {reviewer_token}"}
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["source_reference"] == "Brand Guidelines v2.0 §4.1"


def test_dashboard_kpis(client, admin_token):
    res = client.get(
        "/api/v1/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "metrics" in data
    assert "open_reviews" in data["metrics"]
    assert "blocked_content" in data["metrics"]
    assert "active_facts" in data["metrics"]
    assert "risk_overview" in data
    assert "recent_reviews" in data
    assert "recent_activity" in data
