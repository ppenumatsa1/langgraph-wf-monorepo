\set ON_ERROR_STOP on

\if :{?retention_days}
\else
\echo 'retention_days is required (use -v retention_days=<positive integer>)'
\quit 1
\endif

DELETE FROM checkpoint_writes writes
USING workflow_runs runs
WHERE writes.thread_id = runs.thread_id
  AND runs.status IN ('completed', 'failed', 'escalated')
  AND runs.completed_at < NOW() - (:'retention_days' || ' days')::interval
  AND NOT EXISTS (
      SELECT 1
      FROM workflow_interrupts interrupts
      WHERE interrupts.thread_id = runs.thread_id
        AND interrupts.status IN ('pending', 'resuming')
  );

DELETE FROM checkpoint_blobs blobs
USING workflow_runs runs
WHERE blobs.thread_id = runs.thread_id
  AND runs.status IN ('completed', 'failed', 'escalated')
  AND runs.completed_at < NOW() - (:'retention_days' || ' days')::interval
  AND NOT EXISTS (
      SELECT 1
      FROM workflow_interrupts interrupts
      WHERE interrupts.thread_id = runs.thread_id
        AND interrupts.status IN ('pending', 'resuming')
  );

DELETE FROM checkpoints graph_checkpoints
USING workflow_runs runs
WHERE graph_checkpoints.thread_id = runs.thread_id
  AND runs.status IN ('completed', 'failed', 'escalated')
  AND runs.completed_at < NOW() - (:'retention_days' || ' days')::interval
  AND NOT EXISTS (
      SELECT 1
      FROM workflow_interrupts interrupts
      WHERE interrupts.thread_id = runs.thread_id
        AND interrupts.status IN ('pending', 'resuming')
  );
