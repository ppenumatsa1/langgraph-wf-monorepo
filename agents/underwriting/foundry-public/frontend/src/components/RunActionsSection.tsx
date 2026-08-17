type Props = {
  loading: boolean
  runId: string
  resumeId: string
  onResumeIdChange: (value: string) => void
  onStart: () => void
  onResume: () => void
  onRefresh: () => void
}

export function RunActionsSection({
  loading,
  runId,
  resumeId,
  onResumeIdChange,
  onStart,
  onResume,
  onRefresh,
}: Props) {
  return (
    <section className="card run-actions-card actions">
      <button data-testid="start-run" onClick={onStart} disabled={loading}>
        Start Run
      </button>
      <label className="field">
        Resume run id
        <input
          data-testid="resume-id"
          value={resumeId}
          onChange={(e) => onResumeIdChange(e.target.value)}
          placeholder="run-..."
        />
      </label>
      <button data-testid="resume-run" onClick={onResume} disabled={loading || !resumeId}>
        Resume
      </button>
      <button data-testid="refresh-run" onClick={onRefresh} disabled={loading || !runId}>
        Refresh State/Events
      </button>
    </section>
  )
}
