import StatusBadge from "./StatusBadge";
import type { WorkflowStatus } from "../../types/workflow";

type Props = {
  output: Record<string, unknown> | null;
  status: WorkflowStatus | null;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function stringValue(record: Record<string, unknown>, key: string): string | null {
  const value = record[key];
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
}

function outputSummary(output: Record<string, unknown>) {
  const record = asRecord(output) ?? {};
  const message = stringValue(record, "message") ?? "Workflow output is available.";
  const statusLabel = stringValue(record, "status");
  const action = stringValue(record, "action");
  const orderId = stringValue(record, "order_id");
  const amount = stringValue(record, "amount");
  const decision = stringValue(record, "decision");
  const submissionId = stringValue(record, "submission_id");

  return {
    message,
    fields: [
      ["Status", statusLabel],
      ["Order", orderId],
      ["Action", action],
      ["Amount", amount],
      ["Decision", decision],
      ["Submission", submissionId],
    ].filter((entry): entry is [string, string] => Boolean(entry[1])),
  };
}

export default function LatestOutputPanel({ output, status }: Props) {
  const summary = output ? outputSummary(output) : null;

  const copySummary = async () => {
    if (!output) {
      return;
    }
    await navigator.clipboard.writeText(
      JSON.stringify({ message: summary?.message, fields: summary?.fields ?? [] }, null, 2),
    );
  };

  return (
    <section className="panel panel-output">
      <header className="panel-head">
        <h2>Latest Output</h2>
        <div className="output-head-right">
          {status ? <StatusBadge status={status} /> : null}
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!output}
            onClick={copySummary}
          >
            Copy summary
          </button>
        </div>
      </header>
      {!output || !summary ? (
        <p className="muted">Start or select a workflow to view the latest output.</p>
      ) : (
        <div className="output-summary">
          <p>{summary.message}</p>
          {summary.fields.length > 0 ? (
            <dl className="summary-list">
              {summary.fields.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          <p className="muted">
            Raw model, tool, checkpoint, and backend details are redacted from
            the private frontend.
          </p>
        </div>
      )}
    </section>
  );
}
