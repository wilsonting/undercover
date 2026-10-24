export type Status =
  "waiting" | "in_progress" | "awaiting_sign_off" | "decided";
export type DecisionKind = "approve" | "decline" | "refer";
export type StepKind = "thinking" | "tool_call" | "tool_result" | "error";

export interface ClaimSummary {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  amount_claimed: number;
  submitted_on: string;
  status: Status;
  decision: DecisionKind | null;
  payout: number | null;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Decision {
  decision: DecisionKind;
  payout: number;
  calculation: string;
  reason: string;
  policy_section: string;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  customer_name: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: Item[];
  amount_claimed: number;
  documents: ClaimDocument[];
  status: Status;
  thread_id: string | null;
  decision: Decision | null;
  decided_at: string | null;
  needs_sign_off: boolean;
  sign_off: {
    handler_id: string;
    handler_name: string;
    signed_off_at: string;
  } | null;
  payment: { amount: number; paid_at: string } | null;
}

export interface Policy {
  policy_id: string;
  plan: { name: string };
  add_ons: { add_on: string; name: string }[];
  trip: { destination: string; departs_on: string; returns_on: string };
  travelers: string[];
}

export interface Step {
  step_id: number;
  thread_id: string;
  kind: StepKind;
  content: string;
  created_at: string;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = (await response.json()) as { detail?: unknown };
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `${path} failed (${String(response.status)})`,
    );
  }
  return (await response.json()) as T;
}

function post<T>(path: string, body?: object): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
}

export const api = {
  claims: () => request<ClaimSummary[]>("/api/claims"),
  claim: (id: string) => request<Claim>(`/api/claims/${id}`),
  steps: (id: string) => request<Step[]>(`/api/claims/${id}/steps`),
  policy: (id: string) => request<Policy>(`/api/policies/${id}`),
  handlers: () => request<Handler[]>("/api/handlers"),
  instructions: () => request<{ instructions: string }>("/api/instructions"),
  policyWording: () =>
    request<{ version: string; text: string }>("/api/policy-wording"),
  runClaim: (id: string) => post<Claim>(`/api/claims/${id}/run`),
  runQueue: () => post<string[]>("/api/queue/run"),
  signOff: (id: string, handlerId: string) =>
    post<Claim>(`/api/claims/${id}/sign-off`, { handler_id: handlerId }),
};
