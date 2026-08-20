import type { WorkflowStatus } from "../../types/workflow";

type Props = {
  status: WorkflowStatus;
};

const LABELS: Record<WorkflowStatus, string> = {
  running: "Running",
  waiting_approval: "Waiting Approval",
  completed: "Completed",
  failed: "Failed",
  escalated: "Escalated",
};

export default function StatusBadge({ status }: Props) {
  return (
    <span className={`status-badge status-${status}`}>{LABELS[status]}</span>
  );
}
