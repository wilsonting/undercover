# Status

The claims pilot, built from `docs/PLAN.md`. Done so far: Phases 1 and 2.

## What's built

- `backend/`: FastAPI on SQLite. `backend/db.py` seeds `undercover.db` at the repo root from `data/` (never `data/evals/`). Read routes for the claims queue, a claim, a policy with its plan and add-ons, a customer's claim history (without contact details), the handlers, the agent's instructions (`backend/instructions.md`) and the policy wording.
- Write routes for a run of the agent: start a claim, record its steps, record a decision, pay, sign off and release. A claim is `waiting`, `in_progress`, `awaiting_sign_off` or `decided`. A payout over $1,000 can't be paid until a handler signs off, and the sign-off makes the payment.
- `agent/`: still the hello-world skeleton.
- `dashboard/`: still the hello-world skeleton.
- `e2e/`: one test of the dashboard's health page.

## How to run it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173. The backend seeds the database on first start.
- `npm run reset` puts every claim back in the queue as it is in `data/`.
- `npm run check` runs every check.
