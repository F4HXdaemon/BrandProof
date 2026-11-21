import uuid
import pytest
from datetime import datetime, timezone, timedelta

from app.models.user import User, UserRole
from app.models.organization import (
    Organization,
    OrganizationMembership,
    OrganizationInvitation,
    MembershipStatus,
    InvitationStatus,
)
from app.core.security import hash_password, create_access_token
from app.core.rate_limit import invite_validate_limiter, invite_join_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    invite_validate_limiter.reset_for_test()
    invite_join_limiter.reset_for_test()


@pytest.fixture
def org_and_admin(db_session):
    uid = uuid.uuid4().hex[:8]
    org = Organization(
        name=f"Acme Corp {uid}",
        slug=f"acme-{uid}",
        description="A premier brand compliance workspace.",
        logo_url="https://example.com/logo.png",
        is_active=True,
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    owner = User(
        email=f"owner_{uid}@example.com",
        hashed_password=hash_password("Password1234!"),
        full_name="Acme Owner",
        role=UserRole.OWNER.value,
        organization_id=org.id,
        is_active=True,
    )
    db_session.add(owner)
    db_session.flush()

    org.owner_id = owner.id
    membership = OrganizationMembership(
        user_id=owner.id,
        organization_id=org.id,
        role=UserRole.OWNER.value,
        status=MembershipStatus.ACTIVE.value,
        joined_at=datetime.now(timezone.utc),
    )
    db_session.add(membership)

    admin = User(
        email=f"admin_{uid}@example.com",
        hashed_password=hash_password("Password1234!"),
        full_name="Acme Admin",
        role=UserRole.ADMIN.value,
        organization_id=org.id,
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()

    admin_membership = OrganizationMembership(
        user_id=admin.id,
        organization_id=org.id,
        role=UserRole.ADMIN.value,
        status=MembershipStatus.ACTIVE.value,
        joined_at=datetime.now(timezone.utc),
    )
    db_session.add(admin_membership)

    db_session.commit()
    db_session.refresh(org)
    db_session.refresh(owner)
    db_session.refresh(admin)

    return {"org": org, "owner": owner, "admin": admin}


def make_auth_headers(user: User) -> dict:
    token = create_access_token(
        subject=user.id,
        extra_claims={
            "role": user.role,
            "org_id": user.organization_id,
            "email": user.email,
        }
    )
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Comprehensive 25 Scenario Tests
# ==============================================================================

def test_01_registration_without_org_succeeds(client):
    """1. Registration without organisation succeeds and user has no organisation initially."""
    uid = uuid.uuid4().hex[:8]
    res = client.post("/api/v1/auth/register", json={
        "email": f"freelance_{uid}@example.com",
        "password": "StrongPassword123!",
        "full_name": "Free Lancer",
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["user"]["organization_id"] is None
    assert data["user"]["email"] == f"freelance_{uid}@example.com"


def test_02_registration_with_org_creates_org_and_owner(client):
    """2. Registration with organisation creates org, sets user as OWNER, activates org."""
    uid = uuid.uuid4().hex[:8]
    res = client.post("/api/v1/auth/register", json={
        "email": f"founder_{uid}@example.com",
        "password": "StrongPassword123!",
        "full_name": "Founder",
        "organization_name": f"Startup {uid}",
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["user"]["organization_id"] is not None
    assert data["user"]["role"] == "Owner"


def test_04_user_with_existing_org_my_organizations(client, org_and_admin):
    """4. User with existing organisation belongs to that org and can list memberships."""
    headers = make_auth_headers(org_and_admin["owner"])
    res = client.get("/api/v1/organizations/my-organizations", headers=headers)
    assert res.status_code == 200
    orgs = res.json()
    assert len(orgs) >= 1
    assert any(o["id"] == org_and_admin["org"].id and o["role"] == "Owner" for o in orgs)


def test_05_user_creates_org_from_onboarding(client):
    """5. User can create an organisation from onboarding/dashboard while logged in."""
    uid = uuid.uuid4().hex[:8]
    reg_res = client.post("/api/v1/auth/register", json={
        "email": f"newuser_{uid}@example.com",
        "password": "StrongPassword123!",
        "full_name": "New User",
    })
    assert reg_res.status_code == 200
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/v1/organizations/create", json={
        "name": f"Brand Venture {uid}",
        "description": "Onboarding created workspace",
    }, headers=headers)
    assert create_res.status_code == 200, create_res.text
    created_data = create_res.json()
    assert created_data["role"] == "Owner"
    assert created_data["organization"]["name"] == f"Brand Venture {uid}"


def test_06_and_07_safe_invitation_preview(client, org_and_admin):
    """6 & 7: User can preview org using invitation code without exposing sensitive data."""
    headers = make_auth_headers(org_and_admin["admin"])
    inv_res = client.post("/api/v1/organizations/current/invitations", json={
        "role": "Reviewer",
        "allowed_roles": ["Reviewer", "Creator"],
        "max_uses": 5,
        "requires_approval": False,
    }, headers=headers)
    assert inv_res.status_code == 200
    inv_code = inv_res.json()["invitation_code"]
    assert inv_code is not None

    # Preview using POST /invitations/validate
    prev_res = client.post("/api/v1/organizations/invitations/validate", json={"code": inv_code})
    assert prev_res.status_code == 200
    data = prev_res.json()
    assert data["valid"] is True
    assert data["organization_name"] == org_and_admin["org"].name
    assert data["organization_slug"] == org_and_admin["org"].slug
    assert data["description"] == org_and_admin["org"].description
    assert set(data["allowed_roles"]) == {"Reviewer", "Creator"}
    # Sensitive fields like hashed passwords, member lists, tokens should NOT exist in preview
    assert "token_hash" not in data
    assert "hashed_password" not in data


def test_08_valid_single_use_instant_join(client, org_and_admin):
    """8. Valid single-use invitation code allows instant join with correct role."""
    headers = make_auth_headers(org_and_admin["admin"])
    inv_res = client.post("/api/v1/organizations/current/invitations", json={
        "role": "Brand Manager",
        "max_uses": 1,
        "requires_approval": False,
    }, headers=headers)
    assert inv_res.status_code == 200
    inv_code = inv_res.json()["invitation_code"]

    # Register an independent user
    uid = uuid.uuid4().hex[:8]
    reg = client.post("/api/v1/auth/register", json={
        "email": f"joiner_{uid}@example.com",
        "password": "Password1234!",
        "full_name": "Joiner User",
    })
    token = reg.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {token}"}

    # Join via invitation code
    join_res = client.post("/api/v1/organizations/invitations/join", json={
        "code": inv_code,
        "role": "Brand Manager",
    }, headers=user_headers)
    assert join_res.status_code == 200, join_res.text
    join_data = join_res.json()
    assert join_data["status"] == "active"
    assert join_data["role"] == "Brand Manager"
    assert join_data["organization"]["id"] == org_and_admin["org"].id


def test_09_single_use_cannot_be_reused(client, org_and_admin):
    """9. Single-use invitation code cannot be reused after acceptance limit reached."""
    headers = make_auth_headers(org_and_admin["admin"])
    inv_res = client.post("/api/v1/organizations/current/invitations", json={
        "role": "Creator",
        "max_uses": 1,
        "requires_approval": False,
    }, headers=headers)
    inv_code = inv_res.json()["invitation_code"]

    # First user joins
    uid1 = uuid.uuid4().hex[:8]
    reg1 = client.post("/api/v1/auth/register", json={
        "email": f"first_{uid1}@example.com",
        "password": "Password1234!",
        "full_name": "First Joiner",
    })
    client.post("/api/v1/organizations/invitations/join", json={"code": inv_code}, headers={"Authorization": f"Bearer {reg1.json()['access_token']}"})

    # Second user attempts to join with exhausted code -> rejected
    uid2 = uuid.uuid4().hex[:8]
    reg2 = client.post("/api/v1/auth/register", json={
        "email": f"second_{uid2}@example.com",
        "password": "Password1234!",
        "full_name": "Second Joiner",
    })
    res2 = client.post("/api/v1/organizations/invitations/join", json={"code": inv_code}, headers={"Authorization": f"Bearer {reg2.json()['access_token']}"})
    assert res2.status_code == 400
    assert "limit" in res2.json()["detail"].lower() or "already" in res2.json()["detail"].lower()


def test_10_limited_use_code_allows_configured_number(client, org_and_admin):
    """10. Limited-use invitation code allows exactly the configured number of joins."""
    headers = make_auth_headers(org_and_admin["admin"])
    inv_res = client.post("/api/v1/organizations/current/invitations", json={
        "role": "Creator",
        "max_uses": 2,
        "requires_approval": False,
    }, headers=headers)
    inv_code = inv_res.json()["invitation_code"]

    # User 1 joins -> 200
    u1 = client.post("/api/v1/auth/register", json={"email": f"lim1_{uuid.uuid4().hex[:6]}@t.com", "password": "Password123!", "full_name": "L1"})
    j1 = client.post("/api/v1/organizations/invitations/join", json={"code": inv_code}, headers={"Authorization": f"Bearer {u1.json()['access_token']}"})
    assert j1.status_code == 200

    # User 2 joins -> 200
    u2 = client.post("/api/v1/auth/register", json={"email": f"lim2_{uuid.uuid4().hex[:6]}@t.com", "password": "Password123!", "full_name": "L2"})
    j2 = client.post("/api/v1/organizations/invitations/join", json={"code": inv_code}, headers={"Authorization": f"Bearer {u2.json()['access_token']}"})
    assert j2.status_code == 200

    # User 3 joins -> 400 exhausted
    u3 = client.post("/api/v1/auth/register", json={"email": f"lim3_{uuid.uuid4().hex[:6]}@t.com", "password": "Password123!", "full_name": "L3"})
    j3 = client.post("/api/v1/organizations/invitations/join", json={"code": inv_code}, headers={"Authorization": f"Bearer {u3.json()['access_token']}"})
    assert j3.status_code == 400
    assert "limit" in j3.json()["detail"].lower()


def test_11_unlimited_use_invitation(client, org_and_admin):
    """11. Unlimited invitation code (max_uses=0) allows multiple joins."""
    headers = make_auth_headers(org_and_admin["admin"])
    inv_res = client.post("/api/v1/organizations/current/invitations", json={
        "role": "Creator",
        "max_uses": 0,
        "requires_approval": False,
    }, headers=headers)
    inv_code = inv_res.json()["invitation_code"]

    for i in range(3):
        u = client.post("/api/v1/auth/register", json={"email": f"unlim{i}_{uuid.uuid4().hex[:6]}@t.com", "password": "Password123!", "full_name": f"Unlim {i}"})
        j = client.post("/api/v1/organizations/invitations/join", json={"code": inv_code}, headers={"Authorization": f"Bearer {u.json()['access_token']}"})
        assert j.status_code == 200


def test_12_expired_invitation_rejected(client, db_session, org_and_admin):
    """12. Expired invitation code is rejected."""
    headers = make_auth_headers(org_and_admin["admin"])
    inv_res = client.post("/api/v1/organizations/current/invitations", json={
        "role": "Creator",
        "expires_in_days": 1,
    }, headers=headers)
    inv_code = inv_res.json()["invitation_code"]

    # Manually expire the invitation in DB
    db_inv = db_session.query(OrganizationInvitation).filter(OrganizationInvitation.invitation_code == inv_code).first()
    db_inv.expires_at = datetime.now(timezone.utc) - timedelta(days=2)
    db_session.commit()

    # Attempt to validate and join
    v_res = client.post("/api/v1/organizations/invitations/validate", json={"code": inv_code})
    assert v_res.status_code == 400
    assert "expired" in v_res.json()["detail"].lower()


def test_13_revoked_invitation_rejected(client, org_and_admin):
    """13. Revoked invitation code is rejected."""
    headers = make_auth_headers(org_and_admin["admin"])
    inv_res = client.post("/api/v1/organizations/current/invitations", json={"role": "Creator"}, headers=headers)
    inv_code = inv_res.json()["invitation_code"]

    # Get invitation ID and revoke
    list_res = client.get("/api/v1/organizations/current/invitations", headers=headers)
    inv_item = [x for x in list_res.json() if x["invitation_code"] == inv_code][0]
    rev_res = client.delete(f"/api/v1/organizations/current/invitations/{inv_item['id']}", headers=headers)
    assert rev_res.status_code == 200

    # Validation must reject
    v_res = client.post("/api/v1/organizations/invitations/validate", json={"code": inv_code})
    assert v_res.status_code == 400
    assert "revoked" in v_res.json()["detail"].lower() or "no longer valid" in v_res.json()["detail"].lower()


def test_14_non_existent_code_returns_404(client):
    """14. Non-existent invitation code returns clear error."""
    res = client.post("/api/v1/organizations/invitations/validate", json={"code": "BP-9999-9999"})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_15_and_16_multi_role_selection_and_boundary(client, org_and_admin):
    """15 & 16: Multi-role invitation allows selecting permitted role, rejects unpermitted role."""
    headers = make_auth_headers(org_and_admin["admin"])
    inv_res = client.post("/api/v1/organizations/current/invitations", json={
        "allowed_roles": ["Reviewer", "Creator"],
        "max_uses": 5,
    }, headers=headers)
    inv_code = inv_res.json()["invitation_code"]

    uid = uuid.uuid4().hex[:8]
    u = client.post("/api/v1/auth/register", json={"email": f"role_{uid}@t.com", "password": "Password123!", "full_name": "Role User"})
    u_headers = {"Authorization": f"Bearer {u.json()['access_token']}"}

    # Attempt to self-select "Brand Manager" (not in allowed list) -> 400
    bad_join = client.post("/api/v1/organizations/invitations/join", json={
        "code": inv_code,
        "role": "Brand Manager",
    }, headers=u_headers)
    assert bad_join.status_code == 400
    assert "not permitted" in bad_join.json()["detail"].lower()

    # Select permitted "Reviewer" role -> 200
    good_join = client.post("/api/v1/organizations/invitations/join", json={
        "code": inv_code,
        "role": "Reviewer",
    }, headers=u_headers)
    assert good_join.status_code == 200
    assert good_join.json()["role"] == "Reviewer"


def test_17_user_cannot_self_assign_owner_or_admin(client, org_and_admin):
    """17. User cannot self-assign OWNER or ADMIN through an invitation."""
    headers = make_auth_headers(org_and_admin["admin"])
    # Admins cannot issue ADMIN or OWNER invites
    admin_try = client.post("/api/v1/organizations/current/invitations", json={"role": "Owner"}, headers=headers)
    assert admin_try.status_code in (400, 403)

    admin_try_admin = client.post("/api/v1/organizations/current/invitations", json={"role": "Admin"}, headers=headers)
    assert admin_try_admin.status_code == 403

    # Ordinary invite cannot be joined as Owner
    inv_res = client.post("/api/v1/organizations/current/invitations", json={"role": "Creator"}, headers=headers)
    inv_code = inv_res.json()["invitation_code"]

    u = client.post("/api/v1/auth/register", json={"email": f"hacker_{uuid.uuid4().hex[:6]}@t.com", "password": "Password123!", "full_name": "Hacker"})
    u_headers = {"Authorization": f"Bearer {u.json()['access_token']}"}

    join_owner = client.post("/api/v1/organizations/invitations/join", json={"code": inv_code, "role": "Owner"}, headers=u_headers)
    assert join_owner.status_code in (400, 403)


def test_18_and_19_approval_required_flow(client, org_and_admin):
    """18 & 19: Invitation requiring approval creates pending request; user has no active org."""
    headers = make_auth_headers(org_and_admin["admin"])
    inv_res = client.post("/api/v1/organizations/current/invitations", json={
        "role": "Fact Owner",
        "requires_approval": True,
    }, headers=headers)
    inv_code = inv_res.json()["invitation_code"]

    uid = uuid.uuid4().hex[:8]
    u = client.post("/api/v1/auth/register", json={"email": f"applicant_{uid}@t.com", "password": "Password123!", "full_name": "Applicant"})
    u_headers = {"Authorization": f"Bearer {u.json()['access_token']}"}

    join_res = client.post("/api/v1/organizations/invitations/join", json={"code": inv_code}, headers=u_headers)
    assert join_res.status_code == 200
    assert join_res.json()["status"] == "pending_approval"

    # User still does NOT have access to organization profile
    curr_org_res = client.get("/api/v1/organizations/current", headers=u_headers)
    assert curr_org_res.status_code in (403, 404)


def test_20_21_22_approve_and_reject_membership_requests(client, org_and_admin):
    """20, 21, 22: Admin can list, approve, and reject membership requests."""
    admin_headers = make_auth_headers(org_and_admin["admin"])
    inv_res = client.post("/api/v1/organizations/current/invitations", json={
        "role": "Creator",
        "requires_approval": True,
        "max_uses": 5,
    }, headers=admin_headers)
    inv_code = inv_res.json()["invitation_code"]

    # Applicant 1 (to approve)
    u1 = client.post("/api/v1/auth/register", json={"email": f"app1_{uuid.uuid4().hex[:6]}@t.com", "password": "Password123!", "full_name": "App One"})
    client.post("/api/v1/organizations/invitations/join", json={"code": inv_code}, headers={"Authorization": f"Bearer {u1.json()['access_token']}"})

    # Applicant 2 (to reject)
    u2 = client.post("/api/v1/auth/register", json={"email": f"app2_{uuid.uuid4().hex[:6]}@t.com", "password": "Password123!", "full_name": "App Two"})
    client.post("/api/v1/organizations/invitations/join", json={"code": inv_code}, headers={"Authorization": f"Bearer {u2.json()['access_token']}"})

    # Admin lists pending requests
    reqs_res = client.get("/api/v1/organizations/current/membership-requests", headers=admin_headers)
    assert reqs_res.status_code == 200
    pending_list = reqs_res.json()
    assert len(pending_list) >= 2

    mem1 = [m for m in pending_list if "app1" in m["email"]][0]
    mem2 = [m for m in pending_list if "app2" in m["email"]][0]

    # Admin approves Applicant 1
    appr_res = client.post(f"/api/v1/organizations/current/membership-requests/{mem1['id']}/approve", headers=admin_headers)
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "active"

    # Admin rejects Applicant 2
    rej_res = client.post(f"/api/v1/organizations/current/membership-requests/{mem2['id']}/reject", headers=admin_headers)
    assert rej_res.status_code == 200
    assert rej_res.json()["success"] is True

    # User 1 now has access to organization profile
    u1_login = client.post("/api/v1/auth/login", json={"email": u1.json()["user"]["email"], "password": "Password123!"})
    assert u1_login.status_code == 200
    u1_headers = {"Authorization": f"Bearer {u1_login.json()['access_token']}"}
    u1_curr = client.get("/api/v1/organizations/current", headers=u1_headers)
    assert u1_curr.status_code == 200
    assert u1_curr.json()["id"] == org_and_admin["org"].id


def test_23_and_24_multi_organization_switching(client, org_and_admin):
    """23 & 24: User belongs to multiple orgs with distinct roles and switches between them."""
    uid = uuid.uuid4().hex[:8]
    # Create user
    u = client.post("/api/v1/auth/register", json={"email": f"multi_{uid}@t.com", "password": "Password123!", "full_name": "Multi Org User"})
    u_token = u.json()["access_token"]
    u_headers = {"Authorization": f"Bearer {u_token}"}

    # Org 1: User creates org -> role is Owner
    org1_res = client.post("/api/v1/organizations/create", json={"name": f"Org 1 {uid}"}, headers=u_headers)
    org1_id = org1_res.json()["organization"]["id"]

    # Org 2: test_org invites user as Reviewer
    admin_headers = make_auth_headers(org_and_admin["admin"])
    inv = client.post("/api/v1/organizations/current/invitations", json={"role": "Reviewer", "max_uses": 1}, headers=admin_headers)
    join_res = client.post("/api/v1/organizations/invitations/join", json={"code": inv.json()["invitation_code"]}, headers=u_headers)
    assert join_res.status_code == 200
    assert join_res.json()["role"] == "Reviewer"

    # User switches back to Org 1
    switch_res = client.post("/api/v1/organizations/switch", json={"organization_id": org1_id}, headers=u_headers)
    assert switch_res.status_code == 200
    assert switch_res.json()["role"] == "Owner"
    assert switch_res.json()["organization"]["id"] == org1_id


def test_25_rate_limiting_on_validation(client):
    """25: Rate limiting prevents brute-force invitation code guessing."""
    # invite_validate_limiter has a limit of 30 per minute
    statuses = []
    for _ in range(35):
        r = client.post("/api/v1/organizations/invitations/validate", json={"code": "BP-FAKE-CODE"})
        statuses.append(r.status_code)

    assert 429 in statuses
