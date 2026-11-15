import uuid
import pytest
from app.models.organization import Organization
from app.models.user import User, UserRole


def test_registration_success(client):
    """Registering a new organization and admin creates records and issues a token."""
    uid = uuid.uuid4().hex[:6]
    payload = {
        "organization_name": f"Acme Labs {uid}",
        "organization_slug": f"acme-labs-{uid}",
        "email": f"owner-{uid}@acmelabs.com",
        "password": "SecurePassword123!",
        "full_name": f"Alice Founder {uid}",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == payload["email"].lower()
    assert data["user"]["role"] == "Admin"
    assert data["user"]["full_name"] == payload["full_name"]


def test_registration_validation_rules(client):
    """Enforces password complexity, length bounds, email format, and org name length."""
    uid = uuid.uuid4().hex[:6]

    # 1. Password too short (< 8 chars)
    res_short = client.post("/api/v1/auth/register", json={
        "organization_name": f"Short Org {uid}",
        "email": f"short-{uid}@test.com",
        "password": "short",
        "full_name": "Short Pass User",
    })
    assert res_short.status_code in (400, 422)

    # 2. Password too long (> 72 bytes)
    res_long = client.post("/api/v1/auth/register", json={
        "organization_name": f"Long Org {uid}",
        "email": f"long-{uid}@test.com",
        "password": "P" * 75,
        "full_name": "Long Pass User",
    })
    assert res_long.status_code in (400, 422)

    # 3. Org name too short (< 2 chars)
    res_short_org = client.post("/api/v1/auth/register", json={
        "organization_name": "X",
        "email": f"org-{uid}@test.com",
        "password": "ValidPassword123!",
        "full_name": "Test User",
    })
    assert res_short_org.status_code in (400, 422)

    # 4. Invalid email format
    res_invalid_email = client.post("/api/v1/auth/register", json={
        "organization_name": f"Valid Org {uid}",
        "email": "not-an-email",
        "password": "ValidPassword123!",
        "full_name": "Test User",
    })
    assert res_invalid_email.status_code in (400, 422)


def test_duplicate_registration_rejection(client):
    """Prevents organization takeover / collision and duplicate user registration."""
    uid = uuid.uuid4().hex[:6]
    payload = {
        "organization_name": f"Unique Org {uid}",
        "organization_slug": f"unique-org-{uid}",
        "email": f"first-{uid}@uniqueorg.com",
        "password": "StrongPassword123!",
        "full_name": "First User",
    }
    # Initial registration
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 200

    # Duplicate slug rejection (409 Conflict)
    res_dup_slug = client.post("/api/v1/auth/register", json={
        "organization_name": f"Unique Org {uid}",
        "organization_slug": f"unique-org-{uid}",
        "email": f"different-{uid}@uniqueorg.com",
        "password": "StrongPassword123!",
        "full_name": "Second User",
    })
    assert res_dup_slug.status_code == 409

    # Duplicate email rejection (400 Bad Request)
    res_dup_email = client.post("/api/v1/auth/register", json={
        "organization_name": f"Different Org {uid}",
        "organization_slug": f"diff-org-{uid}",
        "email": f"first-{uid}@uniqueorg.com",
        "password": "StrongPassword123!",
        "full_name": "Duplicate Email User",
    })
    assert res_dup_email.status_code == 400


def test_end_to_end_user_lifecycle(client):
    """Tests registration, sign-in, session verification, dashboard, and settings access."""
    uid = uuid.uuid4().hex[:6]
    org_name = f"Lifecycle Org {uid}"
    email = f"lifecycle-{uid}@company.com"
    password = "LifecyclePassword2026!"
    full_name = f"Lifecycle Admin {uid}"

    # 1. Register
    reg_res = client.post("/api/v1/auth/register", json={
        "organization_name": org_name,
        "email": email,
        "password": password,
        "full_name": full_name,
    })
    assert reg_res.status_code == 200
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Login with credentials
    login_res = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    assert login_res.status_code == 200
    login_token = login_res.json()["access_token"]
    assert login_token is not None

    # 3. Login with invalid password fails
    invalid_login = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "WrongPassword999!",
    })
    assert invalid_login.status_code == 401

    # 4. Verify /auth/me
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == email.lower()
    assert me_data["role"] == "Admin"
    assert me_data["full_name"] == full_name

    # 5. Verify /organizations/current
    org_res = client.get("/api/v1/organizations/current", headers=headers)
    assert org_res.status_code == 200
    org_data = org_res.json()
    assert org_data["name"] == org_name

    # 6. Verify /dashboard loads pristine data without crashing
    dash_res = client.get("/api/v1/dashboard", headers=headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert dash_data["metrics"]["open_reviews"] == 0
    assert dash_data["metrics"]["active_facts"] == 0
    assert dash_data["recent_reviews"] == []
    assert dash_data["risk_overview"]["overall_score"] == 100
    assert dash_data["risk_overview"]["status"] == "Optimal"
