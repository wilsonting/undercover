import type { Step, StepKind } from "../api";

const KIND_LABELS: Record<StepKind, string> = {
  thinking: "Agent",
  tool_call: "Calls a tool",
  tool_result: "Tool result",
  error: "Error",
};

function StepContent({ step }: Readonly<{ step: Step }>) {
  if (step.kind === "tool_result") {
    const split = step.content.indexOf(": ");
    const tool = step.content.slice(0, split);
    return (
      <details>
        <summary>Reply from {tool}</summary>
        <pre className="mono">{step.content.slice(split + 2)}</pre>
      </details>
    );
  }
  if (step.kind === "tool_call") {
    return <pre className="mono">{step.content}</pre>;
  }
  return <div className="prose">{step.content}</div>;
}

export function Steps({
  steps,
  working,
}: Readonly<{ steps: Step[]; working: boolean }>) {
  return (
    <section className="panel" aria-label="The agent's work">
      <h2>The agent&apos;s work</h2>
      {steps.length === 0 && !working && (
        <p className="muted">The agent hasn&apos;t worked on this claim yet.</p>
      )}
      <ol className="steps">
        {steps.map((step) => (
          <li key={step.step_id} className={`step ${step.kind}`}>
            <div className="kind">{KIND_LABELS[step.kind]}</div>
            <StepContent step={step} />
          </li>
        ))}
      </ol>
      {working && (
        <p className="muted" role="status">
          The agent is working on this claim.
        </p>
      )}
    </section>
  );
}
