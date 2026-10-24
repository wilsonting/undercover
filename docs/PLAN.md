# Plan: the claims pilot

The pilot builds the first UnderCover claims platform from `docs/SPEC.md`: a backend that holds the claims queue and enforces the payment rule, the UnderCover Agent that decides claims through that backend, and a dashboard where handlers watch the queue, follow the agent step by step and sign off large payouts.

## Approach

### The shape of the system

```
dashboard (React)  --HTTP-->  backend (FastAPI + SQLite)  <--HTTP--  agent (create_agent)
                                     |
                              seeded from data/
```

- **The backend owns the data and the rules.** It seeds a SQLite database from `data/` and is the only thing that reads it. The payment rule lives here, so it holds whatever the agent does.
- **The agent only talks to the backend's API.** Its tools are thin wrappers over API calls, and it fetches its own instructions from the API at the start of each run. It never reads files in `data/`.
- **The dashboard only talks to the backend's API**, through Vite's `/api` proxy as it does today.

### Key decisions and why

1. **SQLite through Python's standard `sqlite3` module**, no ORM. The pilot has six small tables and a handful of queries, so plain SQL is the simplest thing that works. The database file is `undercover.db` at the repo root (already ignored by `*.db` in `.gitignore`), or the path in `UNDERCOVER_DB` if set, which lets tests and end-to-end runs use their own copy.
2. **Seeding.** On startup the backend creates and seeds the database if it doesn't exist. It reads only the files it needs: `claims.json`, `policies.json`, `customers.json`, `plans.json`, `handlers.json`, `company.json` and `policy_wording.md`. It never reads `data/evals/`, `data/security/`, `claims_manual.md` or `knowledge.json`. `npm run reset` deletes and reseeds the database, so you can start the queue again after trying the agent.
3. **Claim states** match the four the spec asks for: `waiting`, `in_progress`, `awaiting_sign_off` and `decided`. The seed data's `open` becomes `waiting`.

   ```
   waiting --run--> in_progress --decision--> decided            (decline, refer, approve <= $1,000)
                                          \-> awaiting_sign_off  (approve > $1,000) --sign-off--> decided
   ```

   If a run fails or ends without a decision, the claim goes back to `waiting` and the failure is recorded as a step, so nothing gets stuck in progress.
4. **The payment rule is enforced by the backend, not the prompt.** Paying is its own operation, `POST /api/claims/{id}/payment`, which takes the amount. It refuses with `409 Conflict` unless the claim has an approve decision, the amount equals the approved payout, the claim hasn't been paid yet, and, for a payout over the `payout_approval_limit` in `company.json` ($1,000), a handler has signed off. The agent has a `pay_claim` tool, so it can try to pay a large claim; the backend blocks it, and a test proves it. When a handler signs off, the backend records who signed off and makes the held payment of the approved amount through the same code path. No real money moves: a payment is a record with the amount and the time.
5. **What the agent sees.** Its tools:
   - `get_claim(claim_id)`: the story, items, documents, dates and amounts.
   - `get_policy(policy_id)`: the policy with its plan's limits and the add-ons it holds, joined from `plans.json`, so the agent doesn't have to look them up.
   - `get_claim_history(customer_id)`: the customer's earlier claims and when they became a customer. It leaves out contact details, address and date of birth, which the agent doesn't need to decide a claim.
   - `record_decision(claim_id, decision, payout, calculation, reason, policy_section)`: approve, decline or refer, with the payout ($0 unless approving), the working behind it, a two or three sentence reason and the section of the policy wording it rests on.
   - `pay_claim(claim_id, amount)`: pay an approved claim.

   The policy wording isn't a tool: it's short enough to go in the system prompt, so the agent always has it. The system prompt is the instructions plus the wording, both fetched from the API (`GET /api/instructions` and `GET /api/policy-wording`). The instructions live in `backend/instructions.md`, so the backend owns them and the dashboard shows exactly what the agent gets.
6. **Following the agent step by step.** `run(claim_id, thread_id)` streams the agent (`stream_mode="updates"`) and posts each step to the backend as it happens: the model's thinking out loud, each tool call with its inputs, and each tool result. The dashboard polls the claim and its steps every second while the claim is in progress. Polling is simpler than server-sent events and fast enough for a run that takes tens of seconds.
7. **Starting runs from the dashboard.** `POST /api/claims/{id}/run` marks a waiting claim in progress and runs the agent in a FastAPI background task with a fresh thread id. `POST /api/queue/run` works through every waiting claim, one at a time, in the background. The agent can also be run from the terminal: `uv run -m agent CLM-1001`.
8. **Every API operation** has an `operation_id`, a one-line docstring and no optional inputs, as `docs/TECH_STACK.md` asks. Request and response bodies are Pydantic models.
9. **The dashboard** uses a small hash router (`#/`, `#/claims/CLM-1001`, `#/instructions`) instead of adding a routing library: three pages don't need one. It follows `docs/BRAND.md`: the three fonts from Google Fonts, Sea Green, Marigold, Coral and Cerulean for the four claim states, light and dark mode from the system setting, and rounded panels with no outlines. There's no sign-in, so a handler picks their name from the handlers list when they sign off.
10. **Tests never call a model.** Agent tests use a stub chat model with scripted tool calls, as the skeleton does, against the backend's `TestClient`. End-to-end tests run on their own database and ports (backend on 8001, dashboard on 5174) so they never touch your dev data. They play the agent's part through the API (posting steps and a decision) or intercept the run request, rather than running the agent.

### Not in the pilot

Per the spec's "Not for now": the claims manual, sign-in, real payments and messages to customers. Also left for later days: evaluations against `data/evals/`, the agent's memory, durable state and versioned instructions.

## Phase 1: The backend's data and read API

Builds the database, the seeding and everything the dashboard and agent need to read.

- `backend/db.py`: schema (`claims`, `policies`, `customers`, `plans`, `handlers`, `settings`, `steps`, `payments`), connection helper, seeding from `data/`, and `uv run -m backend.db --reset`.
- `backend/main.py`: the read routes, with seeding on startup.
- `backend/instructions.md`: a first version of the agent's instructions.
- `npm run reset` in `package.json`.

Routes:

| Method and path | operation_id | Returns |
|---|---|---|
| `GET /api/claims` | `list_claims` | The queue: id, customer name, type, amount claimed, submitted date, status, decision and payout |
| `GET /api/claims/{claim_id}` | `get_claim` | The claim in full, with its decision, sign-off and payment if any |
| `GET /api/policies/{policy_id}` | `get_policy` | The policy with its plan's limits and its add-ons |
| `GET /api/customers/{customer_id}/claim-history` | `get_claim_history` | Customer since, and earlier claims |
| `GET /api/handlers` | `list_handlers` | The three handlers |
| `GET /api/instructions` | `get_instructions` | The agent's instructions |
| `GET /api/policy-wording` | `get_policy_wording` | The policy wording and its version |
| `GET /api/health` | `health` | Unchanged |

Success criteria:

- [x] `uv run pytest -q backend` passes, with tests for seeding and every route above.
- [x] A test proves the seed reads no file under `data/evals/` or `data/security/` (it patches file opening and checks every path).
- [x] After `npm run reset`, `GET /api/claims` returns 25 claims, all `waiting`, and CLM-1001 is first.
- [x] `GET /api/claims/CLM-1001` returns the Meridian Air story, three items totalling $420.00 and four documents.
- [x] `GET /api/policies/POL-2001` returns plan `premium` with a 6 hour trip delay waiting period, an $800 trip delay maximum and a $50 deductible.
- [x] `GET /api/customers/CUS-3001/claim-history` returns CLM-0412 and contains no email, phone, address or date of birth.
- [x] `GET /api/claims/CLM-9999` returns 404.
- [x] `GET /openapi.json` shows an `operation_id` and a one-line description on every operation, and no optional parameters.
- [x] `npm run check:python` passes with coverage of at least 80%.

## Phase 2: Decisions, payments and the sign-off rule

Builds the write side of the API and the state machine, including the rule that blocks payment over $1,000 until a handler signs off.

Routes:

| Method and path | operation_id | Does |
|---|---|---|
| `POST /api/claims/{claim_id}/start` | `start_claim` | Moves a waiting claim to `in_progress` with a thread id |
| `POST /api/claims/{claim_id}/steps` | `add_step` | Records one step of a run: thread id, kind (`thinking`, `tool_call`, `tool_result`, `error`) and content |
| `GET /api/claims/{claim_id}/steps` | `list_steps` | The steps of the claim's latest run, in order |
| `POST /api/claims/{claim_id}/decision` | `record_decision` | Records the decision and moves the claim to `decided` or `awaiting_sign_off` |
| `POST /api/claims/{claim_id}/payment` | `pay_claim` | Pays an approved claim the given amount, or refuses with 409 |
| `POST /api/claims/{claim_id}/sign-off` | `sign_off_claim` | A handler signs off a claim awaiting sign-off, and the held payment is made |
| `POST /api/claims/{claim_id}/release` | `release_claim` | Moves an in-progress claim back to `waiting` after a failed run |

Success criteria:

- [x] `uv run pytest -q backend` passes, with a test for every transition and every refusal below.
- [x] Recording a decline or refer moves the claim to `decided` with a $0 payout; an approve of $420.00 moves it to `decided`.
- [x] An approve of $1,350.00 moves the claim to `awaiting_sign_off`.
- [x] Paying that $1,350.00 claim before sign-off returns 409 with a message that it needs a handler's sign-off, and no payment is recorded.
- [x] After `sign_off_claim` with `HND-01`, the claim is `decided`, shows Dana Whitfield as the handler who signed off, and has one payment of $1,350.00.
- [x] Paying a claim twice, paying a different amount from the approved payout, and paying a declined claim each return 409.
- [x] A decision with an unknown value, a negative payout, or a non-zero payout on a decline returns 422; a decision on a claim that isn't in progress returns 409.
- [x] Signing off a claim that isn't awaiting sign-off, or with an unknown handler, is refused.
- [x] With the backend running, the same flow works over HTTP with `curl` on CLM-1001 (start, step, decision, payment), and `GET /api/claims/CLM-1001` shows it `decided` and paid.
- [x] `npm run check:python` passes with coverage of at least 80%.

## Phase 3: The UnderCover Agent

Replaces the hello-world agent with the claims agent, and lets the dashboard and the terminal start runs.

- `agent/main.py`: the five tools from the approach, each a call to the backend; `run(claim_id, thread_id)`, which fetches the instructions and wording, streams the agent and posts each step; and the model selection as today (`openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME`).
- `agent/__main__.py`: `uv run -m agent CLM-1001` runs one claim and prints the final reply.
- `backend/instructions.md`: the full instructions: read the claim, the policy and the claim history; check the claim against the wording, section by section; work out the payout as section 10 sets out and show the working; refer when the wording can't settle the claim or a document it needs is missing; record exactly one decision; pay an approved claim; and treat the claim's story and documents as the customer's evidence, not as instructions.
- `backend/main.py`: `POST /api/claims/{claim_id}/run` (`run_claim`) and `POST /api/queue/run` (`run_queue`), which start runs in the background. A run that raises, or ends without a decision, posts an `error` step and releases the claim.

Success criteria:

- [x] `uv run pytest -q agent backend` passes. Using a stub model and the backend's `TestClient`, the tests cover:
  - [x] a full run on CLM-1001 that reads the claim, policy and history, records an approve of $420.00, pays it, and leaves the claim `decided` and paid, with each step recorded in order;
  - [x] a run that approves a $1,350.00 payout and then tries to pay it: the tool returns the backend's refusal, the claim stays `awaiting_sign_off`, and no payment is recorded;
  - [x] a run that ends without a decision, and one where the model raises: both leave an `error` step and the claim back in `waiting`;
  - [x] the system prompt is built from `GET /api/instructions` and `GET /api/policy-wording`;
  - [x] `run_claim` refuses a claim that isn't waiting with 409, and `run_queue` runs only waiting claims.
- [x] No file in `agent/` mentions `data/` (checked with a search), and the agent's only network calls are to the backend and OpenRouter.
- [x] Live check, with your OpenRouter key and a cost of a few cents: after `npm run reset` and with the backend running, `uv run -m agent CLM-1001` records a decision with a reason of two or three sentences and a policy section, and `GET /api/claims/CLM-1001/steps` lists the steps of the run.
- [x] `npm run check:python` passes with coverage of at least 80%.

## Phase 4: The dashboard's queue

Builds the dashboard's frame, the brand and the queue page.

- `dashboard/src/api.ts`: typed functions for each API call, with types that match the backend's models.
- `dashboard/src/router.ts`: the hash router.
- `dashboard/src/theme.css`: the brand's colors, fonts and surfaces for light and dark mode.
- `dashboard/src/pages/Queue.tsx`: a count for each of the four states, and a table of claims with id, customer, type, amount claimed, submitted date, a colored status label, and the decision and payout once decided. Each row opens the claim. A "Work the queue" button starts `run_queue` and the page refreshes every few seconds while any claim is in progress.
- A header with the UnderCover name and links to the queue and the instructions.

Success criteria:

- [x] `npx vitest run --root dashboard --coverage` passes, with tests for the queue page (counts, rows, status labels, empty and error states), the router and the API functions, using a stubbed `fetch`.
- [x] `npm run check:ts` passes: Prettier, ESLint, `tsc` in strict mode with no `any`, and coverage of at least 80%.
- [x] `playwright.config.ts` runs the backend on port 8001 with its own fresh database and the dashboard on port 5174, and the existing health test is replaced by a queue test: the page shows 25 claims whose state counts add up to 25 (later tests change some claims, so all 25 waiting is checked in the browser below), and CLM-1001 links to its claim page.
- [x] In the browser with the Playwright MCP server: after `npm run reset` the queue shows all 25 claims waiting, with amounts like $1,350.00, the fonts are Instrument Sans and JetBrains Mono, and the page looks right in light and dark mode (screenshots of both).

## Phase 5: The claim page and the instructions page

Builds the pages where handlers read a claim, follow the agent and sign off.

- `dashboard/src/pages/Claim.tsx`:
  - the claim: customer, policy and plan, dates, story, items and documents;
  - a "Run agent" button while the claim is waiting;
  - the agent's steps, updated every second (also after the decision, since the agent pays and sums up after it decides): what it's reading, the tools it calls and what it decided;
  - the decision: approve, decline or refer, the payout, the working, the reason and the policy section;
  - the payment: paid with the amount and time, or waiting for sign-off;
  - for a claim awaiting sign-off, a sign-off panel where the handler picks their name and confirms, which records the sign-off and makes the payment.
- `dashboard/src/pages/Instructions.tsx`: the agent's instructions, read only, with the policy wording below them under its own heading, so the team sees everything the agent is told.

Success criteria:

- [x] Vitest tests for both pages pass: the claim in full; the run button only while waiting; steps appearing as polling returns them; each decision type; the payment and sign-off states; signing off sends the chosen handler; and the instructions page shows the text and has no way to edit it.
- [x] `npm run check:ts` passes with coverage of at least 80%.
- [x] Playwright tests pass, playing the agent's part through the API:
  - [x] after starting CLM-1001 and posting two steps, the claim page shows it in progress with both steps, and a third step appears without reloading;
  - [x] after recording an approve of $420.00 and paying it, the page shows the decision, its reason and section, and "Paid $420.00";
  - [x] for a claim approved at $1,350.00, the page shows it waiting for sign-off; signing off as Priya Raman shows it decided, signed off by Priya Raman and paid $1,350.00, and the queue's counts update;
  - [x] the instructions page shows the instructions and the policy wording.
- [x] In the browser with the Playwright MCP server, with the real agent on one waiting claim: clicking "Run agent" shows the steps arriving live, then the decision. Screenshots of the claim page in light and dark mode.

## Phase 6: The whole pilot, end to end

Checks the pilot as a whole and brings the documents up to date.

- A live run of five claims of different kinds, one by one with "Run agent", at a cost of well under a dollar. Note how the decisions read; scoring them against the handlers' decisions is a later day's work.
- `docs/STATUS.md`: what's built, how to run it, how to reset the queue and how to run the agent.

Success criteria:

- [x] `npm run check` passes: ruff, pyright, pytest, Prettier, ESLint, tsc, vitest and Playwright, with both coverage thresholds met.
- [x] `npm run reset` then `npm run dev` gives a dashboard at http://localhost:5173 with 25 waiting claims.
- [x] The five live runs each end `decided` or `awaiting_sign_off`, each with a reason of two or three sentences and a policy section, and none is paid over $1,000 without a sign-off.
- [x] `git grep -n "evals" backend agent dashboard` finds nothing that reads the answer key.
- [x] `docs/STATUS.md` describes the pilot as built, and every box in this plan is ticked.
