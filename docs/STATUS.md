# Status

The claims pilot, built from `docs/PLAN.md`. Done so far: Phases 1 to 5.

## What's built

- `backend/`: FastAPI on SQLite. `backend/db.py` seeds `undercover.db` at the repo root from `data/` (never `data/evals/`). Read routes for the claims queue, a claim, a policy with its plan and add-ons, a customer's claim history (without contact details), the handlers, the agent's instructions (`backend/instructions.md`) and the policy wording.
- Write routes for a run of the agent: start a claim, record its steps, record a decision, pay, sign off and release. A claim is `waiting`, `in_progress`, `awaiting_sign_off` or `decided`. A payout over $1,000 can't be paid until a handler signs off, and the sign-off makes the payment.
- `POST /api/claims/{id}/run` starts the agent on a waiting claim in the background, and `POST /api/queue/run` works through every waiting claim, one at a time.
- `agent/`: the UnderCover Agent. `run(claim_id, thread_id)` starts the claim, reads it with `get_claim`, `get_policy` and `get_claim_history`, records a decision and pays an approved claim, posting each step to the backend. Its system prompt is the instructions and the policy wording from the API. A run that fails or ends without a decision records an error step and puts the claim back in the queue. The tools that decide and pay are bound to the claim being run.
- `dashboard/`: React in the brand's fonts and colors, light and dark. The queue page shows a count for each state and every claim, refreshes every 2 seconds, and has "Work the queue". The claim page shows the claim in full, a "Run agent" button while it waits, the agent's steps as they happen, the decision with its reason, section and working, the payment, and a sign-off panel for payouts over $1,000. The instructions page shows the agent's instructions and the policy wording, read only. Pages are chosen by the address (`#/`, `#/claims/CLM-1001`, `#/instructions`).
- `e2e/`: Playwright tests on their own database (`e2e/undercover-e2e.db`), with the backend on port 8001 and the dashboard on port 5174, so they never touch your dev data.

## How to run it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173. The backend seeds the database on first start.
- `npm run reset` puts every claim back in the queue as it is in `data/`.
- `uv run -m agent CLM-1001` runs the agent on one claim (the backend must be running).
- `npm run check` runs every check.
