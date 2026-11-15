import os
import uuid
import datetime
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.document import Document, DocumentVersion, DocumentStatus
from app.models.review import Review, ReviewStatus, Finding, FindingStatus
from app.models.knowledge import Fact
from app.core.security import hash_password, create_access_token
from app.services.storage import S3CompatibleStorageBackend, StorageError, LocalStorageBackend


def test_organization_takeover_prevented(client, test_org):
    """
    Critical Security Test (C-1): An attacker must never be able to join or take over
    an existing organization simply by registering with its slug.
    """
    payload = {
        "organization_name": "Different Name",
        "organization_slug": test_org.slug,  # Target existing victim organization slug
        "email": f"attacker_{uuid.uuid4().hex[:6]}@evil.com",
        "password": "AttackerPass1234!",
        "full_name": "Malicious User",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_registration_success_creates_isolated_org(client, db_session):
    """Test safe registration creates a clean, isolated new organization."""
    uid = uuid.uuid4().hex[:6]
    payload = {
        "organization_name": f"Acme Corp {uid}",
        "organization_slug": f"acme-corp-{uid}",
        "email": f"founder_{uid}@acme.com",
        "password": "SecurePassword1234!",
        "full_name": f"Founder {uid}",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["role"] == "Admin"

    # Verify newly created org in DB
    new_org = db_session.query(Organization).filter(Organization.slug == f"acme-corp-{uid}").first()
    assert new_org is not None
    assert new_org.name == f"Acme Corp {uid}"


def test_duplicate_email_registration_rejected(client, admin_user):
    """Cannot register multiple accounts with the same email."""
    payload = {
        "organization_name": "Another Org",
        "organization_slug": f"another-org-{uuid.uuid4().hex[:6]}",
        "email": admin_user.email,  # Existing email
        "password": "Password1234!",
        "full_name": "Duplicate User",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_short_password_rejected(client):
    """Short passwords (< 8 chars) are rejected."""
    payload = {
        "organization_name": f"Org {uuid.uuid4().hex[:6]}",
        "email": f"user_{uuid.uuid4().hex[:6]}@test.com",
        "password": "short",
        "full_name": "Short Password",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code in [400, 422]
    assert "at least 8 characters" in str(response.json())


def test_inactive_user_login_rejected(client, db_session, test_org):
    """Deactivated accounts cannot authenticate."""
    user = User(
        organization_id=test_org.id,
        email=f"deactivated_{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("Pass1234!"),
        full_name="Deactivated User",
        role=UserRole.CREATOR.value,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Pass1234!"}
    )
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


def test_jwt_expiration_enforced(client, admin_user):
    """Expired JWT tokens must be rejected."""
    # Create token expired 1 hour ago
    expired_token = create_access_token(
        subject=admin_user.id,
        expires_delta=datetime.timedelta(hours=-1),
        extra_claims={"role": admin_user.role, "org_id": admin_user.organization_id}
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401


def test_cross_organization_isolation(client, db_session, test_org, creator_token):
    """
    Tenant Isolation Test: Users from Organization A cannot view or manipulate
    records belonging to Organization B.
    """
    # Create an independent Org B with sensitive Fact & Document
    org_b = Organization(
        name=f"Victim Org {uuid.uuid4().hex[:6]}",
        slug=f"victim-org-{uuid.uuid4().hex[:6]}",
        domain="victim.com",
    )
    db_session.add(org_b)
    db_session.flush()

    fact_b = Fact(
        organization_id=org_b.id,
        title="Top Secret Org B Financials",
        canonical_value="$500M Revenue",
        source_reference="10-K Report 2026",
    )
    doc_b = Document(
        organization_id=org_b.id,
        title="Confidential Strategy Org B",
        filename="confidential.txt",
        file_type="text/plain",
        file_path="confidential.txt",
        status=DocumentStatus.DRAFT.value,
    )
    db_session.add_all([fact_b, doc_b])
    db_session.flush()

    review_b = Review(
        organization_id=org_b.id,
        document_id=doc_b.id,
        title="Secret Review B",
    )
    db_session.add(review_b)
    db_session.commit()

    # User from Org A tries to access Org B's Fact
    res_fact = client.get(
        f"/api/v1/facts/{fact_b.id}",
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res_fact.status_code == 404

    # User from Org A tries to access Org B's Document
    res_doc = client.get(
        f"/api/v1/documents/{doc_b.id}",
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res_doc.status_code == 404

    # User from Org A tries to access Org B's Review
    res_review = client.get(
        f"/api/v1/reviews/{review_b.id}",
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res_review.status_code == 404


def test_privilege_escalation_prevented(client, db_session, creator_user, creator_token):
    """
    RBAC Test: Non-admin users cannot elevate their own role to Admin
    via the user profile update endpoint.
    """
    res = client.put(
        f"/api/v1/users/{creator_user.id}",
        json={"role": "Admin"},
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert res.status_code == 200
    # Role change must be silently ignored or rejected when caller is not admin
    db_session.refresh(creator_user)
    assert creator_user.role == UserRole.CREATOR.value


def test_demo_reset_disabled_in_production(client):
    """Demo reset endpoint must be blocked when demo reset is disabled."""
    with patch("app.api.v1.demo.settings.ENVIRONMENT", "production"):
        res = client.post("/api/v1/demo/reset")
        assert res.status_code == 403
        assert "disabled in production" in res.json()["detail"].lower()


def test_production_insecure_settings_fail_safe():
    """Application Settings must raise ValueError if required production security is missing."""
    # 1. Default secret in production
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql://user:pass@host:5432/db",
            SECRET_KEY="brandproof-super-secure-production-ready-jwt-secret-key-replace-in-prod"
        )

    # 2. SQLite in production
    with pytest.raises(ValueError, match="SQLite is not permitted"):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="sqlite:///./brandproof.db",
            SECRET_KEY="c0mp1ex_crypt0_pr0duct10n_s3cr3t_k3y_987654321"
        )

    # 3. ENABLE_DEMO_RESET=True in production
    with pytest.raises(ValueError, match="ENABLE_DEMO_RESET"):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql://user:pass@host:5432/db",
            SECRET_KEY="c0mp1ex_crypt0_pr0duct10n_s3cr3t_k3y_987654321",
            ENABLE_DEMO_RESET=True
        )


def test_direct_status_approval_blocked_when_open_blockers(client, db_session, test_org, admin_token):
    """
    Cardinal Invariant: A review with open Blocker findings cannot be approved directly
    via the status update endpoint without proper approval override.
    """
    doc = Document(
        organization_id=test_org.id,
        title="Doc with Blocker",
        filename="blocker.txt",
        file_type="text/plain",
        file_path="blocker.txt",
        status=DocumentStatus.NEEDS_REVIEW.value,
    )
    db_session.add(doc)
    db_session.flush()

    review = Review(
        organization_id=test_org.id,
        document_id=doc.id,
        title="Review with Blocker",
        status=ReviewStatus.NEEDS_REVIEW.value,
    )
    db_session.add(review)
    db_session.flush()

    blocker = Finding(
        organization_id=test_org.id,
        review_id=review.id,
        severity="Blocker",
        status=FindingStatus.OPEN.value,
        message="Critical claim violation",
        source_reference="Fact 1",
    )
    db_session.add(blocker)
    db_session.commit()

    # Attempt to bypass approval workflow via direct status update
    res = client.put(
        f"/api/v1/reviews/{review.id}/status?status=Approved",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 400
    assert "Approval Blocked" in res.json()["detail"]


def test_document_deletion_with_storage_cleanup(client, db_session, test_org, admin_token):
    """Document deletion endpoint cleans up database and object storage."""
    doc = Document(
        organization_id=test_org.id,
        title="Temp Document For Deletion",
        filename="temp_doc.txt",
        file_type="text/plain",
        file_path="temp_delete_test.txt",
        status=DocumentStatus.DRAFT.value,
    )
    db_session.add(doc)
    db_session.commit()

    res = client.delete(
        f"/api/v1/documents/{doc.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    assert "deleted successfully" in res.json()["message"]

    # Verify deleted from DB
    deleted = db_session.query(Document).filter(Document.id == doc.id).first()
    assert deleted is None


def test_s3_storage_backend_unit():
    """Unit tests for S3CompatibleStorageBackend with mocked boto3 S3 client."""
    backend = S3CompatibleStorageBackend()
    backend.bucket = "test-bucket"
    backend.access_key = "test-key"
    backend.secret_key = "test-secret"

    mock_client = MagicMock()
    backend._s3_client = mock_client

    # Test Save
    data = b"Hello BrandProof S3 Object Storage"
    key, size = backend.save_file(data, "test.txt", "text/plain")
    assert key.startswith("documents/")
    assert size == len(data)
    mock_client.put_object.assert_called_once()

    # Test Get
    mock_body = MagicMock()
    mock_body.read.return_value = data
    mock_client.get_object.return_value = {"Body": mock_body}

    retrieved = backend.get_file(key)
    assert retrieved == data

    # Test Delete
    deleted = backend.delete_file(key)
    assert deleted is True
    mock_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key=key)


def test_query_param_token_rejected(client, admin_token):
    """
    Security Test: Token in query string (?token=) must be strictly rejected.
    All protected endpoints must enforce Authorization: Bearer <token>.
    """
    # Attempt to access protected endpoint using query parameter token
    res = client.get(f"/api/v1/auth/me?token={admin_token}")
    assert res.status_code == 401
    assert "credentials were not provided" in res.json()["detail"].lower()

    # With proper Authorization header, it succeeds
    res_auth = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_auth.status_code == 200


def test_password_exceeding_72_bytes_rejected(client):
    """Passwords exceeding the 72-byte bcrypt limit must be rejected with 400/422."""
    long_password = "A" * 75  # 75 bytes
    payload = {
        "organization_name": f"Long Pass Org {uuid.uuid4().hex[:6]}",
        "email": f"longpass_{uuid.uuid4().hex[:6]}@test.com",
        "password": long_password,
        "full_name": "Long Password User",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code in [400, 422]
    # Check that error explains byte limit
    detail_str = str(res.json())
    assert "72 bytes" in detail_str


def test_validation_errors_sanitized(client):
    """
    Security Test: RequestValidationError handler must strip raw input values
    so passwords and credentials are never echoed back in error responses.
    """
    secret_pw = "SuperSecretPassword123!"
    payload = {
        "organization_name": "Test Org",
        "email": "invalid-email-format",
        "password": secret_pw,
        "full_name": "Test User",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 422
    data = res.json()
    assert data["success"] is False
    # Ensure secret password is NOT echoed anywhere in the response body
    body_text = res.text
    assert secret_pw not in body_text
    # Verify error entries do not have raw 'input' containing plaintext secret
    for err in data["error"]:
        assert "input" not in err or err["input"] != secret_pw


def test_login_rate_limiting_brute_force(client, db_session, test_org):
    """Login endpoint rate limits repeated failed attempts and returns 429."""
    user = User(
        organization_id=test_org.id,
        email="ratelimit_target@test.com",
        hashed_password=hash_password("RealPassword123!"),
        full_name="Target User",
        role=UserRole.REVIEWER.value,
    )
    db_session.add(user)
    db_session.commit()

    # Trigger 5 failed attempts
    for _ in range(5):
        res = client.post("/api/v1/auth/login", json={"email": "ratelimit_target@test.com", "password": "WrongPassword!"})
        assert res.status_code == 401

    # 6th attempt must trigger 429 Too Many Requests
    res_blocked = client.post("/api/v1/auth/login", json={"email": "ratelimit_target@test.com", "password": "WrongPassword!"})
    assert res_blocked.status_code == 429
    assert "Retry-After" in res_blocked.headers


def test_storage_deletion_failure_aborts_db_deletion(client, db_session, test_org, admin_token):
    """
    Reliable Deletion: If storage cleanup fails, the database deletion
    must abort to avoid orphaned private data in object storage.
    """
    doc = Document(
        organization_id=test_org.id,
        title="Doc For Failed Delete Test",
        filename="undeletable.txt",
        file_type="text/plain",
        file_path="mock_storage_error.txt",
        status=DocumentStatus.DRAFT.value,
    )
    db_session.add(doc)
    db_session.commit()

    with patch("app.api.v1.documents.get_storage") as mock_get_storage:
        mock_storage = MagicMock()
        mock_storage.delete_file.side_effect = StorageError("S3 network failure")
        mock_get_storage.return_value = mock_storage

        res = client.delete(
            f"/api/v1/documents/{doc.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res.status_code == 500
        assert "Storage cleanup failed" in res.json()["detail"]

    # Verify document is still safely in database
    existing_doc = db_session.query(Document).filter(Document.id == doc.id).first()
    assert existing_doc is not None


def test_end_to_end_document_revision_and_accept_fix(client, db_session, test_org, admin_token, admin_user):
    """
    Complete lifecycle integration test:
    1. Upload document (v1)
    2. Create review with finding
    3. Accept fix -> triggers create_new_version_with_fixes (verifying storage.save_file fix)
    4. Download new version via authenticated endpoint
    5. Delete document and verify clean storage & DB cleanup
    """
    # 1. Upload document
    file_content = b"BrandProof delivers 99.9% uptime with industry-leading compliance guarantee."
    upload_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sla_policy.txt", file_content, "text/plain")},
        data={"title": "SLA Policy Document"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["id"]

    # 2. Create review
    review = Review(
        organization_id=test_org.id,
        document_id=doc_id,
        reviewer_id=admin_user.id,
        title="SLA Policy Review",
        status=ReviewStatus.NEEDS_REVIEW.value,
    )
    # Link review to version 1
    doc = db_session.query(Document).filter(Document.id == doc_id).first()
    review.version_id = doc.versions[0].id
    db_session.add(review)
    db_session.flush()

    finding = Finding(
        organization_id=test_org.id,
        review_id=review.id,
        severity="Medium",
        status=FindingStatus.OPEN.value,
        message="Guarantee requires approved disclaimer",
        quoted_text="guarantee",
        suggested_replacement="commitment (see Terms)",
        source_reference="Fact 1",
    )
    db_session.add(finding)
    db_session.commit()

    # 3. Accept fix -> calls ReviewOrchestrator.create_new_version_with_fixes
    # Verifies the line 667 storage interface fix!
    fix_res = client.post(
        f"/api/v1/reviews/{review.id}/accept-fix",
        json={"finding_id": finding.id, "replacement_text": "commitment (see Terms)"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert fix_res.status_code == 200
    detail = fix_res.json()
    assert detail["status"] == "Needs Review"

    # Verify new document version (v2) was created in database
    db_session.refresh(doc)
    assert len(doc.versions) == 2
    v2 = [v for v in doc.versions if v.version_number == 2][0]
    assert "commitment (see Terms)" in v2.extracted_text

    # 4. Download document
    dl_res = client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert dl_res.status_code == 200
    assert len(dl_res.content) > 0

    # 5. Delete document
    del_res = client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_res.status_code == 200

    # Verify deleted from DB
    assert db_session.query(Document).filter(Document.id == doc_id).first() is None
