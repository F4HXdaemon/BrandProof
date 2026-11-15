import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, get_db
from app.main import app
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.core.security import hash_password, create_access_token

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_org(db_session):
    uid = uuid.uuid4().hex[:8]
    org = Organization(
        name=f"Test Governance Org {uid}",
        slug=f"test-gov-org-{uid}",
        domain=f"testorg-{uid}.com"
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def admin_user(db_session, test_org):
    uid = uuid.uuid4().hex[:8]
    user = User(
        organization_id=test_org.id,
        email=f"admin-{uid}@testorg.com",
        hashed_password=hash_password("Pass1234!"),
        full_name="Admin Test",
        role=UserRole.ADMIN.value
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def creator_user(db_session, test_org):
    uid = uuid.uuid4().hex[:8]
    user = User(
        organization_id=test_org.id,
        email=f"creator-{uid}@testorg.com",
        hashed_password=hash_password("Pass1234!"),
        full_name="Creator Test",
        role=UserRole.CREATOR.value
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def reviewer_user(db_session, test_org):
    uid = uuid.uuid4().hex[:8]
    user = User(
        organization_id=test_org.id,
        email=f"reviewer-{uid}@testorg.com",
        hashed_password=hash_password("Pass1234!"),
        full_name="Reviewer Test",
        role=UserRole.REVIEWER.value
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    return create_access_token(
        subject=admin_user.id,
        extra_claims={"role": admin_user.role, "org_id": admin_user.organization_id}
    )


@pytest.fixture
def creator_token(creator_user):
    return create_access_token(
        subject=creator_user.id,
        extra_claims={"role": creator_user.role, "org_id": creator_user.organization_id}
    )


@pytest.fixture
def reviewer_token(reviewer_user):
    return create_access_token(
        subject=reviewer_user.id,
        extra_claims={"role": reviewer_user.role, "org_id": reviewer_user.organization_id}
    )
