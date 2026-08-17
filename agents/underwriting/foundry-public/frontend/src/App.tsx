import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CopilotChat, useAgentContext } from '@copilotkit/react-core/v2'

import {
  getCheckpoints,
  getEvents,
  getRun,
  getRunHistory,
  getState,
  streamRun,
  type AGUIEvent,
  type RunHistoryItem,
  type UnderwritingApplication,
  type WorkflowCheckpointRecord,
  type WorkflowEventRecord,
  type WorkflowRunRecord,
  type WorkflowStateRow,
} from './api'
import { createSafeSelectedRunContext, underwritingCopilotRuntime } from './copilot'
import { ApplicationSection } from './components/ApplicationSection'
import { RunHistoryPanel } from './components/RunHistoryPanel'
import { RunRecoveryPanel, RunSummaryRail, RunTimeline } from './components/RunDataPanels'
import { ScenarioSection } from './components/ScenarioSection'

type Scenario = 'happy' | 'retry' | 'crash-medical'

const RUN_POLL_INTERVAL_MS = 2000
const RUN_RECENT_POLL_WINDOW_MS = 30000
const HISTORY_PAGE_SIZE = 10
const TERMINAL_STATUSES = new Set(['COMPLETED', 'CRASHED', 'FAILED'])

const defaultApplication: UnderwritingApplication = {
  application_id: `app-${Math.random().toString(16).slice(2, 10)}`,
  applicant_name: 'Ada Lovelace',
  age: 38,
  income: 145000,
  requested_coverage: 500000,
  health_disclosures: 'none',
  driving_history: 'clean',
  credit_score: 760,
}

function createRunId(): string {
  return `run-${crypto.randomUUID().replaceAll('-', '').slice(0, 10)}`
}

function App() {
  const [application, setApplication] = useState<UnderwritingApplication>(defaultApplication)
  const [scenario, setScenario] = useState<Scenario>('happy')
  const [runId, setRunId] = useState('')
  const [runInfo, setRunInfo] = useState<WorkflowRunRecord | null>(null)
  const [stateRows, setStateRows] = useState<WorkflowStateRow[]>([])
  const [events, setEvents] = useState<WorkflowEventRecord[]>([])
  const [checkpoints, setCheckpoints] = useState<WorkflowCheckpointRecord[]>([])
  const [history, setHistory] = useState<RunHistoryItem[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyOffset, setHistoryOffset] = useState(0)
  const [historySearch, setHistorySearch] = useState('')
  const [historyStatus, setHistoryStatus] = useState('')
  const [showNewRun, setShowNewRun] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isStreamingRun, setIsStreamingRun] = useState(false)
  const [streamEventCount, setStreamEventCount] = useState(0)
  const [lastRunActivityAt, setLastRunActivityAt] = useState<number | null>(null)

  const runIdRef = useRef(runId)
  const statusRef = useRef('IDLE')
  const lastRunActivityAtRef = useRef<number | null>(null)
  const pollInFlightRef = useRef(false)

  const currentStatus = String(runInfo?.status ?? (isStreamingRun && runId ? 'RUNNING' : 'IDLE'))
  const selectedRunAssistantContext = useMemo(
    () =>
      createSafeSelectedRunContext({
        runId: runId || null,
        status: currentStatus,
        events,
        checkpoints,
        stateRows,
      }),
    [checkpoints, currentStatus, events, runId, stateRows],
  )

  useAgentContext({
    description:
      'Safe metadata for the selected underwriting run. It contains only the run ID, status, event names and timing, executor names, checkpoint metadata, and an allowlisted categorical final decision.',
    value: selectedRunAssistantContext,
  })

  const refreshHistory = useCallback(async () => {
    const result = await getRunHistory({
      search: historySearch,
      status: historyStatus,
      limit: HISTORY_PAGE_SIZE,
      offset: 0,
    })
    setHistory(result.items)
    setHistoryTotal(result.total)
    setHistoryOffset(result.items.length)
  }, [historySearch, historyStatus])

  function selectHistoryProjection(item: RunHistoryItem): WorkflowRunRecord {
    return {
      id: item.workflow_run_id,
      application_id: item.application_id,
      applicant_name: item.applicant_name,
      status: item.status,
      created_at: item.created_at,
      updated_at: item.updated_at,
    }
  }

  const loadMoreHistory = useCallback(async () => {
    const result = await getRunHistory({
      search: historySearch,
      status: historyStatus,
      limit: HISTORY_PAGE_SIZE,
      offset: historyOffset,
    })
    setHistory((current) => [
      ...current,
      ...result.items.filter((item) => !current.some((existing) => existing.workflow_run_id === item.workflow_run_id)),
    ])
    setHistoryTotal(result.total)
    setHistoryOffset(historyOffset + result.items.length)
  }, [historyOffset, historySearch, historyStatus])

  async function refreshRunData(targetRunId: string) {
    const [run, state, ev, cp] = await Promise.all([
      getRun(targetRunId),
      getState(targetRunId),
      getEvents(targetRunId),
      getCheckpoints(targetRunId),
    ])
    if (runIdRef.current && runIdRef.current !== targetRunId) {
      return
    }
    setRunInfo(run)
    setStateRows(state)
    setEvents(
      [...ev].sort(
        (left, right) =>
          new Date(String(left.created_at ?? '')).getTime() -
          new Date(String(right.created_at ?? '')).getTime(),
      ),
    )
    setCheckpoints(
      [...cp].sort(
        (left, right) =>
          new Date(String(left.created_at ?? '')).getTime() -
          new Date(String(right.created_at ?? '')).getTime(),
      ),
    )
    const now = Date.now()
    setLastRunActivityAt(now)
    lastRunActivityAtRef.current = now
  }

  async function selectRun(item: RunHistoryItem) {
    setLoading(true)
    setError('')
    setShowNewRun(false)
    setIsStreamingRun(false)
    setStreamEventCount(0)
    setRunId(item.workflow_run_id)
    runIdRef.current = item.workflow_run_id
    setRunInfo(selectHistoryProjection(item))
    setStateRows([])
    setEvents([])
    setCheckpoints([])
    try {
      await refreshRunData(item.workflow_run_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  function appendStreamEvent(event: AGUIEvent) {
    if (event.type !== 'CUSTOM' || event.name !== 'underwriting.event') {
      return
    }
    const value = event.value
    if (!value || typeof value !== 'object') {
      return
    }
    const streamEvent = value as Record<string, unknown>
    const createdAt = String(streamEvent.createdAt ?? '')
    const eventType = String(streamEvent.eventType ?? 'event')
    const executorName = String(streamEvent.executorName ?? 'main')
    const workflowRunId = String(streamEvent.workflowRunId ?? runIdRef.current ?? '')
    const now = Date.now()
    setStreamEventCount((current) => current + 1)
    setLastRunActivityAt(now)
    lastRunActivityAtRef.current = now
    setEvents((current) => {
      const alreadyPresent = current.some(
        (item) =>
          item.created_at === createdAt &&
          item.event_type === eventType &&
          item.executor_name === executorName,
      )
      if (alreadyPresent) return current
      return [
        ...current,
        {
          id: `stream-${createdAt}-${eventType}-${executorName}`,
          workflow_run_id: workflowRunId,
          created_at: createdAt,
          event_type: eventType,
          executor_name: executorName,
          payload_json: {},
        },
      ]
    })
  }

  async function runWithStream(
    targetRunId: string,
    action: 'start' | 'resume',
    runApplication?: UnderwritingApplication,
  ) {
    setIsStreamingRun(true)
    setStreamEventCount(0)
    try {
      await streamRun(
        {
          workflowRunId: targetRunId,
          action,
          application: runApplication,
          failRiskOnce: scenario === 'retry',
          crashAfterExecutor: scenario === 'crash-medical' ? 'medical_check' : undefined,
        },
        appendStreamEvent,
      )
    } finally {
      setIsStreamingRun(false)
    }
  }

  async function handleStartRun() {
    const targetRunId = createRunId()
    const runApplication = {
      ...application,
      application_id: `app-${crypto.randomUUID().replaceAll('-', '').slice(0, 10)}`,
    }
    setApplication(runApplication)
    setLoading(true)
    setError('')
    setShowNewRun(false)
    setRunId(targetRunId)
    runIdRef.current = targetRunId
    const startedAt = new Date().toISOString()
    setRunInfo({
      id: targetRunId,
      application_id: runApplication.application_id,
      applicant_name: runApplication.applicant_name,
      status: 'RUNNING',
      created_at: startedAt,
      updated_at: startedAt,
    })
    setStateRows([])
    setEvents([])
    setCheckpoints([])
    try {
      await runWithStream(targetRunId, 'start', runApplication)
      await refreshRunData(targetRunId)
      await refreshHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      await refreshRunData(targetRunId).catch(() => undefined)
      await refreshHistory()
    } finally {
      setLoading(false)
    }
  }

  async function handleResume() {
    if (!runId) return
    setLoading(true)
    setError('')
    setRunInfo((current) => (current ? { ...current, status: 'RUNNING' } : current))
    try {
      await runWithStream(runId, 'resume')
      await refreshRunData(runId)
      await refreshHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      await refreshRunData(runId).catch(() => undefined)
      await refreshHistory()
    } finally {
      setLoading(false)
    }
  }

  async function handleRefresh() {
    if (!runId) return
    setLoading(true)
    setError('')
    try {
      await Promise.all([refreshRunData(runId), refreshHistory()])
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    runIdRef.current = runId
  }, [runId])

  useEffect(() => {
    statusRef.current = currentStatus
  }, [currentStatus])

  useEffect(() => {
    lastRunActivityAtRef.current = lastRunActivityAt
  }, [lastRunActivityAt])

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void refreshHistory().catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
    }, 150)
    return () => window.clearTimeout(timeout)
  }, [refreshHistory])

  useEffect(() => {
    if (!runId) return
    let isUnmounted = false
    const tick = async () => {
      if (isUnmounted || pollInFlightRef.current) return
      const activityAgeMs = Date.now() - (lastRunActivityAtRef.current ?? 0)
      const isActiveOrRecent =
        !TERMINAL_STATUSES.has(statusRef.current) || activityAgeMs <= RUN_RECENT_POLL_WINDOW_MS
      if (!isActiveOrRecent) return
      pollInFlightRef.current = true
      try {
        await refreshRunData(runId)
        await refreshHistory()
      } catch {
        // Durable history is refreshed when the user reconnects or explicitly refreshes.
      } finally {
        pollInFlightRef.current = false
      }
    }
    void tick()
    const intervalId = window.setInterval(() => void tick(), RUN_POLL_INTERVAL_MS)
    return () => {
      isUnmounted = true
      window.clearInterval(intervalId)
      pollInFlightRef.current = false
    }
  }, [refreshHistory, runId])

  return (
    <div className="container operations-shell">
      <header className="app-header">
        <div>
          <span className="eyebrow">LangGraph insurance operations</span>
          <h1>Underwriting Workflow Runs</h1>
          <p className="subtitle">
            Track Responses 2.0 executions, inspect four-check fan-in progress, and recover durable checkpoints without leaving the selected run.
          </p>
        </div>
        <div className="header-actions">
          <span className={`status-chip status-${currentStatus.toLowerCase()}`}>{currentStatus}</span>
          <span className="meta-chip">Selected run: {runId || 'None'}</span>
        </div>
      </header>

      {error ? (
        <section className="card error-card" role="alert">
          <strong>Unable to complete the requested action</strong>
          <p data-testid="error">{error}</p>
        </section>
      ) : null}

      <main className="operations-layout">
        <aside className="operations-history">
          <section className="new-run-panel new-run-dropdown">
            <div className="panel-header">
              <div>
                <span className="panel-kicker">New LangGraph run</span>
                <h2>Start underwriting workflow</h2>
              </div>
              <button
                type="button"
                className="button-secondary"
                aria-expanded={showNewRun}
                onClick={() => setShowNewRun((current) => !current)}
              >
                {showNewRun ? 'Minimize' : 'New underwriting run'}
              </button>
            </div>
            {showNewRun ? (
              <>
                <ScenarioSection scenario={scenario} onChange={setScenario} />
                <ApplicationSection application={application} onChange={setApplication} />
                <button data-testid="start-run" type="button" onClick={() => void handleStartRun()} disabled={loading}>
                  Start run
                </button>
              </>
            ) : null}
          </section>
          <RunHistoryPanel
            items={history}
            total={historyTotal}
            hasMore={history.length < historyTotal}
            selectedRunId={runId}
            search={historySearch}
            status={historyStatus}
            loading={loading}
            onSearchChange={setHistorySearch}
            onStatusChange={setHistoryStatus}
            onSelectRun={(targetRunId) => {
              const selectedItem = history.find((item) => item.workflow_run_id === targetRunId)
              if (selectedItem) {
                void selectRun(selectedItem)
              }
            }}
            onLoadMore={() => void loadMoreHistory()}
            onRefresh={() => void refreshHistory()}
          />
        </aside>

        <section className="operations-center">
          <RunTimeline
            runId={runId}
            events={events}
            onRefresh={() => void handleRefresh()}
            loading={loading}
            isStreaming={isStreamingRun}
            streamedEventCount={streamEventCount}
          />
          <RunRecoveryPanel
            currentStatus={currentStatus}
            stateRows={stateRows}
            events={events}
            checkpoints={checkpoints}
            onResume={() => void handleResume()}
            loading={loading}
          />
          <section className="card assistant-panel" aria-labelledby="copilot-assistant-title" data-testid="copilot-assistant">
            <div className="panel-header">
              <div>
                <span className="panel-kicker">Selected-run assistant</span>
                <h2 id="copilot-assistant-title">Ask about the selected execution</h2>
                <p className="panel-subtitle">
                  Uses the strict selected-run allowlist: status, safe event metadata, checkpoint progress, and the categorical final decision when available.
                </p>
              </div>
            </div>
            <CopilotChat
              agentId={underwritingCopilotRuntime.agentId}
              className="underwriting-copilot-chat"
              labels={{
                chatInputPlaceholder: 'Ask about this run',
                welcomeMessageText:
                  'I can explain the selected run using allowlisted status, event, checkpoint, and final-decision metadata only.',
              }}
            />
          </section>
        </section>

        <RunSummaryRail
          runId={runId}
          currentStatus={currentStatus}
          runInfo={runInfo}
          stateRows={stateRows}
          events={events}
          checkpoints={checkpoints}
        />
      </main>
    </div>
  )
}

export default App
