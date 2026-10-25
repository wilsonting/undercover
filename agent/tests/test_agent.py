import runpy

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend.main import app

CLAIM = "/api/claims/CLM-1001"


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


class BrokenModel(StubModel):
    """A chat model that fails as soon as it is called."""

    def _generate(self, *args, **kwargs):
        raise RuntimeError("The model is unavailable")


def calls(*tool_calls):
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": f"{name}-{i}"}
            for i, (name, args) in enumerate(tool_calls)
        ],
    )


def stub(*replies):
    return StubModel(messages=iter(replies))


def decision(payout):
    return {
        "decision": "approve",
        "payout": payout,
        "calculation": "Hotel $245.00 + meals $95.00 + taxis $80.00",
        "reason": "The airline canceled the flight for a crew problem.",
        "policy_section": "Section 3, Trip Delay",
    }


def reading():
    return calls(
        ("get_claim", {"claim_id": "CLM-1001"}),
        ("get_policy", {"policy_id": "POL-2001"}),
        ("get_claim_history", {"customer_id": "CUS-3001"}),
    )


@pytest.fixture
def backend(client, monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    return client


def test_a_full_run_decides_and_pays(backend):
    model = stub(
        reading(),
        calls(("record_decision", decision(420.0))),
        calls(("pay_claim", {"amount": 420.0})),
        AIMessage(content="Approved and paid $420.00."),
    )
    assert main.run("CLM-1001", "thread-1", model) == "Approved and paid $420.00."
    claim = backend.get(CLAIM).json()
    assert claim["status"] == "decided"
    assert claim["decision"]["policy_section"] == "Section 3, Trip Delay"
    assert claim["payment"]["amount"] == 420.0
    steps = backend.get(f"{CLAIM}/steps").json()
    assert [s["kind"] for s in steps] == [
        *["tool_call"] * 3,
        *["tool_result"] * 3,
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "thinking",
    ]
    assert steps[0]["content"] == 'get_claim {"claim_id": "CLM-1001"}'
    results = {s["content"].split(":")[0] for s in steps[3:6]}
    assert results == {"get_claim", "get_policy", "get_claim_history"}
    assert {s["thread_id"] for s in steps} == {"thread-1"}


def test_the_backend_blocks_paying_over_the_limit(backend):
    model = stub(
        reading(),
        calls(("record_decision", decision(1350.0))),
        calls(("pay_claim", {"amount": 1350.0})),
        AIMessage(content="Approved, waiting for sign-off."),
    )
    main.run("CLM-1001", "thread-1", model)
    claim = backend.get(CLAIM).json()
    assert claim["status"] == "awaiting_sign_off"
    assert claim["payment"] is None
    refusal = backend.get(f"{CLAIM}/steps").json()[-2]["content"]
    assert refusal.startswith("pay_claim: Refused (409)")
    assert "needs a handler's sign-off" in refusal


def test_a_run_without_a_decision_goes_back_to_the_queue(backend):
    main.run("CLM-1001", "thread-1", stub(AIMessage(content="I am not sure.")))
    assert backend.get(CLAIM).json()["status"] == "waiting"
    last = backend.get(f"{CLAIM}/steps").json()[-1]
    assert last == {
        **last,
        "kind": "error",
        "content": "The agent finished without recording a decision.",
    }


def test_a_failed_run_goes_back_to_the_queue(backend):
    with pytest.raises(RuntimeError):
        main.run("CLM-1001", "thread-1", BrokenModel(messages=iter([])))
    assert backend.get(CLAIM).json()["status"] == "waiting"
    last = backend.get(f"{CLAIM}/steps").json()[-1]
    assert last["kind"] == "error"
    assert "The model is unavailable" in last["content"]


def test_a_run_needs_a_waiting_claim(backend):
    backend.post(f"{CLAIM}/start", json={"thread_id": "other"})
    with pytest.raises(Exception, match="409"):
        main.run("CLM-1001", "thread-1", stub())
    assert backend.get(CLAIM).json()["thread_id"] == "other"


def test_the_system_prompt_comes_from_the_api(backend):
    prompt = main.system_prompt()
    assert prompt.startswith("# The UnderCover Agent")
    assert "## 10. How we work out your payment" in prompt


def test_tools_report_refusals(backend):
    assert main.get_claim.invoke({"claim_id": "CLM-9999"}).startswith("Refused (404)")


def test_the_command_line(monkeypatch, capsys):
    monkeypatch.setattr(main, "run", lambda claim_id, thread_id: f"Decided {claim_id}")
    monkeypatch.setattr("sys.argv", ["agent", "CLM-1001"])
    runpy.run_module("agent", run_name="__main__")
    assert capsys.readouterr().out == "Decided CLM-1001\n"


@pytest.mark.parametrize("args", [[], ["CLM-1001", "CLM-1002"]])
def test_the_command_line_needs_one_claim_id(monkeypatch, args):
    monkeypatch.setattr(main, "run", lambda claim_id, thread_id: "Should not run")
    monkeypatch.setattr("sys.argv", ["agent", *args])
    with pytest.raises(SystemExit, match="Usage: uv run -m agent <claim id>"):
        runpy.run_module("agent", run_name="__main__")


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
