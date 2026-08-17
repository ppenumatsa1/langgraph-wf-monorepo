CREATE TABLE IF NOT EXISTS workflow_runs (
    id TEXT PRIMARY KEY,
    workflow_type TEXT NOT NULL,
    application_id TEXT NOT NULL,
    applicant_name TEXT,
    status TEXT NOT NULL,
    latest_output JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms BIGINT
);

ALTER TABLE workflow_runs
    ADD COLUMN IF NOT EXISTS applicant_name TEXT,
    ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS duration_ms BIGINT;

CREATE INDEX IF NOT EXISTS idx_workflow_runs_status_created_at
    ON workflow_runs (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_application_id
    ON workflow_runs (application_id);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_applicant_name
    ON workflow_runs (applicant_name);

CREATE TABLE IF NOT EXISTS business_state (
    id BIGSERIAL PRIMARY KEY,
    workflow_run_id TEXT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    application_id TEXT NOT NULL,
    state_key TEXT NOT NULL,
    state_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ux_business_state_run_key UNIQUE (workflow_run_id, state_key)
);

CREATE INDEX IF NOT EXISTS idx_business_state_run_id
    ON business_state (workflow_run_id, id ASC);

CREATE TABLE IF NOT EXISTS underwriting_results (
    id BIGSERIAL PRIMARY KEY,
    workflow_run_id TEXT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    application_id TEXT NOT NULL,
    check_type TEXT NOT NULL,
    result_json JSONB NOT NULL,
    idempotency_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ux_underwriting_results_idempotency UNIQUE (idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_underwriting_results_run_type
    ON underwriting_results (workflow_run_id, check_type, id DESC);

CREATE TABLE IF NOT EXISTS workflow_events (
    id BIGSERIAL PRIMARY KEY,
    workflow_run_id TEXT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    executor_name TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_events_run_id
    ON workflow_events (workflow_run_id, id ASC);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    idempotency_key TEXT PRIMARY KEY,
    operation_name TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_idempotency_keys_operation_name
    ON idempotency_keys (operation_name, updated_at DESC);

CREATE TABLE IF NOT EXISTS workflow_checkpoints (
    workflow_run_id TEXT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT workflow_checkpoints_pkey PRIMARY KEY (workflow_run_id, checkpoint_ns, checkpoint_id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_run_created_at
    ON workflow_checkpoints (workflow_run_id, created_at DESC);
