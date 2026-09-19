def test_register_creates_user(client):
    resp = client.post("/register", json={"email": "new@test.com", "password": "secret123"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@test.com"
    assert "id" in body


def test_register_duplicate_email_conflict(client):
    client.post("/register", json={"email": "dup@test.com", "password": "secret123"})
    resp = client.post("/register", json={"email": "dup@test.com", "password": "secret123"})
    assert resp.status_code == 409


def test_register_invalid_email(client):
    resp = client.post("/register", json={"email": "not-an-email", "password": "secret123"})
    assert resp.status_code == 422


def test_login_returns_jwt(client):
    from helpers import register_and_login

    token = register_and_login(client, "login@test.com")
    assert token.count(".") == 2


def test_login_wrong_password_rejected(client):
    client.post("/register", json={"email": "pass@test.com", "password": "secret123"})
    resp = client.post("/login", json={"email": "pass@test.com", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_unknown_email_rejected(client):
    resp = client.post("/login", json={"email": "ghost@test.com", "password": "x" * 8})
    assert resp.status_code == 401


def test_me_requires_token(client):
    assert client.get("/me").status_code == 401


def test_me_returns_authenticated_user(client, alice):
    resp = client.get("/me", headers={"Authorization": f"Bearer {alice['token']}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@test.com"