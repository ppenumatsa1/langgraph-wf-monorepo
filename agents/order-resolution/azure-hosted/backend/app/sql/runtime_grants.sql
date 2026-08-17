\set ON_ERROR_STOP on

\if :{?runtime_role}
\else
\echo 'runtime_role is required (use -v runtime_role=<role>)'
\quit 1
\endif

GRANT USAGE ON SCHEMA public TO :"runtime_role";

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    sessions,
    workflow_runs,
    workflow_events,
    conversation_messages,
    workflow_interrupts,
    approvals,
    idempotency_keys,
    responses_dispatches,
    eval_runs,
    eval_results,
    checkpoints,
    checkpoint_blobs,
    checkpoint_writes
TO :"runtime_role";

GRANT SELECT ON TABLE checkpoint_migrations TO :"runtime_role";

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"runtime_role";
