DELETE FROM checkpoint_writes graph_state
USING workflow_runs runs
WHERE graph_state.thread_id = runs.id
  AND runs.status IN ('COMPLETED', 'FAILED')
  AND runs.completed_at < NOW() - make_interval(days => %(retention_days)s);

DELETE FROM checkpoint_blobs graph_state
USING workflow_runs runs
WHERE graph_state.thread_id = runs.id
  AND runs.status IN ('COMPLETED', 'FAILED')
  AND runs.completed_at < NOW() - make_interval(days => %(retention_days)s);

DELETE FROM checkpoints graph_state
USING workflow_runs runs
WHERE graph_state.thread_id = runs.id
  AND runs.status IN ('COMPLETED', 'FAILED')
  AND runs.completed_at < NOW() - make_interval(days => %(retention_days)s);
