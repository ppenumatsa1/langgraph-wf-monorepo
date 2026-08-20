import type { WorkflowEvent } from "../../types/workflow";

type Props = {
  event: WorkflowEvent;
};

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

  switch (event.type) {
    case "workflow.stage": {
      const agent = stringValue(payload, "agent") ?? "workflow";
      const status = stringValue(payload, "status") ?? "updated";
      const action = stringValue(payload, "action");
      const amount = stringValue(payload, "amount");
      return [agent, status, action, amount ? `amount ${amount}` : null]
        .filter(Boolean)
        .join(" - ");
    }
    case "tool.call": {
      const count = stringValue(payload, "evidence_count");
      const orderId = stringValue(payload, "order_id");
      return [
        "Policy/tool activity",
        count ? `${count} evidence item(s)` : null,
        orderId,
      ]
        .filter(Boolean)
        .join(" - ");
    }
    case "checkpoint.created":
      return ["Checkpoint created", stringValue(payload, "reason")]
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
  if (typeof payload.agent === "string") {
    return payload.agent;
  }
  if (event.type === "tool.call") {
    return "policy activity";
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
  return "workflow";
}

function metadataItems(event: WorkflowEvent): string[] {
  const payload = event.payload ?? {};
  const items = [
    stringValue(payload, "order_id"),
    stringValue(payload, "amount"),
    stringValue(payload, "evidence_count"),
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
      </div>
    </article>
  );
}
