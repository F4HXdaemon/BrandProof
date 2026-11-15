import pytest
import io
from app.models.knowledge import Fact, Rule, Term, Guideline, SeverityLevel, FactStatus
from app.models.review import Review, Finding, FindingStatus, ApprovalDecision
from app.services.rule_engine import (
    DeterministicRuleEngine,
    TerminologyChecker,
    RequiredDisclaimerChecker,
    ForbiddenPhraseChecker,
    NumericClaimChecker,
    ExpiryChecker,
    FindingCandidate,
)
from app.services.citation_gate import CitationGate
from app.services.risk_scoring import calculate_risk_score
from app.services.llm import get_llm_provider, compute_word_diff, compute_diff_stats


def test_rule_checkers_unit():
    # 1. TerminologyChecker
    term_checker = TerminologyChecker()
    mock_term = type("TermMock", (), {
        "id": "term-1",
        "term": "Northstar Pro",
        "approved_term": "Northstar Pro",
        "disallowed_variants": ["Northstar Premium", "NS Pro"],
        "case_sensitive": True,
        "source_reference": "Brand Terminology v1",
    })()

    text = "Deploy your database on Northstar Premium today."
    results = term_checker.check(text, [], {}, {"terms": [mock_term]})
    assert len(results) == 1
    assert results[0].finding_type == "terminology"
    assert results[0].quoted_text == "Northstar Premium"
    assert results[0].suggested_replacement == "Northstar Pro"

    # 2. ForbiddenPhraseChecker
    forbidden_checker = ForbiddenPhraseChecker()
    mock_rule = type("RuleMock", (), {
        "id": "rule-1",
        "name": "Absolute Guarantee Prohibition",
        "description": "Never use unqualified guarantee phrases.",
        "rule_type": "FORBIDDEN_PHRASE",
        "severity": SeverityLevel.BLOCKER,
        "config": {"phrases": ["guarantees", "100% secure"]},
        "source_reference": "FTC Compliance Guide §3",
    })()

    text2 = "Northstar guarantees immediate productivity improvements."
    results2 = forbidden_checker.check(text2, [], {}, {"rules": [mock_rule]})
    assert len(results2) == 1
    assert results2[0].finding_type == "forbidden_phrase"
    assert results2[0].severity == "Blocker"
    assert results2[0].quoted_text == "guarantees"

    # 3. NumericClaimChecker
    numeric_checker = NumericClaimChecker()
    mock_fact = type("FactMock", (), {
        "id": "fact-1",
        "title": "Northstar Uptime SLA Availability",
        "canonical_value": "99.95%",
        "source_reference": "Master SLA Contract 2026",
    })()

    text3 = "Enjoy our enterprise SLA uptime of 99.999% globally."
    results3 = numeric_checker.check(text3, [], {}, {"facts": [mock_fact]})
    assert len(results3) == 1
    assert results3[0].finding_type == "numeric_conflict"
    assert results3[0].suggested_replacement == "99.95%"


def test_citation_gate_quarantine(db_session, test_org):
    # Rule: NO VALID SOURCE = NO FINDING
    gate = CitationGate(db_session, test_org.id)

    # 1. Candidate with empty source reference -> Quarantined
    c1 = FindingCandidate(
        finding_type="forbidden_phrase",
        severity="Blocker",
        title="Unsubstantiated Claim",
        message="Invalid claim",
        source_type="rule",
        source_id="non-existent",
        source_reference="",  # BLANK
    )
    is_valid, reason = gate.validate_candidate(c1)
    assert not is_valid
    assert "NO VALID SOURCE = NO FINDING" in reason

    # 2. Candidate with non-existent source_id -> Quarantined
    c2 = FindingCandidate(
        finding_type="forbidden_phrase",
        severity="Blocker",
        title="Unsubstantiated Claim",
        message="Invalid claim",
        source_type="rule",
        source_id="non-existent-rule-id",
        source_reference="Some random policy",
    )
    is_valid, reason = gate.validate_candidate(c2)
    assert not is_valid
    assert "does not exist" in reason

    # 3. Candidate with existing rule -> Valid
    rule = Rule(
        organization_id=test_org.id,
        name="Valid Rule",
        description="A real rule",
        rule_type="FORBIDDEN_PHRASE",
        severity=SeverityLevel.BLOCKER.value,
        source_reference="Legal Memo v1",
    )
    db_session.add(rule)
    db_session.commit()

    c3 = FindingCandidate(
        finding_type="forbidden_phrase",
        severity="Blocker",
        title="Real Finding",
        message="Violation found",
        source_type="rule",
        source_id=rule.id,
        source_reference=rule.source_reference,
    )
    is_valid, reason = gate.validate_candidate(c3)
    assert is_valid
    assert reason is None


def test_risk_scoring_engine():
    # Weights: Info: 1, Warning: 3, High: 7, Blocker: 15
    mock_findings = [
        type("F", (), {"severity": "Info", "status": "Open"})(),
        type("F", (), {"severity": "Warning", "status": "Open"})(),
        type("F", (), {"severity": "High", "status": "Open"})(),
    ]
    # Total = 1 + 3 + 7 = 11 -> Medium
    res = calculate_risk_score(mock_findings)
    assert res["risk_score"] == 11.0
    assert res["risk_level"] == "Medium"
    assert not res["has_blockers"]

    # Add Blocker -> Total = 11 + 15 = 26 -> High (has_blockers)
    mock_findings.append(type("F", (), {"severity": "Blocker", "status": "Open"})())
    res2 = calculate_risk_score(mock_findings)
    assert res2["risk_score"] == 26.0
    assert res2["risk_level"] == "High"
    assert res2["has_blockers"]


def test_diff_engine():
    old_str = "Northstar Premium offers 99.999% SLA."
    new_str = "Northstar Pro offers 99.95% SLA."
    diff_tokens = compute_word_diff(old_str, new_str)
    stats = compute_diff_stats(old_str, new_str)

    assert any(t["type"] == "removed" and "Premium" in t["value"] for t in diff_tokens)
    assert any(t["type"] == "added" and "Pro" in t["value"] for t in diff_tokens)
    assert stats["words_added"] >= 2
    assert stats["words_removed"] >= 2


def test_blocker_approval_and_override_flow(client, reviewer_token, admin_token, test_org, db_session):
    from app.models.document import Document
    # Create document, review, and a Blocker finding
    doc = Document(
        organization_id=test_org.id,
        title="Blocker Test Memo",
        filename="test.md",
        file_type="text/markdown",
        file_path="test.md",
        file_size=100,
        status="Needs Review",
    )
    db_session.add(doc)
    db_session.flush()

    review = Review(
        organization_id=test_org.id,
        document_id=doc.id,
        title="Blocker Test Review",
        status="Needs Review",
        processing_status="Ready",
    )
    db_session.add(review)
    db_session.flush()

    rule = Rule(
        organization_id=test_org.id,
        name="Blocker Rule",
        description="Critical compliance rule",
        severity=SeverityLevel.BLOCKER.value,
        source_reference="Policy §1",
    )
    db_session.add(rule)
    db_session.flush()

    finding = Finding(
        organization_id=test_org.id,
        review_id=review.id,
        severity="Blocker",
        status="Open",
        title="Open Blocker",
        message="Active Blocker violation",
        source_reference="Policy §1",
        source_id=rule.id,
        source_type="rule",
    )
    db_session.add(finding)
    db_session.commit()

    # 1. Reviewer attempts normal approval without override -> MUST FAIL (HTTP 400)
    res_fail = client.post(
        f"/api/v1/approvals/review/{review.id}",
        json={"status": "Approved", "comments": "Standard approval"},
        headers={"Authorization": f"Bearer {reviewer_token}"}
    )
    assert res_fail.status_code == 400
    assert "Approval Blocked" in res_fail.json()["detail"]

    # 2. Reviewer attempts override -> MUST FAIL (HTTP 403, requires Brand Manager/Admin)
    res_forbidden = client.post(
        f"/api/v1/approvals/review/{review.id}",
        json={
            "status": "Approved",
            "is_override": True,
            "override_reason": "Executive approved exception for launch",
            "comments": "Overriding blocker"
        },
        headers={"Authorization": f"Bearer {reviewer_token}"}
    )
    assert res_forbidden.status_code == 403

    # 3. Admin performs override with valid justification -> SUCCEEDS (HTTP 200)
    res_override = client.post(
        f"/api/v1/approvals/review/{review.id}",
        json={
            "status": "Approved",
            "is_override": True,
            "override_reason": "Executive signed waiver for controlled internal beta release",
            "comments": "Authorized waiver applied"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_override.status_code == 200
    approval_data = res_override.json()
    assert approval_data["status"] == "Approved"
    assert approval_data["is_override"] is True
    assert "Executive signed waiver" in approval_data["override_reason"]


def test_insights_api(client, reviewer_token):
    res = client.get("/api/v1/insights", headers={"Authorization": f"Bearer {reviewer_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "metrics" in data
    assert "severity_breakdown" in data
    assert "status_breakdown" in data
    assert "top_violated_rules" in data
    assert "channel_distribution" in data


def test_evaluation_api(client, reviewer_token):
    # Run evaluation
    res = client.get("/api/v1/evaluation/run", headers={"Authorization": f"Bearer {reviewer_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "metrics" in data
    assert "f1_score" in data["metrics"]
    assert "precision" in data["metrics"]
    assert "recall" in data["metrics"]
    assert len(data["cases"]) > 0

    # Export CSV
    res_export = client.get("/api/v1/evaluation/export", headers={"Authorization": f"Bearer {reviewer_token}"})
    assert res_export.status_code == 200
    assert "text/csv" in res_export.headers.get("content-type", "")
    assert "Case ID" in res_export.text
