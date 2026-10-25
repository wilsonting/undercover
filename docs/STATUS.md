# Status

The claims pilot is built, from `docs/PLAN.md`. All six phases are done.

## What's built

- `backend/`: FastAPI on SQLite.
  - `backend/db.py` seeds `undercover.db` at the repo root from `data/`, and never reads `data/evals/`, `data/security/`, the claims manual or `knowledge.json`.
  - Read routes for the queue, a claim, a policy with its plan and add-ons, a customer's claim history (without contact details), the handlers, the agent's instructions (`backend/instructions.md`) and the policy wording.
  - Write routes for a run of the agent: start, steps, decision, payment, sign-off and release. A claim is `waiting`, `in_progress`, `awaiting_sign_off` or `decided`.
  - The payment rule: a payout over $1,000 is refused until a handler signs off, and the sign-off makes the payment. A payment must match the approved payout and is made once.
  - `POST /api/claims/{id}/run` starts the agent on a waiting claim in the background; `POST /api/queue/run` works through every waiting claim, one at a time.
- `agent/`: the UnderCover Agent, LangChain's `create_agent` on OpenRouter (`openai/gpt-6-luna` with low reasoning, or `MODEL_NAME`). `run(claim_id, thread_id)` starts the claim, reads it with `get_claim`, `get_policy` and `get_claim_history`, records one decision and pays an approved claim, posting each step to the backend. The system prompt is the instructions and the policy wording, both from the API. The tools that decide and pay are bound to the claim being run. A run that fails or ends without a decision records an error step and puts the claim back in the queue.
- `dashboard/`: React in the brand's fonts and colors, light and dark.
  - The queue (`#/`): a count for each state, every claim, "Work the queue", refreshed every 2 seconds.
  - A claim (`#/claims/CLM-1001`): the claim in full, "Run agent" while it waits, the agent's steps as they happen, the decision with its reason, policy section and working, the payment, and a sign-off panel for payouts over $1,000.
  - The instructions (`#/instructions`): the agent's instructions and the policy wording, read only.
- `e2e/`: Playwright tests on their own database (`e2e/undercover-e2e.db`), with the backend on port 8001 and the dashboard on port 5174, so they never touch your dev data. They play the agent's part through the API and never call a model.

## How to run it

- `npm run dev` starts the backend on port 8000 and the dashboard at http://localhost:5173. The backend seeds the database on first start.
- `npm run reset` puts every claim back in the queue as it is in `data/`.
- `uv run -m agent CLM-1001` runs the agent on one claim from the terminal, and `uv run -m agent` works every waiting claim in turn, in queue order, going on to the next if a run fails. The backend must be running.
- `npm run check` runs every check.

## The first live run

With `openai/gpt-6-luna`, five claims of different kinds each ended with a decision, a reason of two or three sentences and a policy section: CLM-1003 (emergency medical, approve $3,750.00), CLM-1004 (baggage delay, approve $74.00), CLM-1005 (passport, approve $243.00), CLM-1008 (trip cancellation, approve $2,240.00) and CLM-1011 (baggage, approve $1,110.00), plus CLM-1001 (approve $420.00) and CLM-1010 (decline, alcohol exclusion) earlier. The agent tried to pay each payout over $1,000, and the backend refused each until sign-off. Scoring the decisions against the handlers' own is for a later build.
