GRANT USAGE ON SCHEMA public TO underwriting_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    workflow_runs,
    business_state,
    underwriting_results,
    workflow_events,
    idempotency_keys,
    workflow_checkpoints,
    checkpoint_migrations,
    checkpoints,
    checkpoint_blobs,
    checkpoint_writes
TO underwriting_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO underwriting_runtime;
