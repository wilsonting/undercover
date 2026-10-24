import { api } from "../api";
import { useData } from "../useData";

export function Instructions() {
  const instructions = useData(api.instructions, null);
  const wording = useData(api.policyWording, null);
  const error = instructions.error ?? wording.error;

  if (error) {
    return (
      <p className="alert">The instructions could not be loaded: {error}</p>
    );
  }

  return (
    <>
      <h1>The agent&apos;s instructions</h1>
      <p className="muted">
        What the UnderCover Agent is told for every claim: its instructions,
        then the policy wording. Read only.
      </p>
      <section className="panel" aria-label="Instructions">
        <h2>Instructions</h2>
        <div className="prose">{instructions.data?.instructions}</div>
      </section>
      <section className="panel" aria-label="Policy wording">
        <h2>
          Policy wording
          {wording.data && (
            <span className="muted mono"> version {wording.data.version}</span>
          )}
        </h2>
        <div className="prose">{wording.data?.text}</div>
      </section>
    </>
  );
}
