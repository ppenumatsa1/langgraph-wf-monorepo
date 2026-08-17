import JsonViewer from "./JsonViewer";
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

function findNestedValue(value: unknown, keys: string[], depth = 0): string | null {
  if (depth > 5 || value === null || value === undefined) {
    return null;
  }
  if (typeof value !== "object") {
    return null;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const nested = findNestedValue(item, keys, depth + 1);
      if (nested) {
        return nested;
      }
    }
    return null;
  }

  const record = value as Record<string, unknown>;
  for (const key of keys) {
    const direct = stringValue(record, key);
    if (direct) {
      return direct;
    }
  }
  for (const nested of Object.values(record)) {
    const result = findNestedValue(nested, keys, depth + 1);
    if (result) {
      return result;
    }
  }
  return null;
}

function outputSummary(output: Record<string, unknown>) {
  const record = asRecord(output) ?? {};
  const message = stringValue(record, "message") ?? "Workflow output is available.";
  const statusLabel = stringValue(record, "status");
  const action = findNestedValue(record, ["action"]);
  const orderId = findNestedValue(record, ["order_id", "orderId"]);
  const amount = findNestedValue(record, ["amount", "total_amount", "totalAmount"]);
  const decision = findNestedValue(record, ["decision"]);
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
  const copyOutput = async () => {
    if (!output) {
      return;
    }
    await navigator.clipboard.writeText(JSON.stringify(output, null, 2));
  };

  const summary = output ? outputSummary(output) : null;

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
            onClick={copyOutput}
          >
            Copy raw
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
          <details>
            <summary>Raw details</summary>
            <JsonViewer value={output} emptyText="No output details" />
          </details>
        </div>
      )}
    </section>
  );
}
