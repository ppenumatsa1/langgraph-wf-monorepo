export const USECASE_RUBRIC = [
  {
    id: 'happy-path-decision',
    description: 'Happy path run completes and final decision is visible',
  },
  {
    id: 'retry-behavior',
    description: 'Retry scenario records retry events and still completes',
  },
  {
    id: 'crash-state',
    description: 'Crash scenario produces a crashed run with resumable run id',
  },
  {
    id: 'resume-from-checkpoint',
    description: 'Resume scenario completes from a stored LangGraph-style PostgreSQL checkpoint projection',
  },
  {
    id: 'fanin-state',
    description: 'Fan-in shared state contains all required child check results before final decision',
  },
  {
    id: 'checkpoint-listing',
    description: 'Checkpoint endpoint shows checkpoint ids for the selected run',
  },
  {
    id: 'idempotency-skip',
    description: 'Resume/replay path surfaces idempotency skip events (no duplicate side effects)',
  },
  {
    id: 'observability-fields',
    description: 'Event payload includes workflow and executor observability context',
  },
] as const

export type RubricResultMap = Record<(typeof USECASE_RUBRIC)[number]['id'], boolean>

export function scoreRubric(results: RubricResultMap): { passed: number; total: number; failed: string[] } {
  const failed = USECASE_RUBRIC.filter((criterion) => !results[criterion.id]).map(
    (criterion) => `${criterion.id}: ${criterion.description}`,
  )
  return {
    passed: USECASE_RUBRIC.length - failed.length,
    total: USECASE_RUBRIC.length,
    failed,
  }
}
