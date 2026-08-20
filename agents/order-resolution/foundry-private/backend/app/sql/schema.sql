DO $$
BEGIN
    IF to_regclass('public.checkpoints') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1
           FROM information_schema.columns
           WHERE table_schema = 'public'
             AND table_name = 'checkpoints'
             AND column_name = 'checkpoint_ns'
       )
       AND to_regclass('public.legacy_workflow_checkpoints') IS NULL
    THEN
        ALTER TABLE checkpoints RENAME TO legacy_workflow_checkpoints;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    customer_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
    ON sessions (updated_at DESC);

CREATE TABLE IF NOT EXISTS workflow_runs (
    thread_id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(session_id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    input TEXT NOT NULL,
    input_summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    latest_output JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms BIGINT,
    current_stage TEXT
);

ALTER TABLE workflow_runs
    ALTER COLUMN duration_ms TYPE BIGINT;

ALTER TABLE workflow_runs
    ADD COLUMN IF NOT EXISTS session_id TEXT;

CREATE INDEX IF NOT EXISTS idx_workflow_runs_status_created_at
    ON workflow_runs (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_session_id
    ON workflow_runs (session_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'workflow_runs_session_id_fkey'
    ) THEN
        ALTER TABLE workflow_runs
            ADD CONSTRAINT workflow_runs_session_id_fkey
            FOREIGN KEY (session_id)
            REFERENCES sessions(session_id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS workflow_events (
    id UUID PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES workflow_runs(thread_id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_workflow_events_thread_timestamp
    ON workflow_events (thread_id, timestamp ASC, id ASC);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES workflow_runs(thread_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    dedupe_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE conversation_messages
    ADD COLUMN IF NOT EXISTS dedupe_key TEXT;

CREATE INDEX IF NOT EXISTS idx_conversation_messages_thread_id
    ON conversation_messages (thread_id, id ASC);

CREATE UNIQUE INDEX IF NOT EXISTS ux_conversation_messages_dedupe
    ON conversation_messages (thread_id, dedupe_key)
    WHERE dedupe_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS workflow_interrupts (
    checkpoint_id UUID PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES workflow_runs(thread_id) ON DELETE CASCADE,
    langgraph_checkpoint_id TEXT NOT NULL,
    langgraph_checkpoint_ns TEXT NOT NULL DEFAULT '',
    interrupt_id TEXT NOT NULL,
    status TEXT NOT NULL,
    decision TEXT,
    audit_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewer TEXT,
    comments TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

ALTER TABLE workflow_interrupts
    ADD COLUMN IF NOT EXISTS audit_summary JSONB NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'workflow_interrupts'
          AND column_name = 'state'
    ) THEN
        EXECUTE $migration$
            UPDATE workflow_interrupts
            SET audit_summary = jsonb_strip_nulls(
                jsonb_build_object(
                    'run_id', state -> 'run_id',
                    'session_id', state -> 'session_id',
                    'reconciliation', 'migrated_from_legacy_projection'
                )
            )
        $migration$;
        ALTER TABLE workflow_interrupts DROP COLUMN state;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_workflow_interrupts_thread_created_at
    ON workflow_interrupts (thread_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS ux_workflow_interrupts_langgraph_interrupt
    ON workflow_interrupts (thread_id, interrupt_id)
    WHERE interrupt_id <> '';

WITH ranked_unresolved AS (
    SELECT checkpoint_id,
           ROW_NUMBER() OVER (
               PARTITION BY thread_id
               ORDER BY updated_at DESC, checkpoint_id DESC
           ) AS row_number
    FROM workflow_interrupts
    WHERE status IN ('pending', 'resuming')
)
UPDATE workflow_interrupts wi
SET status = 'orphaned',
    audit_summary = wi.audit_summary || jsonb_build_object(
        'reconciliation', 'duplicate_unresolved_projection_migration'
    ),
    resolved_at = COALESCE(wi.resolved_at, NOW()),
    updated_at = NOW()
FROM ranked_unresolved ranked
WHERE wi.checkpoint_id = ranked.checkpoint_id
  AND ranked.row_number > 1;

DO $$
BEGIN
    IF to_regclass('public.legacy_workflow_checkpoints') IS NOT NULL THEN
        EXECUTE $migration$
            INSERT INTO workflow_interrupts (
                checkpoint_id, thread_id, langgraph_checkpoint_id,
                langgraph_checkpoint_ns, interrupt_id, status, audit_summary,
                reviewer, comments, created_at, updated_at
            )
            SELECT checkpoint_id, thread_id, '', '', '',
                   CASE status
                       WHEN 'pending_hitl' THEN 'pending'
                       ELSE status
                   END,
                   jsonb_strip_nulls(
                       jsonb_build_object(
                           'run_id', state -> 'run_id',
                           'session_id', state -> 'session_id',
                           'reconciliation', 'migrated_legacy_checkpoint'
                       )
                   ),
                   reviewer, comments,
                   created_at, updated_at
            FROM legacy_workflow_checkpoints
            ON CONFLICT (checkpoint_id) DO NOTHING
        $migration$;
    END IF;
END
$$;

WITH ranked_unresolved AS (
    SELECT checkpoint_id,
           ROW_NUMBER() OVER (
               PARTITION BY thread_id
               ORDER BY updated_at DESC, checkpoint_id DESC
           ) AS row_number
    FROM workflow_interrupts
    WHERE status IN ('pending', 'resuming')
)
UPDATE workflow_interrupts wi
SET status = 'orphaned',
    audit_summary = wi.audit_summary || jsonb_build_object(
        'reconciliation', 'duplicate_unresolved_projection_migration'
    ),
    resolved_at = COALESCE(wi.resolved_at, NOW()),
    updated_at = NOW()
FROM ranked_unresolved ranked
WHERE wi.checkpoint_id = ranked.checkpoint_id
  AND ranked.row_number > 1;

CREATE UNIQUE INDEX IF NOT EXISTS ux_workflow_interrupts_one_unresolved_thread
    ON workflow_interrupts (thread_id)
    WHERE status IN ('pending', 'resuming');

CREATE TABLE IF NOT EXISTS approvals (
    approval_id UUID PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES workflow_runs(thread_id) ON DELETE CASCADE,
    checkpoint_id UUID NOT NULL,
    reviewer TEXT,
    comments TEXT,
    status TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ
);

ALTER TABLE approvals
    DROP COLUMN IF EXISTS action,
    DROP COLUMN IF EXISTS order_id,
    DROP COLUMN IF EXISTS amount,
    DROP COLUMN IF EXISTS question;

ALTER TABLE approvals
    DROP CONSTRAINT IF EXISTS approvals_checkpoint_id_fkey;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'approvals_workflow_interrupt_fkey'
    ) THEN
        ALTER TABLE approvals
            ADD CONSTRAINT approvals_workflow_interrupt_fkey
            FOREIGN KEY (checkpoint_id)
            REFERENCES workflow_interrupts(checkpoint_id)
            ON DELETE CASCADE;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_approvals_thread_requested_at
    ON approvals (thread_id, requested_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS ux_approvals_checkpoint_id
    ON approvals (checkpoint_id);

CREATE INDEX IF NOT EXISTS idx_approvals_checkpoint_status
    ON approvals (checkpoint_id, status);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    idempotency_key TEXT PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    business_id TEXT NOT NULL,
    status TEXT NOT NULL,
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_idempotency_keys_run_step
    ON idempotency_keys (workflow_run_id, step_name);

CREATE TABLE IF NOT EXISTS responses_dispatches (
    idempotency_key TEXT PRIMARY KEY,
    request_hash TEXT NOT NULL,
    run_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_responses_dispatches_thread_id
    ON responses_dispatches (thread_id);

CREATE TABLE IF NOT EXISTS eval_runs (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_started_at
    ON eval_runs (started_at DESC);

CREATE TABLE IF NOT EXISTS eval_results (
    id UUID PRIMARY KEY,
    eval_run_id UUID NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    case_id TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    score DOUBLE PRECISION,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eval_results_eval_run_case
    ON eval_results (eval_run_id, case_id);
