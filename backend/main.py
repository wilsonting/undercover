"""The UnderCover backend."""

import json
import logging
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException

from agent.main import run as run_agent
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
    PaymentRequest,
    Plan,
    Policy,
    PolicyWording,
    SignOff,
    SignOffRequest,
    StartRequest,
    Status,
    Step,
    StepRequest,
)

INSTRUCTIONS = Path(__file__).resolve().parent / "instructions.md"
logger = logging.getLogger("uvicorn.error")


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


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def refuse(message: str) -> HTTPException:
    return HTTPException(409, message)


def require_status(claim: Claim, status: Status) -> None:
    if claim.status != status:
        label = claim.status.replace("_", " ")
        raise refuse(
            f"Claim {claim.claim_id} is {label}, not {status.replace('_', ' ')}"
        )


def set_status(db: sqlite3.Connection, claim_id: str, status: Status) -> None:
    db.execute("UPDATE claims SET status = ? WHERE claim_id = ?", (status, claim_id))


def pay(db: sqlite3.Connection, claim: Claim, amount: float) -> None:
    """Record a payment, unless the rules say the claim can't be paid yet."""
    decision = claim.decision
    if decision is None or decision.decision != "approve":
        raise refuse("Only an approved claim can be paid")
    if claim.payment:
        raise refuse(f"Claim {claim.claim_id} has already been paid")
    if round(amount, 2) != round(decision.payout, 2):
        raise refuse(
            f"The payment must be the approved payout of ${decision.payout:,.2f}"
        )
    if claim.needs_sign_off and claim.sign_off is None:
        limit = setting(db, "payout_approval_limit")
        raise refuse(
            f"A payout over ${limit:,.2f} needs a handler's sign-off before it is paid"
        )
    db.execute(
        "INSERT INTO payments (claim_id, amount, paid_at) VALUES (?, ?, ?)",
        (claim.claim_id, round(amount, 2), now()),
    )


@app.post("/api/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str, body: StartRequest, db: Db) -> Claim:
    """Move a waiting claim into progress for a run of the agent."""
    require_status(load_claim(db, claim_id), "waiting")
    db.execute(
        "UPDATE claims SET status = 'in_progress', thread_id = ? WHERE claim_id = ?",
        (body.thread_id, claim_id),
    )
    return load_claim(db, claim_id)


@app.post("/api/claims/{claim_id}/steps", operation_id="add_step")
def add_step(claim_id: str, body: StepRequest, db: Db) -> Step:
    """Record one step of the agent's run on a claim."""
    claim_row(db, claim_id)
    created_at = now()
    cursor = db.execute(
        "INSERT INTO steps (claim_id, thread_id, kind, content, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (claim_id, body.thread_id, body.kind, body.content, created_at),
    )
    return Step(
        **body.model_dump(), step_id=cursor.lastrowid or 0, created_at=created_at
    )


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str, db: Db) -> list[Step]:
    """List the steps of the agent's latest run on a claim, in order."""
    row = claim_row(db, claim_id)
    rows = db.execute(
        "SELECT step_id, thread_id, kind, content, created_at FROM steps"
        " WHERE claim_id = ? AND thread_id = ? ORDER BY step_id",
        (claim_id, row["thread_id"]),
    ).fetchall()
    return [Step(**row) for row in rows]


@app.post("/api/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, body: Decision, db: Db) -> Claim:
    """Record the agent's decision on a claim in progress."""
    require_status(load_claim(db, claim_id), "in_progress")
    db.execute(
        "UPDATE claims SET decision = ?, decided_at = ? WHERE claim_id = ?",
        (body.model_dump_json(), now(), claim_id),
    )
    claim = load_claim(db, claim_id)
    set_status(db, claim_id, "awaiting_sign_off" if claim.needs_sign_off else "decided")
    return load_claim(db, claim_id)


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, body: PaymentRequest, db: Db) -> Claim:
    """Pay an approved claim its payout, once any sign-off it needs is given."""
    pay(db, load_claim(db, claim_id), body.amount)
    return load_claim(db, claim_id)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, body: SignOffRequest, db: Db) -> Claim:
    """Sign off a claim's payout as a handler, which makes the held payment."""
    claim = load_claim(db, claim_id)
    require_status(claim, "awaiting_sign_off")
    handler = record(db, "handlers", "handler_id", body.handler_id)
    if not handler["can_approve_over_limit"]:
        raise HTTPException(403, f"{handler['name']} can't sign off this payout")
    db.execute(
        "UPDATE claims SET status = 'decided', signed_off_by = ?, signed_off_at = ?"
        " WHERE claim_id = ?",
        (body.handler_id, now(), claim_id),
    )
    claim = load_claim(db, claim_id)
    pay(db, claim, claim.decision.payout if claim.decision else 0)
    return load_claim(db, claim_id)


@app.post("/api/claims/{claim_id}/release", operation_id="release_claim")
def release_claim(claim_id: str, db: Db) -> Claim:
    """Put a claim in progress back in the queue after a run that failed."""
    require_status(load_claim(db, claim_id), "in_progress")
    set_status(db, claim_id, "waiting")
    return load_claim(db, claim_id)


def work_queue(claim_ids: list[str]) -> None:
    """Run the agent on each claim in turn. A failed run has already been recorded
    on its claim, so log it and go on to the next."""
    for claim_id in claim_ids:
        try:
            run_agent(claim_id, str(uuid4()))
        except Exception:
            logger.exception("The agent's run on %s failed", claim_id)


@app.post("/api/claims/{claim_id}/run", operation_id="run_claim")
def run_claim(claim_id: str, background: BackgroundTasks, db: Db) -> Claim:
    """Start the UnderCover Agent on a waiting claim."""
    claim = load_claim(db, claim_id)
    require_status(claim, "waiting")
    background.add_task(work_queue, [claim_id])
    return claim


@app.post("/api/queue/run", operation_id="run_queue")
def run_queue(background: BackgroundTasks, db: Db) -> list[str]:
    """Start the UnderCover Agent on every waiting claim, one at a time."""
    rows = db.execute(
        "SELECT claim_id FROM claims WHERE status = 'waiting' ORDER BY position"
    ).fetchall()
    claim_ids = [row["claim_id"] for row in rows]
    background.add_task(work_queue, claim_ids)
    return claim_ids
