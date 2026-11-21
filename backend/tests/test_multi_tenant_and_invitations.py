import uuid
from datetime import datetime, timezone, timedelta
import pytest
from app.models.user import User, UserRole
from app.models.organization import (
    Organization,
    OrganizationMembership,
    OrganizationInvitation,
    MembershipStatus,
    InvitationStatus,
)
from app.models.review import Review
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.knowledge import Fact, Guideline
from app.core.security import hash_password, create_access_token, hash_invitation_token


def test_scenario_01_user_registers_and_creates_new_organization(client):
    """Scenario 1: User registers and creates a new organisation."""
    uid = uuid.uuid4().hex[:6]
    payload = {
        "organization_name": f"Acme Innovations {uid}",
        "organization_slug": f"acme-innovations-{uid}",
        "email": f"founder_{uid}@acmeinnovations.com",
        "password": "Password1234!",
        "full_name": f"Founder {uid}",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == payload["email"].lower()
    assert data["user"]["organization_id"] is not None

    token = data["access_token"]
    # Check current organization
    org_res = client.get("/api/v1/organizations/current", headers={"Authorization": f"Bearer {token}"})
    assert org_res.status_code == 200
    org_data = org_res.json()
    assert org_data["name"] == payload["organization_name"]
    assert org_data["slug"] == payload["organization_slug"]
    assert org_data["owner_id"] == data["user"]["id"]


def test_scenario_02_and_08_admin_invites_member(client, admin_token, test_org):
    """Scenarios 2 & 8: Organisation admin invites another member."""
    invitee_email = f"colleague_{uuid.uuid4().hex[:6]}@partner.com"
    payload = {
        "email": invitee_email,
        "role": "Reviewer",
        "expires_in_days": 5,
    }
    res = client.post(
        "/api/v1/organizations/current/invitations",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "invite_token" in data
    assert data["organization_id"] == test_org.id
    assert data["email"] == invitee_email
    assert data["role"] == "Reviewer"
    assert "/invite/" in data["invite_url"]


def test_scenario_03_existing_user_accepts_and_joins_another_org(client, admin_token, creator_user, creator_token, test_org, db_session):
    """Scenario 3: Existing user receives invitation, accepts it, and joins another organisation."""
    # Create second organization
    uid = uuid.uuid4().hex[:6]
    second_org = Organization(
        name=f"Second Org {uid}",
        slug=f"second-org-{uid}",
        domain="secondorg.com",
        is_active=True,
    )
    db_session.add(second_org)
    db_session.commit()
    db_session.refresh(second_org)

    # Admin of second org creates invite for creator_user's email
    second_admin = User(
        organization_id=second_org.id,
        email=f"admin_{uid}@secondorg.com",
        hashed_password=hash_password("Pass1234!"),
        full_name="Second Admin",
        role=UserRole.ADMIN.value,
    )
    db_session.add(second_admin)
    db_session.commit()
    db_session.refresh(second_admin)

    mem_admin = OrganizationMembership(
        user_id=second_admin.id,
        organization_id=second_org.id,
        role=UserRole.ADMIN.value,
        status="active",
        joined_at=datetime.now(timezone.utc),
    )
    db_session.add(mem_admin)
    second_org.owner_id = second_admin.id
    db_session.commit()

    second_admin_token = create_access_token(
        subject=second_admin.id,
        extra_claims={"role": second_admin.role, "org_id": second_org.id}
    )

    invite_res = client.post(
        "/api/v1/organizations/current/invitations",
        json={"email": creator_user.email, "role": "Brand Manager", "expires_in_days": 7},
        headers={"Authorization": f"Bearer {second_admin_token}"}
    )
    assert invite_res.status_code == 200
    invite_token = invite_res.json()["invite_token"]

    # Creator user accepts invitation while logged in
    accept_res = client.post(
        "/api/v1/organizations/invitations/accept",
        json={"token": invite_token},
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert accept_res.status_code == 200
    accept_data = accept_res.json()
    assert accept_data["role"] == "Brand Manager"
    assert accept_data["organization"]["id"] == second_org.id
    new_token = accept_data["access_token"]

    # Verify user now has access to second org
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "Brand Manager"
    assert me_res.json()["organization_id"] == second_org.id


def test_scenario_04_new_user_registers_through_invitation(client, admin_token, test_org):
    """Scenario 4: New user registers through an invitation (no new org created)."""
    uid = uuid.uuid4().hex[:6]
    invited_email = f"newuser_{uid}@external.com"

    invite_res = client.post(
        "/api/v1/organizations/current/invitations",
        json={"email": invited_email, "role": "Reviewer", "expires_in_days": 7},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert invite_res.status_code == 200
    token = invite_res.json()["invite_token"]

    # Public verify check
    verify_res = client.get(f"/api/v1/organizations/invitations/verify?token={token}")
    assert verify_res.status_code == 200
    assert verify_res.json()["valid"] is True
    assert verify_res.json()["organization_name"] == test_org.name

    # Register via invitation
    reg_payload = {
        "email": invited_email,
        "password": "SecurePassword2026!",
        "full_name": "Invited Reviewer",
        "invite_token": token,
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert reg_data["user"]["organization_id"] == test_org.id
    assert reg_data["user"]["role"] == "Reviewer"


def test_scenario_05_06_07_multi_org_roles_and_switching(client, creator_user, creator_token, test_org, db_session):
    """
    Scenarios 5, 6 & 7:
    - One user belongs to two organisations.
    - User has different roles in each organisation.
    - User switches between organisations.
    """
    uid = uuid.uuid4().hex[:6]
    # Org 2
    org2 = Organization(name=f"Beta Corp {uid}", slug=f"beta-corp-{uid}", is_active=True)
    db_session.add(org2)
    db_session.flush()

    # Creator user is "Creator" in test_org, and "Brand Manager" in org2
    mem2 = OrganizationMembership(
        user_id=creator_user.id,
        organization_id=org2.id,
        role="Brand Manager",
        status="active",
        joined_at=datetime.now(timezone.utc),
    )
    db_session.add(mem2)
    db_session.commit()

    # 1. List user's organizations
    list_res = client.get("/api/v1/organizations/my-organizations", headers={"Authorization": f"Bearer {creator_token}"})
    assert list_res.status_code == 200
    orgs = list_res.json()
    assert len(orgs) >= 2
    org1_entry = next(o for o in orgs if o["id"] == test_org.id)
    org2_entry = next(o for o in orgs if o["id"] == org2.id)
    assert org1_entry["role"] == "Creator"
    assert org2_entry["role"] == "Brand Manager"

    # 2. Switch to org2
    switch_res = client.post(
        "/api/v1/organizations/switch",
        json={"organization_id": org2.id},
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert switch_res.status_code == 200
    switch_data = switch_res.json()
    assert switch_data["role"] == "Brand Manager"
    assert switch_data["organization"]["id"] == org2.id
    token_org2 = switch_data["access_token"]

    # 3. Verify role is Brand Manager in org2 context
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_org2}"})
    assert me_res.json()["role"] == "Brand Manager"
    assert me_res.json()["organization_id"] == org2.id


def test_scenario_09_ordinary_creator_cannot_invite_or_change_roles(client, creator_token):
    """Scenario 9: Ordinary Creator cannot invite users or change roles."""
    # 1. Creator attempts to invite member -> 403
    invite_res = client.post(
        "/api/v1/organizations/current/invitations",
        json={"email": "attempt@test.com", "role": "Creator"},
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert invite_res.status_code == 403
    assert "lacks permission" in invite_res.json()["detail"]

    # 2. Creator attempts to update another member's role -> 403
    fake_mem_id = str(uuid.uuid4())
    update_res = client.put(
        f"/api/v1/organizations/current/members/{fake_mem_id}",
        json={"role": "Admin"},
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert update_res.status_code == 403


def test_scenario_10_invitation_expires(client, admin_token, test_org, db_session):
    """Scenario 10: Invitation expires after expiration timestamp."""
    uid = uuid.uuid4().hex[:6]
    raw_token = f"exp_token_{uid}"
    thash = hash_invitation_token(raw_token)
    past_time = datetime.now(timezone.utc) - timedelta(days=2)

    inv = OrganizationInvitation(
        organization_id=test_org.id,
        invited_email=f"expired_{uid}@example.com",
        assigned_role="Reviewer",
        token_hash=thash,
        expires_at=past_time,
        status="pending",
    )
    db_session.add(inv)
    db_session.commit()

    # Verify endpoint rejects expired token
    verify_res = client.get(f"/api/v1/organizations/invitations/verify?token={raw_token}")
    assert verify_res.status_code == 400
    assert "expired" in verify_res.json()["detail"].lower()


def test_scenario_11_invitation_revoked(client, admin_token, test_org):
    """Scenario 11: Invitation is revoked by admin."""
    # Admin creates invite
    invite_res = client.post(
        "/api/v1/organizations/current/invitations",
        json={"email": f"torevoke_{uuid.uuid4().hex[:6]}@example.com", "role": "Creator"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert invite_res.status_code == 200
    raw_token = invite_res.json()["invite_token"]

    # Get invitation ID from list
    list_res = client.get("/api/v1/organizations/current/invitations", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_res.status_code == 200
    inv_id = list_res.json()[0]["id"]

    # Admin revokes it
    del_res = client.delete(f"/api/v1/organizations/current/invitations/{inv_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert del_res.status_code == 200

    # Verify endpoint rejects revoked token
    verify_res = client.get(f"/api/v1/organizations/invitations/verify?token={raw_token}")
    assert verify_res.status_code == 400
    assert "no longer valid" in verify_res.json()["detail"].lower()


def test_scenario_12_invitation_cannot_be_reused(client, admin_token, test_org):
    """Scenario 12: Invitation cannot be reused after acceptance."""
    uid = uuid.uuid4().hex[:6]
    invited_email = f"onetime_{uid}@test.com"

    invite_res = client.post(
        "/api/v1/organizations/current/invitations",
        json={"email": invited_email, "role": "Creator"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert invite_res.status_code == 200
    token = invite_res.json()["invite_token"]

    # First user registers with invite
    reg1 = client.post("/api/v1/auth/register", json={
        "email": invited_email,
        "password": "Password1234!",
        "full_name": "First User",
        "invite_token": token,
    })
    assert reg1.status_code == 200

    # Second user attempts to reuse invite -> 400
    reg2 = client.post("/api/v1/auth/register", json={
        "email": f"attacker_{uid}@test.com",
        "password": "Password1234!",
        "full_name": "Attacker",
        "invite_token": token,
    })
    assert reg2.status_code == 400
    assert "already been used" in reg2.json()["detail"].lower()


def test_scenario_13_user_cannot_access_other_org_reviews(client, admin_token, test_org, db_session):
    """Scenario 13: User cannot access another organisation's reviews."""
    uid = uuid.uuid4().hex[:6]
    other_org = Organization(name=f"Other Org {uid}", slug=f"other-org-{uid}", is_active=True)
    db_session.add(other_org)
    db_session.flush()

    other_doc = Document(
        organization_id=other_org.id,
        title="Confidential Other Document",
        filename="confidential.txt",
        file_type="text/plain",
        file_path="confidential.txt",
        file_size=120,
    )
    db_session.add(other_doc)
    db_session.flush()

    other_review = Review(
        organization_id=other_org.id,
        document_id=other_doc.id,
        title="Confidential Other Review",
        status="Needs Review",
    )
    db_session.add(other_review)
    db_session.commit()

    # User in test_org queries other_org's review -> 404
    res = client.get(f"/api/v1/reviews/{other_review.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 404


def test_scenario_14_user_cannot_access_other_org_evidence(client, admin_token, db_session):
    """Scenario 14: User cannot access another organisation's evidence."""
    uid = uuid.uuid4().hex[:6]
    other_org = Organization(name=f"Isolated Org {uid}", slug=f"iso-org-{uid}", is_active=True)
    db_session.add(other_org)
    db_session.flush()

    other_evidence = Evidence(
        organization_id=other_org.id,
        title="Proprietary Clinical Trial Evidence",
        filename="trials.pdf",
        file_type="application/pdf",
        file_extension=".pdf",
        file_path="trials.pdf",
        file_size=5000,
        status="Validated",
    )
    db_session.add(other_evidence)
    db_session.commit()

    # User in test_org queries other_org's evidence -> 404
    res = client.get(f"/api/v1/evidence/{other_evidence.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 404


def test_scenario_15_user_cannot_access_other_org_facts_or_guidelines(client, admin_token, db_session):
    """Scenario 15: User cannot access another organisation's facts or guidelines."""
    uid = uuid.uuid4().hex[:6]
    other_org = Organization(name=f"Secret Org {uid}", slug=f"sec-org-{uid}", is_active=True)
    db_session.add(other_org)
    db_session.flush()

    other_fact = Fact(
        organization_id=other_org.id,
        title="Unannounced Acquisition SLA",
        canonical_value="Secret Project Acquisition Agreement",
        source_reference="SEC Filing 2026-X",
    )
    other_guideline = Guideline(
        organization_id=other_org.id,
        category="Competitive",
        title="Secret Positioning Guideline",
        description="Confidential competitive positioning guidelines.",
    )
    db_session.add(other_fact)
    db_session.add(other_guideline)
    db_session.commit()

    # Query fact -> 404
    res_f = client.get(f"/api/v1/facts/{other_fact.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_f.status_code == 404

    # Query guideline -> 404
    res_g = client.get(f"/api/v1/guidelines/{other_guideline.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_g.status_code == 404


def test_scenario_16_user_cannot_access_other_org_reports(client, admin_token, db_session):
    """Scenario 16: User cannot access another organisation's reports."""
    uid = uuid.uuid4().hex[:6]
    other_org = Organization(name=f"External Org {uid}", slug=f"ext-org-{uid}", is_active=True)
    db_session.add(other_org)
    db_session.flush()

    other_doc = Document(
        organization_id=other_org.id,
        title="Financial Report",
        filename="report.md",
        file_type="text/markdown",
        file_path="report.md",
        file_size=200,
    )
    db_session.add(other_doc)
    db_session.flush()

    other_review = Review(
        organization_id=other_org.id,
        document_id=other_doc.id,
        title="Q3 Audit Report",
        status="Approved",
    )
    db_session.add(other_review)
    db_session.commit()

    # User attempts to download report of another org's review -> 404
    res = client.get(f"/api/v1/reviews/{other_review.id}/report", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 404


def test_scenario_17_switching_cannot_bypass_backend_authorization(client, creator_user, creator_token, db_session):
    """Scenario 17: Organisation switching cannot bypass backend authorisation (spoofed org ID rejected)."""
    uid = uuid.uuid4().hex[:6]
    target_org = Organization(name=f"Protected Org {uid}", slug=f"prot-org-{uid}", is_active=True)
    db_session.add(target_org)
    db_session.commit()

    # 1. Switch endpoint directly rejects unauthorized org ID -> 403
    switch_res = client.post(
        "/api/v1/organizations/switch",
        json={"organization_id": target_org.id},
        headers={"Authorization": f"Bearer {creator_token}"}
    )
    assert switch_res.status_code == 403

    # 2. Passing spoofed X-Organization-Id header on arbitrary endpoints -> 403
    spoofed_res = client.get(
        "/api/v1/reviews",
        headers={
            "Authorization": f"Bearer {creator_token}",
            "X-Organization-Id": target_org.id,
        }
    )
    assert spoofed_res.status_code == 403
    assert "access denied" in spoofed_res.json()["detail"].lower()


def test_scenario_18_existing_users_remain_intact_with_memberships(client, admin_user, admin_token, test_org, db_session):
    """Scenario 18: Existing users and their data remain intact with valid memberships."""
    # Admin profile retrieved seamlessly
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["id"] == admin_user.id
    assert res.json()["email"] == admin_user.email
    assert res.json()["organization_id"] == test_org.id

    # Verify membership exists in DB
    mem = db_session.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == admin_user.id,
        OrganizationMembership.organization_id == test_org.id
    ).first()
    assert mem is not None
    assert mem.status == "active"
