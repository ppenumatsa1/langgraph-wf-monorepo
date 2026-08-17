import { getCopilotKitEndpoint, getInitialApiBase } from "./config";
import type {
  PendingApproval,
  WorkflowEvent,
  WorkflowRunDetails,
  WorkflowStatus,
} from "./types/workflow";

const MAX_ASSISTANT_EVENTS = 100;
const SAFE_EVENT_TYPE = /^[a-zA-Z0-9._:-]{1,128}$/;
const SAFE_THREAD_ID = /^[a-zA-Z0-9._:-]{1,128}$/;

const SAFE_STATUSES = new Set<WorkflowStatus>([
  "running",
  "waiting_approval",
  "completed",
  "failed",
  "escalated",
]);

export const orderResolutionCopilotRuntime = {
  agentId: "order-resolution-thread-assistant",
  credentials: "omit" as RequestCredentials,
  runtimeUrl: getCopilotKitEndpoint(getInitialApiBase()),
} as const;

export type SafeSelectedThreadContext = {
  threadId: string | null;
  status: WorkflowStatus | "unknown";
  events: Array<{
    type: string;
    timestamp: string | null;
  }>;
  approvals: {
    pendingCount: number;
  };
  workflow: {
    hasOutput: boolean;
  };
};

function safeThreadId(value: string | null): string | null {
  return value && SAFE_THREAD_ID.test(value) ? value : null;
}

function safeStatus(value: string | null | undefined): WorkflowStatus | "unknown" {
  return value && SAFE_STATUSES.has(value as WorkflowStatus)
    ? (value as WorkflowStatus)
    : "unknown";
}

function safeTimestamp(value: string): string | null {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

function safeEvents(events: WorkflowEvent[]): SafeSelectedThreadContext["events"] {
  return events.slice(-MAX_ASSISTANT_EVENTS).flatMap((event) => {
    if (!SAFE_EVENT_TYPE.test(event.type)) {
      return [];
    }
    return [{ type: event.type, timestamp: safeTimestamp(event.timestamp) }];
  });
}

export function createSafeSelectedThreadContext({
  threadId,
  details,
  events,
  approvals,
}: {
  threadId: string | null;
  details: WorkflowRunDetails | null;
  events: WorkflowEvent[];
  approvals: PendingApproval[];
}): SafeSelectedThreadContext {
  return {
    threadId: safeThreadId(threadId),
    status: safeStatus(details?.status),
    events: safeEvents(events),
    approvals: {
      pendingCount: approvals.filter((approval) => approval.status === "pending").length,
    },
    workflow: {
      hasOutput: Boolean(details?.latest_output),
    },
  };
}
