import io
from datetime import datetime, timedelta, timezone
import pytest
from app.models.knowledge import FactStatus, SeverityLevel, RuleType


def test_fact_dynamic_expiration(client, admin_token):
    now = datetime.now(timezone.utc)
    past_date = (now - timedelta(days=10)).isoformat()
    future_date = (now + timedelta(days=60)).isoformat()

    # 1. Create an active fact with future expiry
    res_active = client.post(
        "/api/v1/facts",
        json={
            "title": "Northstar Enterprise SLA",
            "canonical_value": "99.99% uptime guarantee",
            "source_reference": "Master Services Agreement §4.1",
            "product_scope": "Northstar Cloud",
            "region_scope": "Global",
            "channel_scope": "All",
            "expires_at": future_date,
            "status": "Approved"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_active.status_code == 200
    active_data = res_active.json()
    assert active_data["is_expired"] is False
    assert active_data["effective_status"] == "Approved"
    assert active_data["days_until_expiry"] is not None
    assert active_data["days_until_expiry"] >= 58

    # 2. Create an expired fact (expires_at in past)
    res_expired = client.post(
        "/api/v1/facts",
        json={
            "title": "Old SOC-2 Certification",
            "canonical_value": "SOC-2 Type I certified",
            "source_reference": "2024 Audit Report #SOC-99",
            "product_scope": "All",
            "region_scope": "Global",
            "channel_scope": "All",
            "expires_at": past_date,
            "status": "Approved"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_expired.status_code == 200
    expired_data = res_expired.json()
    # Dynamic expiration must automatically detect that it is expired!
    assert expired_data["is_expired"] is True
    assert expired_data["effective_status"] == "Expired"
    assert expired_data["days_until_expiry"] is not None
    assert expired_data["days_until_expiry"] < 0

    # 3. Filter facts by status=Expired
    res_list_expired = client.get(
        "/api/v1/facts?status=Expired",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_list_expired.status_code == 200
    expired_ids = [f["id"] for f in res_list_expired.json()]
    assert expired_data["id"] in expired_ids
    assert active_data["id"] not in expired_ids

    # 4. Filter facts by status=Approved
    res_list_approved = client.get(
        "/api/v1/facts?status=Approved",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_list_approved.status_code == 200
    approved_ids = [f["id"] for f in res_list_approved.json()]
    assert active_data["id"] in approved_ids
    assert expired_data["id"] not in approved_ids

    # 5. Archive fact
    res_archive = client.put(
        f"/api/v1/facts/{active_data['id']}/archive",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_archive.status_code == 200
    assert res_archive.json()["status"] == "Archived"
    assert res_archive.json()["effective_status"] == "Archived"


def test_applicable_knowledge_scoping_engine(client, admin_token):
    now = datetime.now(timezone.utc)
    future_date = (now + timedelta(days=90)).isoformat()
    past_date = (now - timedelta(days=20)).isoformat()

    # Create Facts with different scopes
    client.post(
        "/api/v1/facts",
        json={
            "title": "Global Fact",
            "canonical_value": "Global Universal Fact",
            "source_reference": "HQ Policy 2026",
            "product_scope": "All",
            "region_scope": "Global",
            "channel_scope": "All",
            "expires_at": future_date,
            "status": "Approved"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    client.post(
        "/api/v1/facts",
        json={
            "title": "US Specific Fact",
            "canonical_value": "US Only Fact",
            "source_reference": "US Legal Addendum",
            "product_scope": "Northstar Pro",
            "region_scope": "North America",
            "channel_scope": "Web",
            "expires_at": future_date,
            "status": "Approved"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    client.post(
        "/api/v1/facts",
        json={
            "title": "Expired EU Fact",
            "canonical_value": "Old EU Spec",
            "source_reference": "EU Directives 2023",
            "product_scope": "Northstar Pro",
            "region_scope": "Europe",
            "channel_scope": "Web",
            "expires_at": past_date,
            "status": "Approved"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # Query applicable knowledge for US / Northstar Pro / Web
    res_applicable = client.get(
        "/api/v1/knowledge/applicable?product=Northstar Pro&region=North America&channel=Web",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_applicable.status_code == 200
    data = res_applicable.json()

    fact_titles = [f["title"] for f in data["facts"]]
    assert "Global Fact" in fact_titles
    assert "US Specific Fact" in fact_titles

    # Query applicable knowledge for APAC / Northstar Pro / Web
    res_apac = client.get(
        "/api/v1/knowledge/applicable?product=Northstar Pro&region=APAC&channel=Web",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_apac.status_code == 200
    apac_facts = [f["title"] for f in res_apac.json()["facts"]]
    assert "Global Fact" in apac_facts
    assert "US Specific Fact" not in apac_facts  # US fact does NOT match APAC


def test_terminology_disallowed_variants(client, admin_token):
    res = client.post(
        "/api/v1/terms",
        json={
            "term": "Northstar Ultra",
            "disallowed_variants": ["Northstar Extreme", "Northstar Max"],
            "replacement": "Northstar Ultra",
            "notes": "Premium product naming convention.",
            "product_scope": "Northstar Ultra",
            "region_scope": "Global",
            "channel_scope": "All",
            "status": "Approved"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    term_data = res.json()
    assert term_data["term"] == "Northstar Ultra"
    assert "Northstar Extreme" in term_data["disallowed_variants"]
    assert "Northstar Max" in term_data["disallowed_variants"]
    assert term_data["replacement"] == "Northstar Ultra"

    # Archive Term
    res_archive = client.put(
        f"/api/v1/terms/{term_data['id']}/archive",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_archive.status_code == 200
    assert res_archive.json()["status"] == "Archived"


def test_rules_configuration(client, admin_token):
    # Create a REQUIRED_DISCLAIMER rule
    res = client.post(
        "/api/v1/rules",
        json={
            "name": "Beta Feature Disclaimer Rule",
            "description": "Enforce experimental disclosure on beta features",
            "rule_type": "REQUIRED_DISCLAIMER",
            "severity": "Blocker",
            "config": {
                "trigger_keywords": ["beta", "preview"],
                "required_text": "This feature is currently in preview and not covered by standard SLA."
            },
            "product_scope": "All",
            "region_scope": "Global",
            "channel_scope": "All",
            "source_reference": "Compliance Standard §9"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    rule_data = res.json()
    assert rule_data["rule_type"] == "REQUIRED_DISCLAIMER"
    assert rule_data["severity"] == "Blocker"
    assert rule_data["config"]["trigger_keywords"] == ["beta", "preview"]


def test_csv_import_facts_and_terms(client, admin_token):
    # 1. Facts CSV import
    csv_content = (
        "title,canonical_value,source_reference,description,product_scope,region_scope,channel_scope,expires_at\n"
        "CSV Fact 1,100ms Latency,SLA Benchmarks,Global latency guarantee,All,Global,All,2028-12-31\n"
        "CSV Fact 2,24/7 Phone Support,Support Tiers,Enterprise support,Enterprise,Global,All,2028-12-31\n"
    )
    files = {"file": ("test_facts.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res_import = client.post(
        "/api/v1/facts/import-csv",
        files=files,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_import.status_code == 200
    import_data = res_import.json()
    assert import_data["imported_count"] == 2
    assert import_data["failed_count"] == 0

    # 2. Terms CSV import
    term_csv_content = (
        "term,disallowed_variants,replacement,notes,product_scope,region_scope,channel_scope\n"
        "BrandProof,Brand Proof|Brand-Proof,BrandProof,One word CamelCase,All,Global,All\n"
    )
    files_term = {"file": ("test_terms.csv", io.BytesIO(term_csv_content.encode("utf-8")), "text/csv")}
    res_term_import = client.post(
        "/api/v1/terms/import-csv",
        files=files_term,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_term_import.status_code == 200
    term_import_data = res_term_import.json()
    assert term_import_data["imported_count"] == 1


def test_rbac_creator_cannot_mutate_facts(client, creator_token):
    # Creator role cannot create facts (Must be Reviewer, Brand Manager, or Admin)
    res = client.post(
        "/api/v1/facts",
        json={
            "title": "Unauthorized Fact",
            "canonical_value": "Should Fail",
            "source_reference": "None",
        },
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res.status_code == 403
