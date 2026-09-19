import pytest

import database

from helpers import auth_headers

FIXED_DECISION = {
    "action": "APPROVE_RETURN",
    "confidence": 0.9,
    "reason": "mocked decision",
    "sources": ["returns.md"],
}


@pytest.fixture
def client(tmp_path_factory):
    import api

    path = str(tmp_path_factory.mktemp("db") / "test.db")
    database.DATABASE_PATH = path
    database.init_db()

    from fastapi.testclient import TestClient

    with TestClient(api.app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh_db_per_test(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", str(tmp_path / "test.db"))
    database.init_db()


@pytest.fixture
def mock_decision(monkeypatch):
    import api

    monkeypatch.setattr(api, "make_decision", lambda ticket: dict(FIXED_DECISION))


def create_ticket(client, token, message="I want to return my unopened non-food item."):
    return client.post(
        "/tickets",
        headers=auth_headers(token),
        json={
            "message": message,
            "order_value_inr": 1200,
            "days_since_delivery": 10,
            "product_type": "non_food",
            "opened_status": "unopened",
            "order_status": "delivered",
        },
    )


@pytest.fixture
def alice(client):
    from helpers import register_and_login

    token = register_and_login(client, "alice@test.com")
    return {"email": "alice@test.com", "token": token}


@pytest.fixture
def bob(client):
    from helpers import register_and_login

    token = register_and_login(client, "bob@test.com")
    return {"email": "bob@test.com", "token": token}