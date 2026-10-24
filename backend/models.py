"""The API's request and response bodies."""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

Status = Literal["waiting", "in_progress", "awaiting_sign_off", "decided"]
DecisionKind = Literal["approve", "decline", "refer"]
StepKind = Literal["thinking", "tool_call", "tool_result", "error"]


class Item(BaseModel):
    description: str
    category: str
    amount: float


class Document(BaseModel):
    name: str
    type: str
    content: str


class Decision(BaseModel):
    decision: DecisionKind
    payout: float = Field(ge=0)
    calculation: str
    reason: str
    policy_section: str

    @model_validator(mode="after")
    def payout_only_on_approve(self) -> Self:
        if self.decision != "approve" and self.payout != 0:
            raise ValueError("Only an approve decision has a payout")
        return self


class SignOff(BaseModel):
    handler_id: str
    handler_name: str
    signed_off_at: str


class Payment(BaseModel):
    amount: float
    paid_at: str


class ClaimSummary(BaseModel):
    claim_id: str
    customer_name: str
    claim_type: str
    amount_claimed: float
    submitted_on: str
    status: Status
    decision: DecisionKind | None
    payout: float | None


class Claim(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str
    customer_name: str
    claim_type: str
    submitted_on: str
    incident_date: str
    incident_location: str
    summary: str
    story: str
    items: list[Item]
    amount_claimed: float
    documents: list[Document]
    status: Status
    thread_id: str | None
    decision: Decision | None
    decided_at: str | None
    needs_sign_off: bool
    sign_off: SignOff | None
    payment: Payment | None


class Plan(BaseModel):
    plan: str
    name: str
    trip_cancellation_max: float
    trip_delay_waiting_hours: int
    trip_delay_max: float
    baggage_delay_waiting_hours: int
    baggage_delay_max: float
    baggage_max: float
    per_item_limit: float
    passport_max: float
    emergency_medical_max: float
    deductible: float
    deductible_applies_to: list[str]


class AddOn(BaseModel):
    add_on: str
    name: str
    effect: str
    electronics_per_item_limit: float | None = None


class Trip(BaseModel):
    destination: str
    departs_on: str
    returns_on: str
    trip_cost: float


class Policy(BaseModel):
    policy_id: str
    customer_id: str
    plan: Plan
    add_ons: list[AddOn]
    purchased_on: str
    sold_through: str
    trip: Trip
    travelers: list[str]
    status: str


class PreviousClaim(BaseModel):
    claim_id: str
    filed_on: str
    incident_date: str
    claim_type: str
    summary: str
    outcome: str
    amount_paid: float


class ClaimHistory(BaseModel):
    customer_id: str
    name: str
    customer_since: str
    previous_claims: list[PreviousClaim]


class Handler(BaseModel):
    handler_id: str
    name: str
    role: str
    can_approve_over_limit: bool


class Instructions(BaseModel):
    instructions: str


class PolicyWording(BaseModel):
    version: str
    text: str


class StartRequest(BaseModel):
    thread_id: str


class StepRequest(BaseModel):
    thread_id: str
    kind: StepKind
    content: str


class Step(StepRequest):
    step_id: int
    created_at: str


class PaymentRequest(BaseModel):
    amount: float = Field(gt=0)


class SignOffRequest(BaseModel):
    handler_id: str
