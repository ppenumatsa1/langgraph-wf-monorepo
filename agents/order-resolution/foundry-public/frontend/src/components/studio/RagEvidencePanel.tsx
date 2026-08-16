import type { WorkflowEvent, WorkflowRunDetails } from "../../types/workflow";

type Props = {
  details: WorkflowRunDetails | null;
  events: WorkflowEvent[];
};

type EvidenceEntry = {
  id: string;
  timestampLabel: string;
  source: string;
  provider: string | null;
  queryId: string | null;
  evidenceCount: number | null;
  policy: string | null;
  chunkIds: string[];
  snippets: string[];
  raw: unknown;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function collectChunkIds(value: unknown, collector: Set<string>, depth = 0): void {
  if (depth > 6 || value === null || value === undefined) {
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectChunkIds(item, collector, depth + 1));
    return;
  }
  if (typeof value !== "object") {
    return;
  }

  Object.entries(value as Record<string, unknown>).forEach(([key, nested]) => {
    if (/chunk(_?id|s?)$/i.test(key) || /^chunk/i.test(key)) {
      if (typeof nested === "string" || typeof nested === "number") {
        collector.add(String(nested));
      } else if (Array.isArray(nested)) {
        nested.forEach((item) => {
          if (typeof item === "string" || typeof item === "number") {
            collector.add(String(item));
          }
        });
      }
    }
    collectChunkIds(nested, collector, depth + 1);
  });
}

function collectSnippets(value: unknown, collector: Set<string>, depth = 0): void {
  if (depth > 6 || value === null || value === undefined) {
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectSnippets(item, collector, depth + 1));
    return;
  }
  if (typeof value !== "object") {
    return;
  }

  Object.entries(value as Record<string, unknown>).forEach(([key, nested]) => {
    if (
      /^(evidence|snippet|quote|passage|content|text|policy)$/i.test(key) &&
      typeof nested === "string"
    ) {
      const trimmed = nested.trim();
      if (trimmed) {
        collector.add(trimmed);
      }
    }
    collectSnippets(nested, collector, depth + 1);
  });
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
  const mcpResult = asRecord(payloadRecord.mcp_result);
  const mcpPayload = mcpResult?.result ?? mcpResult ?? payloadRecord;
  const mcpPayloadRecord = asRecord(mcpPayload) ?? payloadRecord;
  const policyRetrieval = asRecord(payloadRecord.policy_retrieval);

  const chunkIds = new Set<string>();
  collectChunkIds(payloadRecord, chunkIds);
  collectChunkIds(mcpPayloadRecord, chunkIds);

  const snippets = new Set<string>();
  collectSnippets(mcpPayloadRecord, snippets);

  const policy =
    typeof payloadRecord.policy === "string" ? payloadRecord.policy : null;
  if (!policy && chunkIds.size === 0 && snippets.size === 0) {
    return null;
  }

  const timestampLabel = Number.isNaN(new Date(timestamp).getTime())
    ? "n/a"
    : new Date(timestamp).toLocaleTimeString();
  const resolvedSource =
    typeof mcpResult?.source === "string" ? mcpResult.source : source;
  const provider =
    typeof policyRetrieval?.provider === "string" ? policyRetrieval.provider : null;
  const queryId =
    typeof policyRetrieval?.query_id === "string" ? policyRetrieval.query_id : null;
  const evidenceCount =
    typeof policyRetrieval?.count === "number" ? policyRetrieval.count : null;

  return {
    id,
    timestampLabel,
    source: resolvedSource,
    provider,
    queryId,
    evidenceCount,
    policy,
    chunkIds: [...chunkIds].slice(0, 12),
    snippets: [...snippets].slice(0, 3),
    raw: payload,
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
        <h2>RAG Evidence</h2>
      </header>
      {entries.length === 0 ? (
        <p className="muted">
          No policy evidence retrieved yet for the selected workflow.
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
                {entry.provider ? (
                  <div>
                    <dt>Provider</dt>
                    <dd>{entry.provider}</dd>
                  </div>
                ) : null}
                {entry.queryId ? (
                  <div>
                    <dt>Query</dt>
                    <dd>{entry.queryId}</dd>
                  </div>
                ) : null}
                {entry.evidenceCount !== null ? (
                  <div>
                    <dt>Evidence</dt>
                    <dd>{entry.evidenceCount}</dd>
                  </div>
                ) : null}
              </dl>
              {entry.policy ? (
                <div className="evidence-section">
                  <strong>Policy/action</strong>
                  <p className="evidence-policy">{entry.policy}</p>
                </div>
              ) : null}
              {entry.chunkIds.length > 0 ? (
                <div className="evidence-section">
                  <strong>Chunk IDs</strong>
                  <div className="evidence-chunks">
                    {entry.chunkIds.map((chunkId) => (
                      <code key={`${entry.id}-${chunkId}`}>{chunkId}</code>
                    ))}
                  </div>
                </div>
              ) : null}
              {entry.snippets.length > 0 ? (
                <div className="evidence-section">
                  <strong>Snippets</strong>
                  <ul>
                    {entry.snippets.map((snippet) => (
                      <li key={`${entry.id}-${snippet}`}>{snippet}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <details>
                <summary>Raw details</summary>
                <pre className="json-viewer">{JSON.stringify(entry.raw, null, 2)}</pre>
              </details>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
