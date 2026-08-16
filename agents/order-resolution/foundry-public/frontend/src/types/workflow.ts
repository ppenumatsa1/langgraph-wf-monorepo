export type WorkflowStatus =
  | "running"
  | "waiting_approval"
  | "completed"
  | "failed"
  | "escalated";

export type WorkflowEvent = {
  id: string;
  type: string;
  thread_id: string;
  timestamp: string;
  payload: Record<string, unknown>;
};

export type RichWorkflowEventEnvelope = {
  type: "workflow.rich";
  version: "ag-ui-compatible.v1";
  id: string;
  thread_id: string;
  timestamp: string;
  source: "langgraph-order-resolution";
  native_event: WorkflowEvent;
  events: Array<Record<string, unknown>>;
};

export type WorkflowRunListItem = {
  thread_id: string;
  status: WorkflowStatus;
  input_summary: string;
  created_at: string;
  updated_at: string;
};

export type WorkflowRunListResponse = {
  items: WorkflowRunListItem[];
  page: number;
  page_size: number;
  total: number;
};

export type PendingApproval = {
  approval_id: string;
  checkpoint_id: string;
  action?: string | null;
  order_id?: string | null;
  amount?: number | null;
  question?: string | null;
  reviewer?: string | null;
  comments?: string | null;
  status: "pending" | "approved" | "rejected";
  requested_at: string;
  resolved_at?: string | null;
};

export type WorkflowMetadata = {
  thread_id: string;
  status: WorkflowStatus;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  current_stage?: string | null;
};

export type WorkflowRunDetails = {
  thread_id: string;
  status: WorkflowStatus;
  input: string;
  events: WorkflowEvent[];
  pending_approvals: PendingApproval[];
  latest_output: Record<string, unknown> | null;
  metadata: WorkflowMetadata;
};
