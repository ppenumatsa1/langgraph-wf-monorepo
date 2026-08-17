type Props = {
  message: string;
  isSubmitting: boolean;
  onMessageChange: (message: string) => void;
  onSubmit: () => Promise<void>;
  onClear: () => void;
};

export default function WorkflowRunComposer({
  message,
  isSubmitting,
  onMessageChange,
  onSubmit,
  onClear,
}: Props) {
  return (
    <section className="panel panel-composer">
      <header className="panel-head">
        <h2>Start Workflow</h2>
      </header>
      <textarea
        rows={4}
        value={message}
        placeholder="Describe the customer issue or workflow request..."
        onChange={(event) => onMessageChange(event.target.value)}
      />
      <div className="composer-actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={isSubmitting || !message.trim()}
          onClick={onSubmit}
        >
          {isSubmitting ? "Starting..." : "Start Workflow"}
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={isSubmitting}
          onClick={onClear}
        >
          Clear
        </button>
      </div>
    </section>
  );
}
