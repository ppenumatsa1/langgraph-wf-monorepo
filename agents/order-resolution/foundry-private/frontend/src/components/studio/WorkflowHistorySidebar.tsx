import PaginationControls from "./PaginationControls";
import StatusBadge from "./StatusBadge";
import type { WorkflowRunListItem, WorkflowStatus } from "../../types/workflow";

type Props = {
  runs: WorkflowRunListItem[];
  selectedThreadId: string | null;
  statusFilter: "all" | WorkflowStatus;
  searchTerm: string;
  page: number;
  pageSize: number;
  total: number;
  isLoading: boolean;
  error: string | null;
  onSelect: (threadId: string) => void;
  onStatusFilterChange: (value: "all" | WorkflowStatus) => void;
  onSearchChange: (value: string) => void;
  onPreviousPage: () => void;
  onNextPage: () => void;
};

const STATUS_OPTIONS: Array<{ label: string; value: "all" | WorkflowStatus }> =
  [
    { label: "All", value: "all" },
    { label: "Running", value: "running" },
    { label: "Waiting Approval", value: "waiting_approval" },
    { label: "Completed", value: "completed" },
    { label: "Failed", value: "failed" },
    { label: "Escalated", value: "escalated" },
  ];

function shortThreadId(threadId: string): string {
  if (threadId.length <= 10) {
    return threadId;
  }
  return `${threadId.slice(0, 8)}...${threadId.slice(-4)}`;
}

export default function WorkflowHistorySidebar({
  runs,
  selectedThreadId,
  statusFilter,
  searchTerm,
  page,
  pageSize,
  total,
  isLoading,
  error,
  onSelect,
  onStatusFilterChange,
  onSearchChange,
  onPreviousPage,
  onNextPage,
}: Props) {
  return (
    <aside className="panel sidebar-history">
      <header className="panel-head">
        <h2>Workflow History</h2>
      </header>

      <div className="history-filters">
        <input
          value={searchTerm}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search thread or input..."
        />
        <select
          value={statusFilter}
          onChange={(event) =>
            onStatusFilterChange(event.target.value as "all" | WorkflowStatus)
          }
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? <p className="muted">Loading workflow history...</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {!isLoading && !error && runs.length === 0 ? (
        <p className="muted">No workflows found.</p>
      ) : null}

      <div className="history-list">
        {runs.map((run) => (
          <button
            key={run.thread_id}
            type="button"
            className={`history-item ${selectedThreadId === run.thread_id ? "active" : ""}`}
            onClick={() => onSelect(run.thread_id)}
          >
            <div className="history-top">
              <strong>{shortThreadId(run.thread_id)}</strong>
              <StatusBadge status={run.status} />
            </div>
            <p>{run.input_summary}</p>
            <time>{new Date(run.created_at).toLocaleString()}</time>
          </button>
        ))}
      </div>

      <PaginationControls
        page={page}
        pageSize={pageSize}
        total={total}
        visibleCount={runs.length}
        isLoading={isLoading}
        onPrevious={onPreviousPage}
        onNext={onNextPage}
      />
    </aside>
  );
}
