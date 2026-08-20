import { useEffect, useRef, useState } from "react";

import type { AgUiFrame } from "../../lib/agUiClient";
import {
  openCopilotKitThreadStream,
  OptionalCopilotKitEndpointError,
} from "../../lib/copilotKitClient";
import type { CopilotKitThreadStream } from "../../lib/copilotKitClient";

type Props = {
  apiBase: string;
  threadId: string | null;
};

function unavailableMessage(error: unknown): string {
  if (error instanceof OptionalCopilotKitEndpointError) {
    return `${error.message} The workflow studio and native SSE timeline remain active.`;
  }
  return "The optional CopilotKit view could not be opened. The workflow studio and native SSE timeline remain active.";
}

export default function SelectedThreadAssistantPanel({ apiBase, threadId }: Props) {
  const streamRef = useRef<CopilotKitThreadStream | null>(null);
  const [frames, setFrames] = useState<AgUiFrame[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    streamRef.current?.stop();
    streamRef.current = null;
    setFrames([]);
    setIsLoading(false);
    setError(null);

    return () => {
      streamRef.current?.stop();
      streamRef.current = null;
    };
  }, [threadId]);

  const loadAssistantView = () => {
    if (!threadId || isLoading) {
      return;
    }

    streamRef.current?.stop();
    setFrames([]);
    setError(null);
    setIsLoading(true);
    const stream = openCopilotKitThreadStream({
      apiBase,
      threadId,
      onFrame: (frame) => {
        setFrames((previous) => [...previous, frame]);
      },
    });
    streamRef.current = stream;
    void stream.completed.then(
      () => {
        if (streamRef.current === stream) {
          setIsLoading(false);
        }
      },
      (streamError: unknown) => {
        if (streamRef.current === stream) {
          setError(unavailableMessage(streamError));
          setIsLoading(false);
        }
      },
    );
  };

  return (
    <section
      className="panel panel-thread-assistant"
      aria-labelledby="thread-assistant-title"
      data-testid="copilot-thread-assistant"
    >
      <header className="panel-head">
        <div>
          <h2 id="thread-assistant-title">Selected Thread Assistant</h2>
          <p className="panel-description">
            The CopilotKit bridge receives only the selected thread identifier and returns a
            redacted durable event projection.
          </p>
        </div>
      </header>
      {!threadId ? (
        <p className="muted">Select a workflow to ask about its execution progress.</p>
      ) : (
        <>
          <p className="muted">
            This optional read-only bridge cannot approve, reject, start, or alter a workflow.
          </p>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={isLoading}
            onClick={loadAssistantView}
          >
            {isLoading ? "Loading assistant view..." : "Load assistant view"}
          </button>
          {error ? <p className="error-text" role="status">{error}</p> : null}
          {frames.length > 0 ? (
            <ol className="ag-ui-frame-list" aria-label="CopilotKit assistant frames">
              {frames.map((frame) => (
                <li key={frame.id}>
                  <code>{frame.type}</code>
                  <span>
                    {frame.text ??
                      (frame.timestamp ? new Date(frame.timestamp).toLocaleTimeString() : "n/a")}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted">No CopilotKit assistant events received.</p>
          )}
        </>
      )}
    </section>
  );
}
