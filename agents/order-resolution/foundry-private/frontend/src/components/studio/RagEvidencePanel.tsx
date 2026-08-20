import type { WorkflowEvent, WorkflowRunDetails } from "../../types/workflow";

type Props = {
  details: WorkflowRunDetails | null;
  events: WorkflowEvent[];
};

type EvidenceEntry = {
  id: string;
  timestampLabel: string;
  source: string;
  evidenceCount: number | null;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function extractEvidenceEntry(
  id: string,
  source: string,
  timestamp: string,
  payload: unknown,
): EvidenceEntry | null {
  const payloadRecord = asRecord(payload);
  if (!payloadRecord) {
    return null;
  }
  const evidenceCount =
    typeof payloadRecord.evidence_count === "number"
      ? payloadRecord.evidence_count
      : null;
  if (evidenceCount === null) {
    return null;
  }

  const timestampLabel = Number.isNaN(new Date(timestamp).getTime())
    ? "n/a"
    : new Date(timestamp).toLocaleTimeString();

  return {
    id,
    timestampLabel,
    source,
    evidenceCount,
  };
}

function buildEntries(
  details: WorkflowRunDetails | null,
  events: WorkflowEvent[],
): EvidenceEntry[] {
  const eventEntries = events
    .filter((event) => event.type === "tool.call" || event.type === "workflow.output")
    .map((event) =>
      extractEvidenceEntry(event.id, event.type, event.timestamp, event.payload),
    )
    .filter((entry): entry is EvidenceEntry => Boolean(entry));

  if (details?.latest_output) {
    const latestOutputEntry = extractEvidenceEntry(
      "latest-output",
      "latest_output",
      details.metadata.started_at ?? "",
      details.latest_output,
    );
    if (latestOutputEntry) {
      eventEntries.push(latestOutputEntry);
    }
  }

  return eventEntries;
}

export default function RagEvidencePanel({ details, events }: Props) {
  const entries = buildEntries(details, events);

  return (
    <section className="panel panel-rag-evidence">
      <header className="panel-head">
        <h2>Policy Evidence</h2>
      </header>
      {entries.length === 0 ? (
        <p className="muted">
          No redacted policy evidence metadata is available for the selected
          workflow.
        </p>
      ) : (
        <div className="evidence-list">
          {entries.map((entry) => (
            <article className="evidence-item" key={entry.id}>
              <div className="evidence-head">
                <span className="event-badge">{entry.source}</span>
                <span className="muted">{entry.timestampLabel}</span>
              </div>
              <dl className="summary-list evidence-summary-list">
                {entry.evidenceCount !== null ? (
                  <div>
                    <dt>Evidence</dt>
                    <dd>{entry.evidenceCount}</dd>
                  </div>
                ) : null}
              </dl>
              <p className="muted">
                Evidence text, chunk IDs, provider/query identifiers, MCP/RAG
                payloads, and raw tool data are redacted from the private
                frontend.
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
