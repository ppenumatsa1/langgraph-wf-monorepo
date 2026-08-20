import TimelineEvent from "./TimelineEvent";
import type { WorkflowEvent } from "../../types/workflow";

type Props = {
  events: WorkflowEvent[];
  hasSelectedWorkflow: boolean;
  onRefresh: () => Promise<void>;
  isLoading: boolean;
  error: string | null;
  isLiveStreaming: boolean;
  richEnvelopeCount: number;
};

export default function WorkflowTimeline({
  events,
  hasSelectedWorkflow,
  onRefresh,
  isLoading,
  error,
  isLiveStreaming,
  richEnvelopeCount,
}: Props) {
  return (
    <section className="panel panel-timeline">
      <header className="panel-head">
        <h2>
          Event Timeline
          {isLiveStreaming ? (
            <span className="muted"> • Live (rich stream) • envelopes: {richEnvelopeCount}</span>
          ) : null}
        </h2>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={isLoading}
          onClick={onRefresh}
        >
          Refresh
        </button>
      </header>

      {events.length === 0 ? (
        <p className="muted">
          {hasSelectedWorkflow
            ? "No events available for this workflow yet."
            : "Start a workflow or select a run to view timeline events."}
        </p>
      ) : (
        <div className="timeline-list">
          {events.map((event) => (
            <TimelineEvent key={event.id} event={event} />
          ))}
        </div>
      )}
      {error ? <p className="error-text">{error}</p> : null}
    </section>
  );
}
