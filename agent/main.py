"""The UnderCover Agent."""

import json
import os
from collections.abc import Iterator
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend and return its reply, or why it refused."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_error:
        return f"Refused ({response.status_code}): {response.text}"
    return response.text


@tool
def get_claim(claim_id: str) -> str:
    """Read a claim: the customer's story, the items claimed and the documents."""
    return call("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> str:
    """Read a policy: its plan's limits, its add-ons, the trip and the travelers."""
    return call("GET", f"/api/policies/{policy_id}")


@tool
def get_claim_history(customer_id: str) -> str:
    """Read a customer's earlier claims."""
    return call("GET", f"/api/customers/{customer_id}/claim-history")


def claim_tools(claim_id: str) -> list[BaseTool]:
    """The tools that act on the claim being decided, and on no other."""

    @tool
    def record_decision(
        decision: Literal["approve", "decline", "refer"],
        payout: float,
        calculation: str,
        reason: str,
        policy_section: str,
    ) -> str:
        """Record your decision on the claim. Call this exactly once."""
        body = {
            "decision": decision,
            "payout": payout,
            "calculation": calculation,
            "reason": reason,
            "policy_section": policy_section,
        }
        return call("POST", f"/api/claims/{claim_id}/decision", body)

    @tool
    def pay_claim(amount: float) -> str:
        """Pay the approved claim its payout."""
        return call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})

    return [get_claim, get_policy, get_claim_history, record_decision, pay_claim]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def system_prompt() -> str:
    """Build the system prompt from the instructions and the policy wording."""
    with backend() as client:
        instructions = client.get("/api/instructions").json()["instructions"]
        wording = client.get("/api/policy-wording").json()["text"]
    return f"{instructions}\n\n{wording}"


def steps(message: BaseMessage) -> Iterator[tuple[str, str]]:
    """Turn one message from the agent into steps for the dashboard."""
    if isinstance(message, ToolMessage):
        yield "tool_result", f"{message.name}: {message.text}"
    elif isinstance(message, AIMessage):
        if message.text:
            yield "thinking", message.text
        for tool_call in message.tool_calls:
            yield "tool_call", f"{tool_call['name']} {json.dumps(tool_call['args'])}"


def post_step(claim_id: str, thread_id: str, kind: str, content: str) -> None:
    body = {"thread_id": thread_id, "kind": kind, "content": content}
    with backend() as client:
        client.post(f"/api/claims/{claim_id}/steps", json=body).raise_for_status()


def work(claim_id: str, thread_id: str, llm: BaseChatModel) -> str:
    """Let the agent decide the claim, posting each step as it goes."""
    agent = create_agent(
        llm, tools=claim_tools(claim_id), system_prompt=system_prompt()
    )
    reply = ""
    for update in agent.stream(
        {"messages": [{"role": "user", "content": f"Please decide claim {claim_id}."}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    ):
        for node in update.values():
            for message in node["messages"]:
                for kind, content in steps(message):
                    post_step(claim_id, thread_id, kind, content)
                if isinstance(message, AIMessage):
                    reply = message.text
    return reply


def undecided(claim_id: str) -> bool:
    with backend() as client:
        return client.get(f"/api/claims/{claim_id}").json()["status"] == "in_progress"


def stop(claim_id: str, thread_id: str, reason: str) -> None:
    """Record why a run stopped, and put the claim back in the queue if undecided."""
    post_step(claim_id, thread_id, "error", reason)
    if undecided(claim_id):
        with backend() as client:
            client.post(f"/api/claims/{claim_id}/release").raise_for_status()


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    with backend() as client:
        response = client.post(
            f"/api/claims/{claim_id}/start", json={"thread_id": thread_id}
        )
        response.raise_for_status()
    try:
        reply = work(claim_id, thread_id, llm or model())
    except Exception as error:
        stop(claim_id, thread_id, f"The run stopped with an error: {error}")
        raise
    if undecided(claim_id):
        stop(claim_id, thread_id, "The agent finished without recording a decision.")
    return reply
