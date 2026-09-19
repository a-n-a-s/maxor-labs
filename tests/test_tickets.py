from helpers import auth_headers

from conftest import create_ticket


def test_create_ticket_requires_token(client):
    resp = client.post(
        "/tickets", json={"message": "I want a refund."}
    )
    assert resp.status_code == 401


def test_create_ticket_generates_decision(client, alice, mock_decision):
    resp = create_ticket(client, alice["token"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["message"].startswith("I want to return")
    assert body["decision"]["action"] == "APPROVE_RETURN"
    assert body["decision"]["sources"] == ["returns.md"]


def test_create_ticket_empty_message_rejected(client, alice):
    resp = client.post(
        "/tickets",
        headers=auth_headers(alice["token"]),
        json={"message": "   "},
    )
    assert resp.status_code == 422


def test_list_tickets_returns_own_tickets(client, alice, mock_decision):
    create_ticket(client, alice["token"], message="First ticket")
    create_ticket(client, alice["token"], message="Second ticket")

    resp = client.get("/tickets", headers=auth_headers(alice["token"]))
    assert resp.status_code == 200
    tickets = resp.json()["tickets"]
    assert len(tickets) == 2
    messages = {t["message"] for t in tickets}
    assert messages == {"First ticket", "Second ticket"}


def test_get_ticket_detail_includes_decision(client, alice, mock_decision):
    created = create_ticket(client, alice["token"]).json()
    ticket_id = created["id"]

    resp = client.get(f"/tickets/{ticket_id}", headers=auth_headers(alice["token"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == ticket_id
    assert body["decision"]["action"] == "APPROVE_RETURN"
    assert body["details"]["product_type"] == "non_food"


def test_get_unknown_ticket_returns_404(client, alice):
    resp = client.get("/tickets/99999", headers=auth_headers(alice["token"]))
    assert resp.status_code == 404