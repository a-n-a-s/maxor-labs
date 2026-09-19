from helpers import auth_headers

from conftest import create_ticket


def test_alice_cannot_read_bobs_ticket(client, alice, bob, mock_decision):
    created = create_ticket(client, alice["token"], message="Alice's private issue").json()
    ticket_id = created["id"]

    resp = client.get(f"/tickets/{ticket_id}", headers=auth_headers(bob["token"]))
    assert resp.status_code == 404


def test_bob_cannot_list_alices_tickets(client, alice, bob, mock_decision):
    create_ticket(client, alice["token"], message="Private ticket")

    resp = client.get("/tickets", headers=auth_headers(bob["token"]))
    assert resp.status_code == 200
    assert resp.json()["tickets"] == []


def test_bad_token_rejected(client, alice):
    resp = client.get("/tickets", headers=auth_headers("not.a.valid.jwt"))
    assert resp.status_code == 401