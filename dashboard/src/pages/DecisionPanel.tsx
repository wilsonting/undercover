import { useCallback, useState } from "react";
import { api, type Claim } from "../api";
import { DECISION_LABELS, money } from "../format";
import { useData } from "../useData";

function SignOff({
  claim,
  onSignedOff,
}: Readonly<{ claim: Claim; onSignedOff: () => void }>) {
  const { data: handlers } = useData(api.handlers, null);
  const [handlerId, setHandlerId] = useState("");
  const [error, setError] = useState<string>();
  const payout = claim.decision?.payout ?? 0;

  const signOff = () => {
    api
      .signOff(claim.claim_id, handlerId)
      .then(onSignedOff, (failure: unknown) => {
        setError(failure instanceof Error ? failure.message : String(failure));
      });
  };

  return (
    <div className="note">
      <h3>Waiting for sign-off</h3>
      <p>
        A payout over $1,000.00 needs a handler&apos;s sign-off. Signing off
        pays {money(payout)}.
      </p>
      {error && <p className="alert">{error}</p>}
      <div className="row">
        <label>
          Handler{" "}
          <select
            value={handlerId}
            onChange={(event) => {
              setHandlerId(event.target.value);
            }}
          >
            <option value="">Choose your name</option>
            {handlers?.map((handler) => (
              <option key={handler.handler_id} value={handler.handler_id}>
                {handler.name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={signOff} disabled={handlerId === ""}>
          Sign off and pay {money(payout)}
        </button>
      </div>
    </div>
  );
}

function PaymentLine({ claim }: Readonly<{ claim: Claim }>) {
  if (claim.payment) {
    return (
      <p>
        <strong>Paid {money(claim.payment.amount)}</strong>{" "}
        <span className="muted mono">{claim.payment.paid_at.slice(0, 10)}</span>
        {claim.sign_off && <> · Signed off by {claim.sign_off.handler_name}</>}
      </p>
    );
  }
  if (claim.decision?.decision === "approve" && !claim.needs_sign_off) {
    return <p className="muted">Not paid yet.</p>;
  }
  return null;
}

export function DecisionPanel({
  claim,
  onChange,
}: Readonly<{ claim: Claim; onChange: () => void }>) {
  const [signedOff, setSignedOff] = useState(false);
  const onSignedOff = useCallback(() => {
    setSignedOff(true);
    onChange();
  }, [onChange]);
  const { decision } = claim;

  return (
    <section className="panel" aria-label="Decision">
      <h2>Decision</h2>
      {decision ? (
        <>
          <p>
            <span className={`decision ${decision.decision}`}>
              {DECISION_LABELS[decision.decision]}
            </span>
            {decision.decision === "approve" && (
              <>
                {" "}
                with a payout of{" "}
                <span className="mono">{money(decision.payout)}</span>
              </>
            )}
          </p>
          <p>{decision.reason}</p>
          <p className="muted">{decision.policy_section}</p>
          <details>
            <summary>The agent&apos;s working</summary>
            <pre className="mono prose">{decision.calculation}</pre>
          </details>
          <PaymentLine claim={claim} />
          {claim.status === "awaiting_sign_off" && !signedOff && (
            <SignOff claim={claim} onSignedOff={onSignedOff} />
          )}
        </>
      ) : (
        <p className="muted">No decision yet.</p>
      )}
    </section>
  );
}
