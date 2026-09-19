def register_and_login(client, email="alice@test.com", password="secret123"):
    resp = client.post("/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    login = client.post("/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}