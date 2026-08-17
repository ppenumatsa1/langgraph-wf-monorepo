import type { WorkflowCheckpointRecord, WorkflowEventRecord, WorkflowStateRow } from './api'
import { apiBaseUrl } from './api'

const MAX_ASSISTANT_EVENTS = 100

const SAFE_STATUSES = new Set([
  'IDLE',
  'IN_PROGRESS',
  'RUNNING',
  'COMPLETED',
  'CRASHED',
  'FAILED',
])

const SAFE_DECISIONS = new Set([
  'APPROVE',
  'APPROVED',
  'DECLINE',
  'DECLINED',
  'PENDING',
  'REFER',
  'REFERRED',
  'MANUAL_REVIEW',
])

export const underwritingCopilotRuntime = {
  agentId: 'underwriting-run-assistant',
  credentials: 'omit' as RequestCredentials,
  runtimeUrl: `${apiBaseUrl}/api/v1/underwriting/copilotkit`,
} as const

export type UnderwritingCopilotRuntimeContract = typeof underwritingCopilotRuntime

export type SafeSelectedRunContext = {
  runId: string | null
  status: string
  events: Array<{
    name: string
    timestamp: string | null
    executor: string | null
  }>
  checkpoints: {
    count: number
    latestCreatedAt: string | null
  }
  output: {
    finalDecision: string | null
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function safeIdentifier(value: unknown): string | null {
  return typeof value === 'string' && /^[a-zA-Z0-9_-]{1,128}$/.test(value)
    ? value
    : null
}

function safeTimestamp(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const timestamp = new Date(value)
  return Number.isNaN(timestamp.getTime()) ? null : timestamp.toISOString()
}

function safeStatus(value: string): string {
  const normalized = value.toUpperCase()
  return SAFE_STATUSES.has(normalized) ? normalized : 'UNKNOWN'
}

function selectedRunDecision(stateRows: WorkflowStateRow[]): string | null {
  const persistedDecision = asRecord(
    stateRows.find((row) => row.state_key === 'final_decision')?.state_json,
  )
  const decision = persistedDecision?.decision
  return typeof decision === 'string' && SAFE_DECISIONS.has(decision.toUpperCase())
    ? decision.toUpperCase()
    : null
}

function latestCheckpointTimestamp(checkpoints: WorkflowCheckpointRecord[]): string | null {
  return checkpoints.reduce<string | null>((latest, checkpoint) => {
    const timestamp = safeTimestamp(checkpoint.created_at)
    return timestamp && (!latest || timestamp > latest) ? timestamp : latest
  }, null)
}

export function createSafeSelectedRunContext({
  runId,
  status,
  events,
  checkpoints,
  stateRows,
}: {
  runId: string | null
  status: string
  events: WorkflowEventRecord[]
  checkpoints: WorkflowCheckpointRecord[]
  stateRows: WorkflowStateRow[]
}): SafeSelectedRunContext {
  return {
    runId: safeIdentifier(runId),
    status: safeStatus(status),
    events: events.slice(-MAX_ASSISTANT_EVENTS).flatMap((event) => {
      const name = safeIdentifier(event.event_type)
      return name
        ? [{
            name,
            timestamp: safeTimestamp(event.created_at),
            executor: safeIdentifier(event.executor_name),
          }]
        : []
    }),
    checkpoints: {
      count: checkpoints.length,
      latestCreatedAt: latestCheckpointTimestamp(checkpoints),
    },
    output: {
      finalDecision: selectedRunDecision(stateRows),
    },
  }
}
