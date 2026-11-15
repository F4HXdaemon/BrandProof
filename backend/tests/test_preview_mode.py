import os
import tempfile
import uuid
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.document import Document, DocumentStatus
from app.core.security import hash_password, create_access_token
from app.services.storage import LocalStorageBackend


def test_preview_configuration_defaults():
    """Preview mode permits SQLite and LocalStorage without PostgreSQL or S3 credentials."""
    s = Settings(
        ENVIRONMENT="preview",
        DATABASE_URL="",
        STORAGE_DIR="",
        SECRET_KEY="any-preview-test-secret-key-32-chars",
    )
    assert s.ENVIRONMENT == "preview"
    assert s.DATABASE_URL.startswith("sqlite:///")
    assert "brandproof-preview.db" in s.DATABASE_URL
    assert "brandproof-uploads" in s.STORAGE_DIR
    assert s.STORAGE_BACKEND == "local"
    assert s.ENABLE_DEMO_RESET is False
    assert s.DEBUG is False


def test_production_invariants_remain_strict_against_sqlite():
    """Production mode must still strictly reject SQLite and insecure secrets."""
    # 1. Reject SQLite in production
    with pytest.raises(ValueError, match="SQLite is not permitted in production"):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="sqlite:///./test.db",
            SECRET_KEY="a" * 35,
        )

    # 2. Reject short secret in production
    with pytest.raises(ValueError, match="SECRET_KEY must be a cryptographically secure"):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            SECRET_KEY="short-secret",
        )


def test_preview_health_endpoint_returns_notice(client, monkeypatch):
    """Health check endpoint in preview mode surfaces ephemeral storage notice."""
    from app.config import settings
    monkeypatch.setattr(settings, "ENVIRONMENT", "preview")

    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["environment"] == "preview"
    assert "PREVIEW MODE" in data["warning"]


def test_preview_root_endpoint_returns_notice(client, monkeypatch):
    """Root endpoint in preview mode returns operational status with preview notice."""
    from app.config import settings
    monkeypatch.setattr(settings, "ENVIRONMENT", "preview")

    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "operational"
    assert "PREVIEW DEPLOYMENT" in data["preview_notice"]


def test_preview_demo_reset_forbidden(client, monkeypatch):
    """Demo reset endpoint is strictly forbidden in preview mode."""
    from app.config import settings
    monkeypatch.setattr(settings, "ENVIRONMENT", "preview")

    res = client.post("/api/v1/demo/reset")
    assert res.status_code == 403
    assert "disabled in production and preview" in res.json()["detail"]


def test_preview_core_lifecycle_workflows(client, db_session):
    """
    Test end-to-end user journey in preview mode:
    1. Register new organization and admin
    2. Authenticate and retrieve JWT
    3. Ingest document via upload
    4. Access dashboard metrics
    5. Download document via authenticated endpoint
    """
    uid = uuid.uuid4().hex[:6]
    # 1. Register
    reg_payload = {
        "organization_name": f"Preview Org {uid}",
        "organization_slug": f"preview-org-{uid}",
        "email": f"founder_{uid}@preview.com",
        "password": "PreviewPassword123!",
        "full_name": f"Preview Admin {uid}",
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 200
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": f"founder_{uid}@preview.com", "password": "PreviewPassword123!"}
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # 3. Dashboard metrics
    dash_res = client.get("/api/v1/dashboard", headers=headers)
    assert dash_res.status_code == 200

    # 4. Upload document
    doc_content = b"Preview Test Document Content: BrandProof guarantees compliance with 100% precision."
    upload_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("preview_doc.txt", doc_content, "text/plain")},
        data={"title": "Preview Policy Test"},
        headers=headers,
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["id"]

    # 5. Download document
    dl_res = client.get(f"/api/v1/documents/{doc_id}/download", headers=headers)
    assert dl_res.status_code == 200
    assert dl_res.content == doc_content
