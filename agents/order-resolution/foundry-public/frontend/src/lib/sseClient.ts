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

export function openThreadStream(
  apiBase: string,
  threadId: string,
  onEvent: (event: WorkflowEvent) => void,
): EventSource {
  const source = new EventSource(`${apiBase}/api/chat/stream/${threadId}`);
  source.onmessage = (msg) => {
    const parsed = JSON.parse(msg.data) as WorkflowEvent;
    onEvent(parsed);
  };
  return source;
}

export function openRichThreadStream(
  apiBase: string,
  threadId: string,
  onEvent: (event: RichWorkflowEventEnvelope) => void,
): EventSource {
  const source = new EventSource(`${apiBase}/api/chat/stream/${threadId}/rich`);
  source.addEventListener("workflow.rich", (msg) => {
    const parsed = JSON.parse(msg.data) as RichWorkflowEventEnvelope;
    onEvent(parsed);
  });
  return source;
}
