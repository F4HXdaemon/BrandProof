import uuid
from datetime import timedelta
import pytest
from app.core.security import create_access_token, create_invite_token, hash_password
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.document import Document
from app.models.review import Review


def test_auth_suite_successful_registration(client):
    """1. Successful user and organization registration."""
    uid = uuid.uuid4().hex[:6]
    payload = {
        "organization_name": f"Acme Growth {uid}",
        "organization_slug": f"acme-growth-{uid}",
        "email": f"founder_{uid}@acmegrowth.com",
        "password": "StrongPassword2026!",
        "full_name": f"Founder {uid}",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == payload["email"].lower()
    assert data["user"]["role"] == "Admin"
    assert data["user"]["full_name"] == payload["full_name"]


def test_auth_suite_duplicate_email_registration(client, admin_user):
    """2. Registration fails with duplicate email address."""
    uid = uuid.uuid4().hex[:6]
    payload = {
        "organization_name": f"Another Org {uid}",
        "organization_slug": f"another-org-{uid}",
        "email": admin_user.email,  # Already existing email
        "password": "StrongPassword2026!",
        "full_name": "Duplicate Tester",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"]


def test_auth_suite_invalid_email(client):
    """3. Registration fails with malformed email."""
    uid = uuid.uuid4().hex[:6]
    payload = {
        "organization_name": f"Org {uid}",
        "email": "not-an-email-address",
        "password": "StrongPassword2026!",
        "full_name": "Invalid Email",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code in (400, 422)


def test_auth_suite_weak_password(client):
    """4. Registration fails with weak / too-short password."""
    uid = uuid.uuid4().hex[:6]
    payload = {
        "organization_name": f"Org {uid}",
        "email": f"weak_{uid}@test.com",
        "password": "short",
        "full_name": "Weak Password User",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code in (400, 422)


def test_auth_suite_incorrect_login_credentials(client, admin_user):
    """5. Login fails with incorrect credentials."""
    # A) Wrong password
    res_wrong_pw = client.post("/api/v1/auth/login", json={
        "email": admin_user.email,
        "password": "WrongPassword999!",
    })
    assert res_wrong_pw.status_code == 401
    assert "Incorrect email or password" in res_wrong_pw.json()["detail"]

    # B) Non-existent email
    res_no_user = client.post("/api/v1/auth/login", json={
        "email": "nonexistent_user_999@test.com",
        "password": "AnyPassword123!",
    })
    assert res_no_user.status_code == 401


def test_auth_suite_successful_login(client, admin_user):
    """6. Successful login returns access token and user profile."""
    res = client.post("/api/v1/auth/login", json={
        "email": admin_user.email,
        "password": "Pass1234!",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["id"] == admin_user.id
    assert data["user"]["email"] == admin_user.email


def test_auth_suite_protected_endpoint_without_auth(client):
    """7. Accessing protected endpoints without token returns 401."""
    # /auth/me
    res_me = client.get("/api/v1/auth/me")
    assert res_me.status_code == 401
    assert "Authentication credentials were not provided" in res_me.json()["detail"]

    # /organizations/current
    res_org = client.get("/api/v1/organizations/current")
    assert res_org.status_code == 401

    # /documents
    res_docs = client.get("/api/v1/documents")
    assert res_docs.status_code == 401


def test_auth_suite_protected_endpoint_with_auth(client, admin_token, admin_user):
    """8. Accessing protected endpoints with valid token succeeds."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == admin_user.id
    assert data["email"] == admin_user.email


def test_auth_suite_logout(client, admin_token):
    """9. Logout endpoint clears session cookie and records audit event."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post("/api/v1/auth/logout", headers=headers)
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Check that Set-Cookie header invalidates brandproof_token
    set_cookie_header = res.headers.get("set-cookie", "")
    assert "brandproof_token" in set_cookie_header


def test_auth_suite_expired_session(client, admin_user):
    """10. Access with expired token returns 401 with Token has expired error."""
    expired_token = create_access_token(
        subject=admin_user.id,
        expires_delta=timedelta(seconds=-60),  # expired 60 seconds ago
        extra_claims={"role": admin_user.role, "org_id": admin_user.organization_id}
    )
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "Token has expired" in res.json()["detail"]


def test_auth_suite_cross_organization_access_prevented(client, db_session, test_org, creator_user, creator_token):
    """11. Cross-organization data access strictly prevented."""
    # Create Organization B and data belonging to Organization B
    uid = uuid.uuid4().hex[:6]
    victim_org = Organization(
        name=f"Victim Org {uid}",
        slug=f"victim-org-{uid}",
        domain=f"victim{uid}.com"
    )
    db_session.add(victim_org)
    db_session.flush()

    victim_user = User(
        organization_id=victim_org.id,
        email=f"victim_{uid}@victim.com",
        hashed_password=hash_password("Pass1234!"),
        full_name="Victim User",
        role=UserRole.ADMIN.value
    )
    db_session.add(victim_user)
    db_session.flush()

    victim_doc = Document(
        organization_id=victim_org.id,
        creator_id=victim_user.id,
        title="Victim Private Document",
        filename="private_doc.txt",
        file_path="victim/private_doc.txt",
        file_size=100,
        file_type="text/plain",
    )
    db_session.add(victim_doc)
    db_session.flush()

    victim_review = Review(
        organization_id=victim_org.id,
        document_id=victim_doc.id,
        reviewer_id=victim_user.id,
        title="Victim Secret Review",
        product="Secret Product",
        region="Global",
        channel="All",
        status="Needs Review",
    )
    db_session.add(victim_review)
    db_session.commit()

    # Attacker from test_org attempts to access victim's document
    headers = {"Authorization": f"Bearer {creator_token}"}
    res_doc = client.get(f"/api/v1/documents/{victim_doc.id}", headers=headers)
    assert res_doc.status_code == 404

    # Attacker attempts to access victim's review
    res_rev = client.get(f"/api/v1/reviews/{victim_review.id}", headers=headers)
    assert res_rev.status_code == 404

    # Attacker attempts to access victim's user profile
    res_usr = client.get(f"/api/v1/users/{victim_user.id}", headers=headers)
    assert res_usr.status_code == 404


def test_auth_suite_invite_flow_and_privilege_restriction(client, admin_token, db_session, test_org):
    """
    12. Organization invite flow:
    - Admin creates invite
    - Prospective user verifies invite
    - User registers via invite
    - Privileged role assignment is strictly rejected (cannot register as Admin)
    - User is added to existing org as Creator
    """
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Step 1: Admin generates invite
    invite_res = client.post(
        "/api/v1/organizations/current/invites",
        json={"email": None, "expires_in_days": 3},
        headers=admin_headers
    )
    assert invite_res.status_code == 200
    invite_data = invite_res.json()
    invite_token = invite_data["invite_token"]
    assert invite_data["organization_id"] == test_org.id

    # Step 2: Verify invite publicly
    verify_res = client.get(f"/api/v1/organizations/invites/verify?token={invite_token}")
    assert verify_res.status_code == 200
    assert verify_res.json()["organization_id"] == test_org.id
    assert verify_res.json()["organization_name"] == test_org.name

    # Step 3: Privilege Escalation Attempt: User tries to register with role="Admin"
    uid = uuid.uuid4().hex[:6]
    bad_payload = {
        "invite_token": invite_token,
        "email": f"hacker_{uid}@member.com",
        "password": "SecurePassword2026!",
        "full_name": f"Hacker {uid}",
        "role": "Admin",  # Attempting to assign themselves Admin!
    }
    bad_res = client.post("/api/v1/auth/register", json=bad_payload)
    assert bad_res.status_code == 400
    assert "Privileged roles cannot be self-assigned" in bad_res.json()["detail"]

    # Step 4: Valid Registration via Invite (joins as Creator)
    valid_payload = {
        "invite_token": invite_token,
        "email": f"teammate_{uid}@member.com",
        "password": "SecurePassword2026!",
        "full_name": f"Team Member {uid}",
    }
    reg_res = client.post("/api/v1/auth/register", json=valid_payload)
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert reg_data["user"]["role"] == "Creator"
    assert reg_data["user"]["organization_id"] == test_org.id

    # Step 5: Verify new user can sign in and access org members
    login_res = client.post("/api/v1/auth/login", json={
        "email": valid_payload["email"],
        "password": valid_payload["password"],
    })
    assert login_res.status_code == 200
    new_token = login_res.json()["access_token"]
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "Creator"
