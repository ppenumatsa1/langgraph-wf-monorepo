import { useEffect, useRef, useState } from "react";

import {
  openAgUiThreadStream,
  OptionalAgUiEndpointError,
} from "../../lib/agUiClient";
import type {
  AgUiFrame,
  AgUiThreadStream,
} from "../../lib/agUiClient";

type ConnectionState = "idle" | "connecting" | "connected" | "complete" | "unavailable";

type Props = {
  apiBase: string;
  threadId: string | null;
};

function unavailableMessage(error: unknown): string {
  if (error instanceof OptionalAgUiEndpointError) {
    return `${error.message} The native SSE timeline remains active.`;
  }
  return "The optional AG-UI view could not be opened. The native SSE timeline remains active.";
}

export default function AgUiThreadPanel({ apiBase, threadId }: Props) {
  const streamRef = useRef<AgUiThreadStream | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const [frames, setFrames] = useState<AgUiFrame[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    streamRef.current?.stop();
    streamRef.current = null;
    setConnectionState("idle");
    setFrames([]);
    setError(null);

    return () => {
      streamRef.current?.stop();
      streamRef.current = null;
    };
  }, [threadId]);

  const connect = () => {
    if (!threadId || connectionState === "connecting") {
      return;
    }

    streamRef.current?.stop();
    setFrames([]);
    setError(null);
    setConnectionState("connecting");
    const stream = openAgUiThreadStream({
      apiBase,
      threadId,
      onFrame: (frame) => {
        setFrames((previous) => [...previous, frame]);
      },
    });
    streamRef.current = stream;
    setConnectionState("connected");
    void stream.completed.then(
      () => {
        if (streamRef.current === stream) {
          setConnectionState("complete");
        }
      },
      (streamError: unknown) => {
        if (streamRef.current === stream) {
          setError(unavailableMessage(streamError));
          setConnectionState("unavailable");
        }
      },
    );
  };

  const disconnect = () => {
    streamRef.current?.stop();
    streamRef.current = null;
    setConnectionState("idle");
  };

  return (
    <section className="panel panel-ag-ui" data-testid="ag-ui-thread-view">
      <header className="panel-head">
        <div>
          <h2>AG-UI Selected Thread</h2>
          <p className="panel-description">
            Optional read-only protocol view for the selected workflow thread.
          </p>
        </div>
        <div className="panel-actions">
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!threadId || connectionState === "connecting"}
            onClick={connect}
          >
            {connectionState === "connecting" ? "Connecting..." : "Connect AG-UI"}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!threadId || connectionState === "idle"}
            onClick={disconnect}
          >
            Disconnect
          </button>
        </div>
      </header>

      {!threadId ? (
        <p className="muted">Select a workflow to enable the optional AG-UI view.</p>
      ) : (
        <>
          <p className="muted">
            Sends only the selected thread ID to the configured AG-UI endpoint. It never
            starts, approves, rejects, or changes this workflow.
          </p>
          {error ? <p className="error-text" role="status">{error}</p> : null}
          {!error && connectionState === "complete" ? (
            <p className="muted" role="status">AG-UI stream completed.</p>
          ) : null}
          {frames.length > 0 ? (
            <ol className="ag-ui-frame-list" aria-label="AG-UI protocol frames">
              {frames.map((frame) => (
                <li key={frame.id}>
                  <code>{frame.type}</code>
                  <span>{frame.timestamp ? new Date(frame.timestamp).toLocaleTimeString() : "n/a"}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted">No AG-UI protocol frames received.</p>
          )}
        </>
      )}
    </section>
  );
}
