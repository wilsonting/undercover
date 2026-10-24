import pytest

from backend import main


@pytest.fixture
def runs(monkeypatch):
    started = []
    monkeypatch.setattr(main, "run_agent", lambda claim_id, _: started.append(claim_id))
    return started


def test_run_claim_starts_the_agent(client, runs):
    response = client.post("/api/claims/CLM-1001/run")
    assert response.status_code == 200
    assert runs == ["CLM-1001"]


def test_run_claim_needs_a_waiting_claim(client, runs):
    client.post("/api/claims/CLM-1001/start", json={"thread_id": "t"})
    assert client.post("/api/claims/CLM-1001/run").status_code == 409
    assert runs == []


def test_run_queue_runs_only_waiting_claims(client, runs):
    client.post("/api/claims/CLM-1001/start", json={"thread_id": "t"})
    claim_ids = client.post("/api/queue/run").json()
    assert len(claim_ids) == 24
    assert "CLM-1001" not in claim_ids
    assert runs == claim_ids


def test_the_queue_carries_on_after_a_failed_run(client, monkeypatch, caplog):
    started = []

    def run_agent(claim_id, _):
        started.append(claim_id)
        if claim_id == "CLM-1001":
            raise RuntimeError("The model is unavailable")

    monkeypatch.setattr(main, "run_agent", run_agent)
    main.work_queue(["CLM-1001", "CLM-1002"])
    assert started == ["CLM-1001", "CLM-1002"]
    assert "The agent's run on CLM-1001 failed" in caplog.text
