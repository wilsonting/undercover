import { useCallback, useState } from "react";
import { api, type Claim, type Policy } from "../api";
import { StatusLabel } from "../components";
import { money, words } from "../format";
import { useData } from "../useData";
import { DecisionPanel } from "./DecisionPanel";
import { Steps } from "./Steps";

const REFRESH_MS = 1000;

function Details({
  claim,
  policy,
}: Readonly<{ claim: Claim; policy: Policy | undefined }>) {
  return (
    <section className="panel" aria-label="The claim">
      <h2>The claim</h2>
      <dl>
        <dt>Customer</dt>
        <dd>{claim.customer_name}</dd>
        <dt>Type</dt>
        <dd>{words(claim.claim_type)}</dd>
        <dt>Policy</dt>
        <dd>
          <span className="mono">{claim.policy_id}</span>
          {policy && ` · ${policy.plan.name}`}
          {policy?.add_ons.map((addOn) => ` · ${addOn.name}`)}
        </dd>
        {policy && (
          <>
            <dt>Trip</dt>
            <dd>
              {policy.trip.destination},{" "}
              <span className="mono">
                {policy.trip.departs_on} to {policy.trip.returns_on}
              </span>
            </dd>
            <dt>Travelers</dt>
            <dd>{policy.travelers.join(", ")}</dd>
          </>
        )}
        <dt>Incident</dt>
        <dd>
          <span className="mono">{claim.incident_date}</span>,{" "}
          {claim.incident_location}
        </dd>
        <dt>Submitted</dt>
        <dd className="mono">{claim.submitted_on}</dd>
      </dl>
      <h3 className="spaced">The customer&apos;s story</h3>
      <p className="quote">{claim.story}</p>
      <h3>Items claimed</h3>
      <div className="table-wrap">
        <table>
          <tbody>
            {claim.items.map((item) => (
              <tr key={item.description}>
                <td>{item.description}</td>
                <td>{words(item.category)}</td>
                <td className="amount mono">{money(item.amount)}</td>
              </tr>
            ))}
            <tr>
              <td>
                <strong>Total</strong>
              </td>
              <td />
              <td className="amount mono">
                <strong>{money(claim.amount_claimed)}</strong>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <h3 className="spaced">Documents</h3>
      <div className="steps">
        {claim.documents.map((document) => (
          <div key={document.name} className="step">
            <div className="kind">{words(document.type)}</div>
            <strong>{document.name}</strong>
            <div>{document.content}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function ClaimPage({ claimId }: Readonly<{ claimId: string }>) {
  const [requested, setRequested] = useState(false);
  const [message, setMessage] = useState<string>();
  const loadClaim = useCallback(() => api.claim(claimId), [claimId]);
  const loadSteps = useCallback(() => api.steps(claimId), [claimId]);
  const claimData = useData(loadClaim, REFRESH_MS);
  const claim = claimData.data;
  const { data: steps, reload: reloadSteps } = useData(loadSteps, REFRESH_MS);
  const policyId = claim?.policy_id;
  const loadPolicy = useCallback(
    () => (policyId ? api.policy(policyId) : Promise.resolve(undefined)),
    [policyId],
  );
  const { data: policy } = useData(loadPolicy, null);
  const reloadClaim = claimData.reload;
  const reload = useCallback(() => {
    reloadClaim();
    reloadSteps();
  }, [reloadClaim, reloadSteps]);

  const runAgent = () => {
    setRequested(true);
    setMessage(undefined);
    api.runClaim(claimId).then(
      () => {
        setRequested(false);
        reload();
      },
      (failure: unknown) => {
        setRequested(false);
        setMessage(
          failure instanceof Error ? failure.message : String(failure),
        );
      },
    );
  };

  if (claimData.error && !claim) {
    return (
      <p className="alert">
        Claim {claimId} could not be loaded: {claimData.error}
      </p>
    );
  }
  if (!claim) return <p className="muted">Loading the claim</p>;

  const working = claim.status === "in_progress";

  return (
    <>
      <p>
        <a href="#/">Back to the queue</a>
      </p>
      <div className="row">
        <div>
          <h1 className="mono">{claim.claim_id}</h1>
          <p className="muted flush">{claim.summary}</p>
        </div>
        <div className="row flush">
          <StatusLabel status={claim.status} />
          {claim.status === "waiting" && (
            <button type="button" onClick={runAgent} disabled={requested}>
              Run agent
            </button>
          )}
        </div>
      </div>
      {message && <p className="alert">{message}</p>}
      <div className="grid">
        <Details claim={claim} policy={policy} />
        <div>
          <DecisionPanel claim={claim} onChange={reload} />
          <Steps steps={steps ?? []} working={working} />
        </div>
      </div>
    </>
  );
}
