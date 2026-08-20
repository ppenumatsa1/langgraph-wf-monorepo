import type { WorkflowMetadata } from "../../types/workflow";
import StatusBadge from "./StatusBadge";

type Props = {
  metadata: WorkflowMetadata | null;
};

function formatDuration(durationMs?: number | null): string {
  if (!durationMs && durationMs !== 0) {
    return "n/a";
  }
  if (durationMs < 1000) {
    return `${durationMs} ms`;
  }
  return `${(durationMs / 1000).toFixed(2)} s`;
}

export default function RunMetadataPanel({ metadata }: Props) {
  return (
    <section className="panel panel-metadata">
      <header className="panel-head">
        <h2>Run Metadata</h2>
      </header>
      {!metadata ? (
        <p className="muted">No workflow selected.</p>
      ) : (
        <dl className="metadata-list">
          <div>
            <dt>Thread ID</dt>
            <dd>{metadata.thread_id}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>
              <StatusBadge status={metadata.status} />
            </dd>
          </div>
          <div>
            <dt>Started At</dt>
            <dd>
              {metadata.started_at
                ? new Date(metadata.started_at).toLocaleString()
                : "n/a"}
            </dd>
          </div>
          <div>
            <dt>Completed At</dt>
            <dd>
              {metadata.completed_at
                ? new Date(metadata.completed_at).toLocaleString()
                : "n/a"}
            </dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>{formatDuration(metadata.duration_ms)}</dd>
          </div>
          <div>
            <dt>Current Stage</dt>
            <dd>{metadata.current_stage ?? "n/a"}</dd>
          </div>
        </dl>
      )}
    </section>
  );
}
