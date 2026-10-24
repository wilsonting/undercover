import { useState } from "react";
import { api, type Status } from "../api";
import { StatusLabel } from "../components";
import { DECISION_LABELS, money, STATUS_LABELS, words } from "../format";
import { useData } from "../useData";

const STATUSES: Status[] = [
  "waiting",
  "in_progress",
  "awaiting_sign_off",
  "decided",
];
const REFRESH_MS = 2000;

export function Queue() {
  const { data: claims, error, reload } = useData(api.claims, REFRESH_MS);
  const [message, setMessage] = useState<string>();

  const workQueue = () => {
    api.runQueue().then(
      (started) => {
        const claims =
          started.length === 1 ? "1 claim" : `${String(started.length)} claims`;
        setMessage(`The agent is working through ${claims}, one at a time.`);
        reload();
      },
      (failure: unknown) => {
        setMessage(
          failure instanceof Error ? failure.message : String(failure),
        );
      },
    );
  };

  if (error && !claims)
    return <p className="alert">The queue could not be loaded: {error}</p>;
  if (!claims) return <p className="muted">Loading the queue</p>;

  const count = (status: Status) =>
    claims.filter((claim) => claim.status === status).length;

  return (
    <>
      <div className="row">
        <h1>Claims queue</h1>
        <button
          type="button"
          onClick={workQueue}
          disabled={count("waiting") === 0}
        >
          Work the queue
        </button>
      </div>
      {message && (
        <p className="note" role="status">
          {message}
        </p>
      )}
      <div className="tiles">
        {STATUSES.map((status) => (
          <div className="tile" key={status} data-testid={`count-${status}`}>
            <div>
              <span className={`dot ${status}`} />
              {STATUS_LABELS[status]}
            </div>
            <div className="count">{count(status)}</div>
          </div>
        ))}
      </div>
      <div className="panel table-wrap">
        {claims.length === 0 ? (
          <p className="muted">The queue is empty.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Claim</th>
                <th>Customer</th>
                <th>Type</th>
                <th>Submitted</th>
                <th className="amount">Claimed</th>
                <th>Status</th>
                <th>Decision</th>
                <th className="amount">Payout</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((claim) => (
                <tr key={claim.claim_id}>
                  <td className="mono">
                    <a href={`#/claims/${claim.claim_id}`}>{claim.claim_id}</a>
                  </td>
                  <td>{claim.customer_name}</td>
                  <td>{words(claim.claim_type)}</td>
                  <td className="mono">{claim.submitted_on}</td>
                  <td className="amount mono">{money(claim.amount_claimed)}</td>
                  <td>
                    <StatusLabel status={claim.status} />
                  </td>
                  <td>
                    {claim.decision && (
                      <span className={`decision ${claim.decision}`}>
                        {DECISION_LABELS[claim.decision]}
                      </span>
                    )}
                  </td>
                  <td className="amount mono">
                    {claim.payout === null ? "" : money(claim.payout)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
