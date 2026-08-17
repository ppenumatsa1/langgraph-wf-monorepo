import type {
  WorkflowCheckpointRecord,
  WorkflowEventRecord,
  WorkflowRunRecord,
  WorkflowStateRow,
} from '../api'

type RunData = {
  runId: string | null
  currentStatus: string
  runInfo: WorkflowRunRecord | null
  stateRows: WorkflowStateRow[]
  events: WorkflowEventRecord[]
  checkpoints: WorkflowCheckpointRecord[]
}

type TimelineProps = Pick<RunData, 'runId' | 'events'> & {
  onRefresh: () => void
  loading: boolean
  isStreaming: boolean
  streamedEventCount: number
}

type RecoveryProps = Pick<RunData, 'currentStatus' | 'stateRows' | 'events' | 'checkpoints'> & {
  onResume: () => void
  loading: boolean
}

type SummaryProps = RunData

type TimelineTone = 'started' | 'completed' | 'failed' | 'retrying' | 'cached' | 'info'

function valueAsObject(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {}
}

function businessLabel(value: string): string {
  const labels: Record<string, string> = {
    main: 'Underwriting',
    init_context: 'Prepare application',
    risk_score: 'Risk assessment',
    credit_check: 'Credit assessment',
    medical_check: 'Medical assessment',
    driving_check: 'Driving assessment',
    fan_in_aggregator: 'Aggregate checks',
    final_decision: 'Make decision',
  }
  return labels[value] ?? value.replace(/_/g, ' ')
}

function eventSummary(event: WorkflowEventRecord): {
  title: string
  description: string
  tone: TimelineTone
} {
  const eventType = String(event.event_type ?? 'event')
  const executor = businessLabel(String(event.executor_name ?? 'main'))
  const payload = valueAsObject(event.payload_json)
  const decision = payload.decision ? `Decision: ${String(payload.decision)}` : ''
  const attempt = payload.attempt ? `Attempt ${String(payload.attempt)}` : ''
  const summaries: Record<string, [string, TimelineTone]> = {
    workflow_start: ['Run started', 'started'],
    init_context: ['Application prepared', 'completed'],
    retry_attempt: [attempt || 'Check started', 'started'],
    retry_backoff: [attempt ? `Retry scheduled (${attempt})` : 'Retry scheduled', 'retrying'],
    retry_exhausted: ['Check failed after retry', 'failed'],
    check_completed: ['Check completed', 'completed'],
    fan_in_result_received: ['Check result received', 'info'],
    final_decision: [decision || 'Decision completed', 'completed'],
    workflow_completed: ['Run completed', 'completed'],
    workflow_crashed: ['Run stopped and can be recovered', 'failed'],
    resume_requested: ['Recovery started from checkpoint', 'started'],
    resume_completed: ['Recovery completed', 'completed'],
    idempotency_skip: ['Previously completed result reused', 'cached'],
  }
  const [description, tone] = summaries[eventType] ?? [eventType.replace(/_/g, ' '), 'info']
  return { title: executor, description, tone }
}

function formatTime(value: unknown): string {
  const raw = String(value ?? '')
  const date = new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(raw) ? raw : `${raw}Z`)
  return Number.isNaN(date.getTime())
    ? 'Time unavailable'
    : date.toLocaleTimeString([], {
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        timeZoneName: 'short',
      })
}

function formatDateTime(value: unknown): string {
  const raw = String(value ?? '')
  const date = new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(raw) ? raw : `${raw}Z`)
  return Number.isNaN(date.getTime())
    ? 'Not available'
    : date.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        timeZoneName: 'short',
      })
}

function JsonDetails({ title, testId, value }: { title: string; testId: string; value: unknown }) {
  return (
    <details className="technical-details">
      <summary>{title}</summary>
      <pre data-testid={testId}>{JSON.stringify(value, null, 2)}</pre>
    </details>
  )
}

export function RunTimeline({
  runId,
  events,
  onRefresh,
  loading,
  isStreaming,
  streamedEventCount,
}: TimelineProps) {
  const orderedEvents = [...events].sort((left, right) => {
    const leftTime = new Date(String(left.created_at ?? '')).getTime()
    const rightTime = new Date(String(right.created_at ?? '')).getTime()
    return leftTime - rightTime
  })
  const retryEventCount = events.filter((event) => String(event.event_type).startsWith('retry_')).length
  const idempotencySkipCount = events.filter((event) => String(event.event_type) === 'idempotency_skip').length

  return (
    <section className="card timeline-panel">
      <div className="panel-header">
        <div>
          <span className="panel-kicker">Execution</span>
          <h2>Event Timeline</h2>
          <p className="panel-subtitle">
            AG-UI updates mirror the durable underwriting timeline in execution order.
          </p>
        </div>
        <div className="timeline-toolbar">
          <span
            className={`meta-chip ${isStreaming ? 'meta-chip-live' : ''}`}
            data-testid="agui-stream-status"
          >
            {isStreaming ? `AG-UI live • ${streamedEventCount}` : 'AG-UI idle'}
          </span>
          <button type="button" className="button-secondary" onClick={onRefresh} disabled={loading || !runId}>
            Refresh
          </button>
        </div>
      </div>
      <div className="event-counters">
        <div data-testid="retry-event-count" className="summary-item">
          <span>Retries</span>
          <strong>{retryEventCount}</strong>
        </div>
        <div data-testid="idempotency-skip-count" className="summary-item">
          <span>Reused results</span>
          <strong>{idempotencySkipCount}</strong>
        </div>
      </div>
      <div className="events-timeline" aria-label="Chronological event timeline">
        {orderedEvents.length === 0 ? (
          <div className="timeline-empty">Choose a workflow run or start a new one to see execution details.</div>
        ) : (
          orderedEvents.map((event, index) => {
            const summary = eventSummary(event)
            return (
              <article className="timeline-event" data-testid="timeline-event" key={`${String(event.id ?? index)}-${String(event.event_type)}`}>
                <span className={`timeline-dot timeline-dot-${summary.tone}`} />
                <div className="timeline-content">
                  <div className="timeline-title-row">
                    <span className="timeline-time">{formatTime(event.created_at)}</span>
                    <strong>{summary.title}</strong>
                    <span className={`timeline-badge timeline-badge-${summary.tone}`}>{summary.tone}</span>
                  </div>
                  <p className="timeline-meta">{summary.description}</p>
                  <details className="event-details">
                    <summary>Technical event details</summary>
                    <pre>{JSON.stringify(event, null, 2)}</pre>
                  </details>
                </div>
              </article>
            )
          })
        )}
      </div>
      <JsonDetails title="Technical event log" testId="events-json" value={events} />
    </section>
  )
}

export function RunRecoveryPanel({
  currentStatus,
  stateRows,
  events,
  checkpoints,
  onResume,
  loading,
}: RecoveryProps) {
  const context = valueAsObject(stateRows.find((row) => row.state_key === 'underwriting_context')?.state_json)
  const aggregation = valueAsObject(stateRows.find((row) => row.state_key === 'aggregation_state')?.state_json)
  const completedChecks = Array.isArray(aggregation.completed_checks)
    ? aggregation.completed_checks.map(String)
    : Array.isArray(context.completed_checks)
      ? context.completed_checks.map(String)
      : []
  const expectedChecks = Array.isArray(aggregation.expected_checks)
    ? aggregation.expected_checks.map(String)
    : Array.isArray(context.expected_checks)
      ? context.expected_checks.map(String)
      : ['risk', 'credit', 'medical', 'driving']
  const status = currentStatus
  const latestCheckpoint = checkpoints.at(-1)
  const failed = events.some((event) =>
    ['workflow_crashed', 'retry_exhausted'].includes(String(event.event_type)),
  )
  const resumable = status === 'CRASHED' && checkpoints.length > 0

  return (
    <section className="card recovery-panel">
      <div className="panel-header">
        <div>
          <span className="panel-kicker">State and recovery</span>
          <h2>Run Progress</h2>
        </div>
        <span className={`status-chip status-${status.toLowerCase()}`}>{status}</span>
      </div>
      <div className="progress-summary">
        <div>
          <span>Completed checks</span>
          <strong data-testid="fanin-completed-checks">
            {completedChecks.length} of {expectedChecks.length}
            {completedChecks.length ? ` • ${completedChecks.join(', ')}` : ''}
          </strong>
        </div>
        <div>
          <span>Latest LangGraph checkpoint</span>
          <strong>{latestCheckpoint ? formatDateTime(latestCheckpoint.created_at) : 'Not created yet'}</strong>
        </div>
      </div>
      <div className="check-grid">
        {expectedChecks.map((check) => (
          <span className={`check-pill ${completedChecks.includes(check) ? 'check-pill-complete' : 'check-pill-pending'}`} key={check}>
            {completedChecks.includes(check) ? 'Completed' : failed ? 'Not completed' : 'Pending'} • {businessLabel(`${check}_check`)}
          </span>
        ))}
      </div>
      <div className="recovery-action">
        <div>
          <strong>{resumable ? 'Recovery is ready' : 'Recovery status'}</strong>
          <p>
            {resumable
              ? `Resume from checkpoint ${String(latestCheckpoint?.checkpoint_id ?? '').slice(0, 8)} without rerunning completed work.`
              : checkpoints.length
                ? 'The run is complete or still active; recovery is not needed.'
                : 'A durable LangGraph checkpoint will appear after the workflow starts.'}
          </p>
        </div>
        <button data-testid="resume-run" type="button" onClick={onResume} disabled={loading || !resumable}>
          Resume run
        </button>
      </div>
      <div className="recovery-metrics">
        <span data-testid="checkpoint-count">Checkpoints: {checkpoints.length}</span>
        <span>{failed ? 'Attention required' : 'No recovery issue detected'}</span>
      </div>
      <JsonDetails title="Technical shared state" testId="state-json" value={stateRows} />
      <JsonDetails title="Technical checkpoints" testId="checkpoints-json" value={checkpoints} />
    </section>
  )
}

export function RunSummaryRail({
  runId,
  currentStatus,
  runInfo,
  stateRows,
  events,
  checkpoints,
}: SummaryProps) {
  const status = currentStatus
  const context = valueAsObject(stateRows.find((row) => row.state_key === 'underwriting_context')?.state_json)
  const persistedDecision = valueAsObject(stateRows.find((row) => row.state_key === 'final_decision')?.state_json)
  const decision = persistedDecision.decision ?? 'Pending'
  const rationale = persistedDecision.rationale
  const scoreBreakdown = valueAsObject(persistedDecision.score_breakdown)

  return (
    <aside className="summary-rail-layout">
      <section className="card decision-panel">
        <div className="panel-header">
          <div>
            <span className="panel-kicker">Decision</span>
            <h2>Underwriting Outcome</h2>
          </div>
          <span className={`status-chip status-${status.toLowerCase()}`}>{status}</span>
        </div>
        <div className="decision-value">{String(decision)}</div>
        {rationale ? <p className="decision-rationale">{String(rationale)}</p> : <p className="decision-rationale">The final rationale appears when the decision completes.</p>}
        {Object.keys(scoreBreakdown).length ? (
          <div className="score-breakdown">
            {Object.entries(scoreBreakdown).map(([check, score]) => (
              <div key={check}>
                <span>{businessLabel(`${check}_check`)}</span>
                <strong>{typeof score === 'number' ? score.toFixed(2) : String(score)}</strong>
              </div>
            ))}
          </div>
        ) : null}
      </section>
      <section className="card application-panel">
        <div className="panel-header">
          <div>
            <span className="panel-kicker">Application</span>
            <h2>Run Details</h2>
          </div>
        </div>
        <div data-testid="run-id" className="detail-row">
          <span>Run ID</span>
          <strong>{runId || 'None selected'}</strong>
        </div>
        <div data-testid="run-status" className="detail-row">
          <span>Status</span>
          <strong>{status}</strong>
        </div>
        <div className="detail-row">
          <span>Applicant</span>
          <strong>{String(context.applicant_name ?? runInfo?.applicant_name ?? 'Not available')}</strong>
        </div>
        <div className="detail-row">
          <span>Application ID</span>
          <strong>{String(context.application_id ?? runInfo?.application_id ?? 'Not available')}</strong>
        </div>
        <div className="detail-row">
          <span>Requested coverage</span>
          <strong>{context.requested_coverage ? `$${Number(context.requested_coverage).toLocaleString()}` : 'Not available'}</strong>
        </div>
        <div className="detail-row">
          <span>Events / checkpoints</span>
          <strong>{events.length} / {checkpoints.length}</strong>
        </div>
      </section>
      <section className="card output-panel">
        <span className="panel-kicker">Technical output</span>
        <JsonDetails title="Persisted final decision output" testId="run-outputs" value={persistedDecision} />
      </section>
    </aside>
  )
}
