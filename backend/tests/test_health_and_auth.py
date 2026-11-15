def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "healthy"


def test_auth_login_success(client, admin_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "Pass1234!"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == admin_user.email


def test_auth_login_invalid_password(client, admin_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "WrongPassword!"}
    )
    assert response.status_code == 401


def test_auth_me_endpoint(client, admin_token, admin_user):
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == admin_user.id
    assert data["email"] == admin_user.email
    assert data["role"] == "Admin"


def test_auth_me_unauthorized(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
