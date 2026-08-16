import type { WorkflowEvent } from "../lib/sseClient";

type Props = {
  events: WorkflowEvent[];
};

export default function EventTimeline({ events }: Props) {
  return (
    <section className="panel timeline">
      <h2>Event Timeline</h2>
      <div className="timeline-list">
        {events.map((event) => (
          <article key={event.id} className="timeline-item">
            <header>
              <span className="event-type">{event.type}</span>
              <time>{new Date(event.timestamp).toLocaleTimeString()}</time>
            </header>
            <pre>{JSON.stringify(event.payload, null, 2)}</pre>
          </article>
        ))}
        {events.length === 0 && (
          <p className="muted">No events yet. Start a run.</p>
        )}
      </div>
    </section>
  );
}
