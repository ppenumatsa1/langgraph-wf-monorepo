import type {
  PendingApproval,
  WorkflowEvent,
  WorkflowRunDetails,
} from "../types/workflow";

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function stringValue(record: Record<string, unknown> | null, key: string): string | null {
  const value = record?.[key];
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
}

function numberValue(record: Record<string, unknown> | null, key: string): number | null {
  const value = record?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function setIfPresent(
  target: Record<string, unknown>,
  key: string,
  value: string | number | null,
): void {
  if (value !== null) {
    target[key] = value;
  }
}

function outputProjection(output: Record<string, unknown> | null): Record<string, unknown> | null {
  if (!output) {
    return null;
  }

  const proposedAction = asRecord(output.proposed_action);
  const safe: Record<string, unknown> = {};
  setIfPresent(safe, "message", stringValue(output, "message"));
  setIfPresent(safe, "status", stringValue(output, "status"));
  setIfPresent(
    safe,
    "action",
    stringValue(output, "action") ?? stringValue(proposedAction, "action"),
  );
  setIfPresent(
    safe,
    "order_id",
    stringValue(output, "order_id") ?? stringValue(proposedAction, "order_id"),
  );
  setIfPresent(
    safe,
    "amount",
    numberValue(output, "amount") ?? numberValue(proposedAction, "amount"),
  );
  setIfPresent(
    safe,
    "decision",
    stringValue(output, "decision"),
  );
  setIfPresent(safe, "submission_id", stringValue(output, "submission_id"));

  return Object.keys(safe).length > 0 ? safe : { status: "available" };
}

function evidenceCount(payload: Record<string, unknown>): number | null {
  return numberValue(payload, "evidence_count");
}

function eventPayloadProjection(event: WorkflowEvent): Record<string, unknown> {
  const payload = event.payload ?? {};
  const safe: Record<string, unknown> = {};

  switch (event.type) {
    case "workflow.stage":
      setIfPresent(safe, "agent", stringValue(payload, "agent"));
      setIfPresent(safe, "status", stringValue(payload, "status"));
      setIfPresent(safe, "action", stringValue(payload, "action"));
      setIfPresent(safe, "amount", numberValue(payload, "amount"));
      break;
    case "tool.call":
      setIfPresent(safe, "status", stringValue(payload, "status"));
      setIfPresent(safe, "evidence_count", evidenceCount(payload));
      setIfPresent(safe, "order_id", stringValue(payload, "order_id"));
      break;
    case "checkpoint.created":
      setIfPresent(safe, "reason", stringValue(payload, "reason"));
      break;
    case "hitl.request":
      setIfPresent(safe, "question", stringValue(payload, "question"));
      setIfPresent(safe, "action", stringValue(payload, "action"));
      setIfPresent(safe, "order_id", stringValue(payload, "order_id"));
      setIfPresent(safe, "amount", numberValue(payload, "amount"));
      break;
    case "hitl.response":
      setIfPresent(safe, "decision", stringValue(payload, "decision"));
      setIfPresent(safe, "reviewer", stringValue(payload, "reviewer"));
      setIfPresent(safe, "comments", stringValue(payload, "comments"));
      break;
    case "workflow.output":
      setIfPresent(safe, "message", stringValue(payload, "message"));
      setIfPresent(safe, "status", stringValue(payload, "status"));
      break;
    default:
      setIfPresent(safe, "status", stringValue(payload, "status"));
  }

  return safe;
}

function approvalProjection(approval: PendingApproval): PendingApproval {
  return {
    approval_id: approval.approval_id,
    checkpoint_id: approval.checkpoint_id,
    action: approval.action ?? null,
    order_id: approval.order_id ?? null,
    amount: approval.amount ?? null,
    question: approval.question ?? null,
    status: approval.status,
    requested_at: approval.requested_at,
    resolved_at: approval.resolved_at ?? null,
    reviewer: null,
    comments: null,
  };
}

export function redactWorkflowEvent(event: WorkflowEvent): WorkflowEvent {
  return {
    id: event.id,
    type: event.type,
    thread_id: event.thread_id,
    timestamp: event.timestamp,
    payload: eventPayloadProjection(event),
  };
}

export function redactWorkflowRunDetails(
  details: WorkflowRunDetails,
): WorkflowRunDetails {
  return {
    thread_id: details.thread_id,
    status: details.status,
    input: "",
    events: details.events.map(redactWorkflowEvent),
    pending_approvals: details.pending_approvals.map(approvalProjection),
    latest_output: outputProjection(details.latest_output),
    metadata: {
      thread_id: details.metadata.thread_id,
      status: details.metadata.status,
      started_at: details.metadata.started_at ?? null,
      completed_at: details.metadata.completed_at ?? null,
      duration_ms: details.metadata.duration_ms ?? null,
      current_stage: details.metadata.current_stage ?? null,
    },
  };
}
