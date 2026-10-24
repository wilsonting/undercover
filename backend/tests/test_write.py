import json

import pytest

from backend import db

CLAIM = "/api/claims/CLM-1001"


def decision(kind="approve", payout=420.0):
    return {
        "decision": kind,
        "payout": payout,
        "calculation": "Hotel $245.00 + meals $95.00 + taxis $80.00 = $420.00",
        "reason": "The flight was canceled for a crew problem. The costs are covered.",
        "policy_section": "Section 3, Trip Delay",
    }


def start(client, path=CLAIM):
    response = client.post(f"{path}/start", json={"thread_id": "thread-1"})
    assert response.status_code == 200
    return response.json()


def decide(client, kind="approve", payout=420.0, path=CLAIM):
    start(client, path)
    response = client.post(f"{path}/decision", json=decision(kind, payout))
    assert response.status_code == 200
    return response.json()


def test_start_moves_a_waiting_claim_into_progress(client):
    claim = start(client)
    assert claim["status"] == "in_progress"
    assert claim["thread_id"] == "thread-1"


def test_start_refuses_a_claim_in_progress(client):
    start(client)
    response = client.post(f"{CLAIM}/start", json={"thread_id": "thread-2"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 is in progress, not waiting"


def test_steps_of_the_latest_run(client):
    start(client)
    for kind, content in [("tool_call", "get_claim"), ("thinking", "Covered")]:
        body = {"thread_id": "thread-1", "kind": kind, "content": content}
        assert client.post(f"{CLAIM}/steps", json=body).status_code == 200
    old = {"thread_id": "thread-0", "kind": "error", "content": "An older run"}
    client.post(f"{CLAIM}/steps", json=old)
    steps = client.get(f"{CLAIM}/steps").json()
    assert [s["content"] for s in steps] == ["get_claim", "Covered"]
    assert steps[0]["step_id"] < steps[1]["step_id"]


def test_step_on_an_unknown_claim(client):
    body = {"thread_id": "t", "kind": "thinking", "content": "x"}
    assert client.post("/api/claims/CLM-9999/steps", json=body).status_code == 404


@pytest.mark.parametrize("kind", ["decline", "refer"])
def test_decline_and_refer_are_decided_with_no_payout(client, kind):
    claim = decide(client, kind, 0)
    assert claim["status"] == "decided"
    assert claim["decision"]["decision"] == kind
    assert claim["decision"]["payout"] == 0
    assert claim["decided_at"]


def test_approve_within_the_limit_is_decided(client):
    claim = decide(client, "approve", 420.0)
    assert claim["status"] == "decided"
    assert claim["needs_sign_off"] is False
    summary = client.get("/api/claims").json()[0]
    assert (summary["decision"], summary["payout"]) == ("approve", 420.0)


def test_approve_over_the_limit_waits_for_sign_off(client):
    claim = decide(client, "approve", 1350.0)
    assert claim["status"] == "awaiting_sign_off"
    assert claim["needs_sign_off"] is True


def test_pay_an_approved_claim(client):
    decide(client, "approve", 420.0)
    response = client.post(f"{CLAIM}/payment", json={"amount": 420.0})
    assert response.status_code == 200
    assert response.json()["payment"]["amount"] == 420.0


def test_payment_over_the_limit_is_blocked_until_sign_off(client):
    decide(client, "approve", 1350.0)
    response = client.post(f"{CLAIM}/payment", json={"amount": 1350.0})
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "A payout over $1,000.00 needs a handler's sign-off before it is paid"
    )
    claim = client.get(CLAIM).json()
    assert claim["payment"] is None
    assert claim["status"] == "awaiting_sign_off"


def test_sign_off_makes_the_held_payment(client):
    decide(client, "approve", 1350.0)
    response = client.post(f"{CLAIM}/sign-off", json={"handler_id": "HND-01"})
    assert response.status_code == 200
    claim = response.json()
    assert claim["status"] == "decided"
    assert claim["sign_off"]["handler_name"] == "Dana Whitfield"
    assert claim["payment"]["amount"] == 1350.0
    again = client.post(f"{CLAIM}/payment", json={"amount": 1350.0})
    assert again.status_code == 409


def test_payment_refusals(client):
    decide(client, "approve", 420.0)
    wrong = client.post(f"{CLAIM}/payment", json={"amount": 400.0})
    assert wrong.status_code == 409
    assert (
        wrong.json()["detail"] == "The payment must be the approved payout of $420.00"
    )
    assert client.post(f"{CLAIM}/payment", json={"amount": 420.0}).status_code == 200
    twice = client.post(f"{CLAIM}/payment", json={"amount": 420.0})
    assert twice.json()["detail"] == "Claim CLM-1001 has already been paid"


def test_a_declined_claim_cannot_be_paid(client):
    decide(client, "decline", 0)
    response = client.post(f"{CLAIM}/payment", json={"amount": 420.0})
    assert response.status_code == 409
    assert response.json()["detail"] == "Only an approved claim can be paid"


def test_a_waiting_claim_cannot_be_paid(client):
    response = client.post(f"{CLAIM}/payment", json={"amount": 420.0})
    assert response.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        decision("maybe", 0),
        decision("approve", -5),
        decision("decline", 100),
        {"decision": "approve", "payout": 420.0},
    ],
)
def test_invalid_decisions(client, body):
    start(client)
    assert client.post(f"{CLAIM}/decision", json=body).status_code == 422


def test_decision_needs_a_claim_in_progress(client):
    response = client.post(f"{CLAIM}/decision", json=decision())
    assert response.status_code == 409
    decide(client)
    assert client.post(f"{CLAIM}/decision", json=decision()).status_code == 409


def test_sign_off_needs_a_claim_awaiting_sign_off(client):
    decide(client, "approve", 420.0)
    response = client.post(f"{CLAIM}/sign-off", json={"handler_id": "HND-01"})
    assert response.status_code == 409


def test_sign_off_by_an_unknown_handler(client):
    decide(client, "approve", 1350.0)
    response = client.post(f"{CLAIM}/sign-off", json={"handler_id": "HND-99"})
    assert response.status_code == 404
    assert client.get(CLAIM).json()["status"] == "awaiting_sign_off"


def test_sign_off_by_a_handler_without_authority(client):
    with db.connect() as connection:
        handler = db.load("handlers.json")[2]
        handler["can_approve_over_limit"] = False
        connection.execute(
            "UPDATE handlers SET data = ? WHERE handler_id = 'HND-03'",
            (json.dumps(handler),),
        )
    decide(client, "approve", 1350.0)
    response = client.post(f"{CLAIM}/sign-off", json={"handler_id": "HND-03"})
    assert response.status_code == 403
    assert client.get(CLAIM).json()["payment"] is None


def test_release_puts_a_claim_back_in_the_queue(client):
    start(client)
    claim = client.post(f"{CLAIM}/release").json()
    assert claim["status"] == "waiting"
    assert claim["thread_id"] == "thread-1"
    assert client.post(f"{CLAIM}/release").status_code == 409
