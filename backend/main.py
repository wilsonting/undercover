"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from backend.db import connect, ensure_seeded, setting
from backend.models import (
    AddOn,
    Claim,
    ClaimHistory,
    ClaimSummary,
    Decision,
    Handler,
    Instructions,
    Payment,
    Plan,
    Policy,
    PolicyWording,
    SignOff,
)

INSTRUCTIONS = Path(__file__).resolve().parent / "instructions.md"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    ensure_seeded()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


def get_db() -> Iterator[sqlite3.Connection]:
    with connect() as db:
        yield db


Db = Annotated[sqlite3.Connection, Depends(get_db)]


def record(db: sqlite3.Connection, table: str, key: str, value: str) -> Any:
    """Read one JSON record by its key, or raise a 404."""
    row = db.execute(
        f"SELECT data FROM {table} WHERE {key} = ?",  # noqa: S608
        (value,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No record {value}")
    return json.loads(row["data"])


def claim_row(db: sqlite3.Connection, claim_id: str) -> sqlite3.Row:
    row = db.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"No claim {claim_id}")
    return row


def load_claim(db: sqlite3.Connection, claim_id: str) -> Claim:
    """Build the full claim from its row, its decision, sign-off and payment."""
    row = claim_row(db, claim_id)
    data = json.loads(row["data"])
    customer = record(db, "customers", "customer_id", row["customer_id"])
    decision = (
        Decision.model_validate_json(row["decision"]) if row["decision"] else None
    )
    sign_off = None
    if row["signed_off_by"]:
        handler = record(db, "handlers", "handler_id", row["signed_off_by"])
        sign_off = SignOff(
            handler_id=handler["handler_id"],
            handler_name=handler["name"],
            signed_off_at=row["signed_off_at"],
        )
    payment = db.execute(
        "SELECT amount, paid_at FROM payments WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    limit = setting(db, "payout_approval_limit")
    return Claim(
        **{key: value for key, value in data.items() if key != "status"},
        customer_name=customer["name"],
        status=row["status"],
        thread_id=row["thread_id"],
        decision=decision,
        decided_at=row["decided_at"],
        needs_sign_off=bool(
            decision and decision.decision == "approve" and decision.payout > limit
        ),
        sign_off=sign_off,
        payment=Payment(**payment) if payment else None,
    )


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(db: Db) -> list[ClaimSummary]:
    """List the claims queue with where each claim stands."""
    rows = db.execute(
        "SELECT claims.data, claims.status, claims.decision, customers.data AS customer"
        " FROM claims JOIN customers USING (customer_id) ORDER BY position"
    ).fetchall()
    summaries = []
    for row in rows:
        data = json.loads(row["data"])
        decision = (
            Decision.model_validate_json(row["decision"]) if row["decision"] else None
        )
        summaries.append(
            ClaimSummary(
                claim_id=data["claim_id"],
                customer_name=json.loads(row["customer"])["name"],
                claim_type=data["claim_type"],
                amount_claimed=data["amount_claimed"],
                submitted_on=data["submitted_on"],
                status=row["status"],
                decision=decision.decision if decision else None,
                payout=decision.payout if decision else None,
            )
        )
    return summaries


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, db: Db) -> Claim:
    """Get one claim in full, with its decision, sign-off and payment."""
    return load_claim(db, claim_id)


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, db: Db) -> Policy:
    """Get a policy with its plan's limits and its add-ons."""
    policy = record(db, "policies", "policy_id", policy_id)
    plan = record(db, "plans", "plan", policy["plan"])
    add_ons = [a for a in setting(db, "add_ons") if a["add_on"] in policy["add_ons"]]
    return Policy(
        **{
            **policy,
            "plan": Plan(
                **plan, deductible_applies_to=setting(db, "deductible_applies_to")
            ),
            "add_ons": [AddOn(**a) for a in add_ons],
        }
    )


@app.get("/api/customers/{customer_id}/claim-history", operation_id="get_claim_history")
def get_claim_history(customer_id: str, db: Db) -> ClaimHistory:
    """Get a customer's earlier claims, without their contact details."""
    return ClaimHistory(**record(db, "customers", "customer_id", customer_id))


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(db: Db) -> list[Handler]:
    """List the claims handlers."""
    rows = db.execute("SELECT data FROM handlers ORDER BY handler_id").fetchall()
    return [Handler(**json.loads(row["data"])) for row in rows]


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> Instructions:
    """Get the UnderCover Agent's instructions."""
    return Instructions(instructions=INSTRUCTIONS.read_text(encoding="utf-8"))


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording(db: Db) -> PolicyWording:
    """Get the policy wording that decisions follow."""
    return PolicyWording(**setting(db, "policy_wording"))
