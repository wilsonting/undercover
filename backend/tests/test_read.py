from pathlib import Path

from fastapi.testclient import TestClient

from backend import db
from backend.main import app


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_startup_seeds_a_new_database(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "new.db"))
    with TestClient(app) as client:
        assert len(client.get("/api/claims").json()) == 25


def test_startup_keeps_an_existing_database(client):
    with db.connect() as connection:
        connection.execute("UPDATE claims SET status = 'decided'")
    with TestClient(app) as again:
        assert again.get("/api/claims/CLM-1001").json()["status"] == "decided"


def test_seed_never_reads_the_answer_key(tmp_path, monkeypatch):
    read = []
    original = Path.read_text

    def spy(self, *args, **kwargs):
        read.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", spy)
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "spy.db"))
    with db.connect() as connection:
        db.seed(connection)
    names = {path.name for path in read}
    assert "claims.json" in names
    assert all(path.parent == db.DATA for path in read)
    assert "claims_manual.md" not in names
    assert "knowledge.json" not in names


def test_list_claims(client):
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert claims[0] == {
        "claim_id": "CLM-1001",
        "customer_name": "Maya Patel",
        "claim_type": "trip_delay",
        "amount_claimed": 420.0,
        "submitted_on": "2026-06-24",
        "status": "waiting",
        "decision": None,
        "payout": None,
    }
    assert {claim["status"] for claim in claims} == {"waiting"}


def test_get_claim(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["story"].startswith("My flight home from Rome")
    assert sum(item["amount"] for item in claim["items"]) == 420.0
    assert len(claim["documents"]) == 4
    assert claim["status"] == "waiting"
    assert claim["decision"] is None
    assert claim["needs_sign_off"] is False
    assert claim["payment"] is None


def test_unknown_claim(client):
    assert client.get("/api/claims/CLM-9999").status_code == 404


def test_get_policy(client):
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"]["plan"] == "premium"
    assert policy["plan"]["trip_delay_waiting_hours"] == 6
    assert policy["plan"]["trip_delay_max"] == 800.0
    assert policy["plan"]["deductible"] == 50.0
    assert policy["plan"]["deductible_applies_to"] == ["baggage", "emergency_medical"]
    assert policy["travelers"] == ["Maya Patel"]


def test_policy_lists_its_add_ons(client):
    policies = db.load("policies.json")
    with_add_on = next(p for p in policies if p["add_ons"])
    policy = client.get(f"/api/policies/{with_add_on['policy_id']}").json()
    assert [a["add_on"] for a in policy["add_ons"]] == with_add_on["add_ons"]
    assert all(a["effect"] for a in policy["add_ons"])


def test_unknown_policy(client):
    assert client.get("/api/policies/POL-9999").status_code == 404


def test_claim_history_leaves_out_personal_details(client):
    response = client.get("/api/customers/CUS-3001/claim-history")
    history = response.json()
    assert [c["claim_id"] for c in history["previous_claims"]] == ["CLM-0412"]
    for detail in ("email", "phone", "address", "date_of_birth", "Jersey City"):
        assert detail not in response.text


def test_list_handlers(client):
    names = [h["name"] for h in client.get("/api/handlers").json()]
    assert names == ["Dana Whitfield", "Marcus Oyelaran", "Priya Raman"]


def test_instructions(client):
    instructions = client.get("/api/instructions").json()["instructions"]
    assert instructions.startswith("# The UnderCover Agent")


def test_policy_wording(client):
    wording = client.get("/api/policy-wording").json()
    assert wording["version"] == "2026.1"
    assert "## 10. How we work out your payment" in wording["text"]


def test_every_operation_is_documented_with_no_optional_inputs(client):
    schema = client.get("/openapi.json").json()
    for path in schema["paths"].values():
        for operation in path.values():
            assert operation["operationId"]
            assert operation["description"].count("\n") == 0
            for parameter in operation.get("parameters", []):
                assert parameter["required"]
    schemas = schema["components"]["schemas"]
    for path in schema["paths"].values():
        for operation in path.values():
            if "requestBody" in operation:
                ref = operation["requestBody"]["content"]["application/json"]["schema"]
                model = schemas[ref["$ref"].split("/")[-1]]
                assert set(model["required"]) == set(model["properties"])
