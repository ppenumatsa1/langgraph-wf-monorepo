import type { RunHistoryItem } from '../api'

type Props = {
  items: RunHistoryItem[]
  total: number
  hasMore: boolean
  selectedRunId: string
  search: string
  status: string
  loading: boolean
  onSearchChange: (value: string) => void
  onStatusChange: (value: string) => void
  onSelectRun: (runId: string) => void
  onLoadMore: () => void
  onRefresh: () => void
}

function formatDate(value: string): string {
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`
  const date = new Date(normalized)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        timeZoneName: 'short',
      })
}

export function RunHistoryPanel({
  items,
  total,
  hasMore,
  selectedRunId,
  search,
  status,
  loading,
  onSearchChange,
  onStatusChange,
  onSelectRun,
  onLoadMore,
  onRefresh,
}: Props) {
  return (
    <section className="history-panel">
      <div className="panel-header">
        <div>
          <span className="panel-kicker">Workflow runs</span>
          <h2>Underwriting Run History</h2>
        </div>
        <button type="button" className="button-secondary button-icon" onClick={onRefresh} disabled={loading}>
          Refresh
        </button>
      </div>
      <label className="field">
        Search runs
        <input
          data-testid="history-search"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Run ID, application ID, or applicant"
        />
      </label>
      <label className="field">
        Status
        <select data-testid="history-status-filter" value={status} onChange={(event) => onStatusChange(event.target.value)}>
          <option value="">All statuses</option>
          <option value="COMPLETED">Completed</option>
          <option value="CRASHED">Needs recovery</option>
          <option value="RUNNING">Running</option>
        </select>
      </label>
      <p className="history-count">{total} run{total === 1 ? '' : 's'} • newest first</p>
      <div className="history-list" aria-label="Underwriting run history">
        {items.length === 0 ? (
          <p className="history-empty">No underwriting runs match this view.</p>
        ) : (
          items.map((item) => (
            <button
              key={item.workflow_run_id}
              type="button"
              data-testid={`history-run-${item.workflow_run_id}`}
              className={`history-run ${item.workflow_run_id === selectedRunId ? 'history-run-selected' : ''}`}
              onClick={() => onSelectRun(item.workflow_run_id)}
            >
              <span className="history-run-topline">
                <strong>{item.applicant_name}</strong>
                <span className={`status-chip status-${item.status.toLowerCase()}`}>{item.status}</span>
              </span>
              <span>{item.application_id}</span>
              <span className="history-run-meta">
                {item.final_decision ?? (item.resumable ? 'Recovery available' : 'In progress')} • {formatDate(item.created_at)}
              </span>
            </button>
          ))
        )}
      </div>
      {hasMore ? (
        <button type="button" className="button-secondary history-load-more" onClick={onLoadMore} disabled={loading}>
          Load 10 more
        </button>
      ) : null}
    </section>
  )
}
