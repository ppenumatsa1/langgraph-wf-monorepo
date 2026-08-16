import JsonViewer from "./JsonViewer";
import type { WorkflowEvent } from "../../types/workflow";

type Props = {
  event: WorkflowEvent;
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

function summarizeEvent(event: WorkflowEvent): string {
  const payload = event.payload ?? {};
  const result = asRecord(payload.result);
  const order = asRecord(payload.order);
  const policyRetrieval = asRecord(payload.policy_retrieval);

  switch (event.type) {
    case "workflow.stage": {
      const agent = stringValue(payload, "agent") ?? "workflow";
      const status = stringValue(payload, "status") ?? "updated";
      const action = result ? stringValue(result, "action") : null;
      const provider = result ? stringValue(result, "provider") : null;
      const amount = result ? stringValue(result, "amount") : null;
      return [agent, status, action, provider, amount ? `amount ${amount}` : null]
        .filter(Boolean)
        .join(" - ");
    }
    case "tool.call": {
      const localTool = stringValue(payload, "local_tool");
      const mcpTool = stringValue(payload, "mcp_tool");
      const provider = policyRetrieval
        ? stringValue(policyRetrieval, "provider")
        : null;
      const count = policyRetrieval ? stringValue(policyRetrieval, "count") : null;
      const orderId = order ? stringValue(order, "order_id") : null;
      return [
        localTool ?? "tool call",
        mcpTool ? `MCP ${mcpTool}` : null,
        provider,
        count ? `${count} evidence item(s)` : null,
        orderId,
      ]
        .filter(Boolean)
        .join(" - ");
    }
    case "checkpoint.created":
      return [
        "Checkpoint created",
        stringValue(payload, "reason"),
        stringValue(payload, "checkpoint_id"),
      ]
        .filter(Boolean)
        .join(" - ");
    case "hitl.request":
      return [
        stringValue(payload, "question") ?? "Human approval requested",
        stringValue(payload, "action"),
        stringValue(payload, "order_id"),
        stringValue(payload, "amount")
          ? `amount ${stringValue(payload, "amount")}`
          : null,
      ]
        .filter(Boolean)
        .join(" - ");
    case "hitl.response":
      return [
        `Decision ${stringValue(payload, "decision") ?? "recorded"}`,
        stringValue(payload, "reviewer"),
        stringValue(payload, "comments"),
      ]
        .filter(Boolean)
        .join(" - ");
    case "workflow.output":
      return [
        stringValue(payload, "message") ?? "Workflow output emitted",
        stringValue(payload, "status"),
      ]
        .filter(Boolean)
        .join(" - ");
    default:
      return (
        stringValue(payload, "status") ??
        stringValue(payload, "question") ??
        stringValue(payload, "message") ??
        stringValue(payload, "action") ??
        "Event emitted"
      );
  }
}

function stageName(event: WorkflowEvent): string {
  const payload = event.payload ?? {};
  const result = asRecord(payload.result);
  if (typeof payload.agent === "string") {
    return payload.agent;
  }
  if (event.type === "tool.call") {
    return "policy/tools";
  }
  if (event.type === "checkpoint.created") {
    return "checkpoint";
  }
  if (event.type === "hitl.request" || event.type === "hitl.response") {
    return "human review";
  }
  if (event.type === "workflow.output") {
    return "output";
  }
  if (typeof payload.action === "string") {
    return payload.action;
  }
  if (result && typeof result.action === "string") {
    return result.action;
  }
  return "workflow";
}

function metadataItems(event: WorkflowEvent): string[] {
  const payload = event.payload ?? {};
  const result = asRecord(payload.result);
  const order = asRecord(payload.order);
  const policyRetrieval = asRecord(payload.policy_retrieval);
  const items = [
    stringValue(payload, "checkpoint_id"),
    stringValue(payload, "order_id") ?? (order ? stringValue(order, "order_id") : null),
    stringValue(payload, "amount") ?? (order ? stringValue(order, "total_amount") : null),
    policyRetrieval ? stringValue(policyRetrieval, "query_id") : null,
    result ? stringValue(result, "query_id") : null,
  ];
  return items.filter((item): item is string => Boolean(item));
}

export default function TimelineEvent({ event }: Props) {
  return (
    <article className="timeline-event">
      <div className="timeline-marker" />
      <div className="timeline-card">
        <header>
          <time>{new Date(event.timestamp).toLocaleTimeString()}</time>
          <strong>{stageName(event)}</strong>
          <span className="event-badge">{event.type}</span>
        </header>
        <p className="event-summary">{summarizeEvent(event)}</p>
        {metadataItems(event).length > 0 ? (
          <div className="event-meta">
            {metadataItems(event).map((item) => (
              <code key={item}>{item}</code>
            ))}
          </div>
        ) : null}
        <details>
          <summary>Details</summary>
          <JsonViewer value={event.payload} emptyText="No payload details" />
        </details>
      </div>
    </article>
  );
}
