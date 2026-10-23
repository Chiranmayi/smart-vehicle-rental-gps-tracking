
def test_register_user(client):
    response = client.post(
        "/auth/register",
        json={
            "name": "Test User",
            "email": "testuser@example.com",
            "password": "TestPassword123",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Test User"
    assert data["email"] == "testuser@example.com"
    assert data["role"] == "CUSTOMER"
    assert "hashed_password" not in data


def test_duplicate_email_rejected(client):
    payload = {
        "name": "Test User",
        "email": "duplicate@example.com",
        "password": "TestPassword123",
    }

    first = client.post("/auth/register", json=payload)
    second = client.post("/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_login_success(client):
    client.post(
        "/auth/register",
        json={
            "name": "Login User",
            "email": "login@example.com",
            "password": "TestPassword123",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "login@example.com",
            "password": "TestPassword123",
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_wrong_password(client):
    client.post(
        "/auth/register",
        json={
            "name": "Login User",
            "email": "wrongpass@example.com",
            "password": "TestPassword123",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "wrongpass@example.com",
            "password": "WrongPassword123",
        },
    )

    assert response.status_code == 401


def test_profile_requires_authentication(client):
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_profile_with_valid_token(client):
    client.post(
        "/auth/register",
        json={
            "name": "Profile User",
            "email": "profile@example.com",
            "password": "TestPassword123",
        },
    )

    login_response = client.post(
        "/auth/login",
        json={
            "email": "profile@example.com",
            "password": "TestPassword123",
        },
    )

    token = login_response.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "profile@example.com"
