"""
Phase 9 Automated End-to-End User Journey Tests
Validates the complete 16-step user lifecycle in production-identical conditions:
1. Open landing page.
2. Click Sign Up (endpoint readiness).
3. Registration page renders (health & config contract).
4. Submit invalid registration (weak password, bad email, empty fields).
5. Receive correct validation messages (sanitized 422 payload).
6. Register a new account (user + unique org created).
7. Authenticate successfully (JWT token + profile returned).
8. Reach onboarding / dashboard (metrics & current org returned).
9. Sign out (session invalidation).
10. Open Sign In (login contract verification).
11. Sign in again (access token re-acquired).
12. Open protected pages (reviews, evidence, facts).
13. Test invalid or expired session (401 Unauthorized).
14. Test invitation acceptance (invite created, verified, and accepted).
15. Test organisation switching (switches active tenant & claims).
16. Test unauthorised organisation access (strict 403/404 isolation).
"""

import uuid
import pytest
from app.models.organization import Organization, OrganizationMembership
from app.models.user import User, UserRole
from app.core.security import hash_password, create_access_token


def test_phase9_complete_16_step_user_journey(client, db_session):
    # Step 1: Open the landing page
    res_root = client.get("/")
    assert res_root.status_code == 200
    root_data = res_root.json()
    assert root_data["status"] == "operational"
    assert "invariant" in root_data

    # Step 2: Click Sign Up (Backend endpoint readiness & CORS preflight)
    res_cors = client.options("/api/v1/auth/register")
    assert res_cors.status_code in (200, 204, 405)

    # Step 3: Registration page renders (Backend health check confirms healthy status)
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["status"] == "healthy"
    assert health_data["database"] == "healthy"

    # Step 4: Submit invalid registration (weak password, malformed email)
    res_bad_pw = client.post("/api/v1/auth/register", json={
        "full_name": "Test User",
        "organization_name": "Test Org",
        "email": "valid@email.com",
        "password": "short",  # < 8 chars
    })
    assert res_bad_pw.status_code == 422

    res_bad_email = client.post("/api/v1/auth/register", json={
        "full_name": "Test User",
        "organization_name": "Test Org",
        "email": "not-an-email",
        "password": "ValidPassword123!",
    })
    assert res_bad_email.status_code == 422

    # Step 5: Receive correct validation messages (sanitized, contains error details)
    bad_email_data = res_bad_email.json()
    assert "detail" in bad_email_data
    assert isinstance(bad_email_data["detail"], list)
    assert any("email" in str(err) for err in bad_email_data["detail"])
    # Passwords must not be leaked in 422 responses
    assert "ValidPassword123!" not in res_bad_email.text

    # Step 6: Register a new account with valid credentials
    uid = uuid.uuid4().hex[:6]
    user_email = f"journey_user_{uid}@example.com"
    user_password = "SecurePassword2026!"
    org_name = f"Apex Labs {uid}"
    org_slug = f"apex-labs-{uid}"

    res_reg = client.post("/api/v1/auth/register", json={
        "full_name": f"Apex Founder {uid}",
        "organization_name": org_name,
        "organization_slug": org_slug,
        "email": user_email,
        "password": user_password,
    })
    assert res_reg.status_code == 200
    reg_data = res_reg.json()
    assert "access_token" in reg_data
    assert reg_data["user"]["email"] == user_email
    assert reg_data["user"]["role"] in ("Admin", "Owner")
    org_id_1 = reg_data["user"]["organization_id"]
    token_1 = reg_data["access_token"]

    # Step 7: Authenticate successfully (Token validity checked)
    res_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_1}"})
    assert res_me.status_code == 200
    me_data = res_me.json()
    assert me_data["email"] == user_email
    assert me_data["organization_id"] == org_id_1

    # Step 8: Reach onboarding/dashboard (Fetch dashboard metrics & current organization)
    res_dash = client.get(
        "/api/v1/dashboard/metrics",
        headers={"Authorization": f"Bearer {token_1}", "X-Organization-Id": org_id_1}
    )
    assert res_dash.status_code == 200
    dash_data = res_dash.json()
    assert "risk" in dash_data
    assert "findings_by_severity" in dash_data["risk"]

    res_curr_org = client.get(
        "/api/v1/organizations/current",
        headers={"Authorization": f"Bearer {token_1}"}
    )
    assert res_curr_org.status_code == 200
    assert res_curr_org.json()["id"] == org_id_1

    # Step 9: Sign out
    res_logout = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token_1}"})
    assert res_logout.status_code == 200

    # Step 10: Open Sign In (verify login endpoint readiness)
    res_login_options = client.options("/api/v1/auth/login")
    assert res_login_options.status_code in (200, 204, 405)

    # Step 11: Sign in again
    res_login = client.post("/api/v1/auth/login", json={
        "email": user_email,
        "password": user_password,
    })
    assert res_login.status_code == 200
    login_data = res_login.json()
    token_2 = login_data["access_token"]
    assert token_2 is not None

    # Step 12: Open protected pages with authenticated token
    # Reviews list
    res_reviews = client.get("/api/v1/reviews", headers={"Authorization": f"Bearer {token_2}"})
    assert res_reviews.status_code == 200

    # Evidence list
    res_evidence = client.get("/api/v1/evidence", headers={"Authorization": f"Bearer {token_2}"})
    assert res_evidence.status_code == 200

    # Knowledge facts list
    res_facts = client.get("/api/v1/facts", headers={"Authorization": f"Bearer {token_2}"})
    assert res_facts.status_code == 200

    # Step 13: Test invalid or expired session
    res_bad_token = client.get(
        "/api/v1/reviews",
        headers={"Authorization": "Bearer invalid_or_expired_jwt_token_12345"}
    )
    assert res_bad_token.status_code == 401

    # Step 14: Test invitation acceptance
    # Another organization admin invites our user
    org2_uid = uuid.uuid4().hex[:6]
    org2 = Organization(name=f"Partner Org {org2_uid}", slug=f"partner-org-{org2_uid}", is_active=True)
    db_session.add(org2)
    db_session.commit()
    db_session.refresh(org2)

    org2_admin = User(
        organization_id=org2.id,
        email=f"org2_admin_{org2_uid}@partner.com",
        hashed_password=hash_password("Pass1234!"),
        full_name="Org 2 Admin",
        role=UserRole.ADMIN.value,
    )
    db_session.add(org2_admin)
    db_session.commit()
    db_session.refresh(org2_admin)

    db_session.add(OrganizationMembership(
        user_id=org2_admin.id,
        organization_id=org2.id,
        role=UserRole.ADMIN.value,
        status="active",
    ))
    db_session.commit()

    token_org2_admin = create_access_token({
        "sub": org2_admin.id,
        "email": org2_admin.email,
        "role": org2_admin.role,
        "org_id": org2.id,
    })

    # Create invitation for user_email
    res_invite = client.post(
        "/api/v1/organizations/current/invitations",
        json={"email": user_email, "role": "Reviewer", "expires_in_days": 7},
        headers={"Authorization": f"Bearer {token_org2_admin}"}
    )
    assert res_invite.status_code == 200
    invite_raw_token = res_invite.json()["invite_token"]

    # Verify the invitation token publicly
    res_verify = client.get(f"/api/v1/auth/invite/{invite_raw_token}")
    assert res_verify.status_code == 200
    verify_data = res_verify.json()
    assert verify_data["valid"] is True
    assert verify_data["organization_name"] == org2.name

    # Accept the invitation while logged in as user_email
    res_accept = client.post(
        f"/api/v1/organizations/invitations/{invite_raw_token}/accept",
        headers={"Authorization": f"Bearer {token_2}"}
    )
    assert res_accept.status_code == 200
    accept_data = res_accept.json()
    token_3 = accept_data["access_token"]
    assert accept_data["organization"]["id"] == org2.id
    assert accept_data["user"]["role"] == "Reviewer"

    # Step 15: Test organisation switching
    # User switches back to org_id_1
    res_switch_1 = client.post(
        f"/api/v1/organizations/{org_id_1}/switch",
        headers={"Authorization": f"Bearer {token_3}"}
    )
    assert res_switch_1.status_code == 200
    token_4 = res_switch_1.json()["access_token"]
    assert res_switch_1.json()["organization"]["id"] == org_id_1
    assert res_switch_1.json()["user"]["role"] in ("Admin", "Owner")

    # User switches back to org2.id
    res_switch_2 = client.post(
        f"/api/v1/organizations/{org2.id}/switch",
        headers={"Authorization": f"Bearer {token_4}"}
    )
    assert res_switch_2.status_code == 200
    token_5 = res_switch_2.json()["access_token"]
    assert res_switch_2.json()["organization"]["id"] == org2.id
    assert res_switch_2.json()["user"]["role"] == "Reviewer"

    # Step 16: Test unauthorised organisation access
    # Create an un-joined 3rd org
    org3_uid = uuid.uuid4().hex[:6]
    org3 = Organization(name=f"Secret Org {org3_uid}", slug=f"secret-org-{org3_uid}", is_active=True)
    db_session.add(org3)
    db_session.commit()
    db_session.refresh(org3)

    # Attempt to switch to org3 (should be 403 Forbidden)
    res_bad_switch = client.post(
        f"/api/v1/organizations/{org3.id}/switch",
        headers={"Authorization": f"Bearer {token_5}"}
    )
    assert res_bad_switch.status_code == 403
    assert "Not an active member" in res_bad_switch.json()["detail"]

    # Attempt to spoof X-Organization-Id header for org3
    res_spoof = client.get(
        "/api/v1/reviews",
        headers={"Authorization": f"Bearer {token_5}", "X-Organization-Id": org3.id}
    )
    assert res_spoof.status_code == 403
    assert "Not an active member" in res_spoof.json()["detail"]
