import { getCopilotKitEndpoint } from "../config";
import { consumeAgUiSseResponse } from "./agUiClient";
import type { AgUiFrame } from "./agUiClient";

export class OptionalCopilotKitEndpointError extends Error {
  readonly status: number | null;

  constructor(status: number | null) {
    super(
      status === null
        ? "The optional CopilotKit endpoint could not be reached."
        : `The optional CopilotKit endpoint returned ${status}.`,
    );
    this.name = "OptionalCopilotKitEndpointError";
    this.status = status;
  }
}

export type CopilotKitThreadStream = {
  completed: Promise<void>;
  stop: () => void;
};

async function consumeCopilotKitThreadStream({
  apiBase,
  threadId,
  onFrame,
  signal,
}: {
  apiBase: string;
  threadId: string;
  onFrame: (frame: AgUiFrame) => void;
  signal: AbortSignal;
}): Promise<void> {
  let response: Response;
  try {
    response = await fetch(getCopilotKitEndpoint(apiBase), {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
      },
      credentials: "same-origin",
      signal,
      body: JSON.stringify({
        threadId,
      }),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return;
    }
    throw new OptionalCopilotKitEndpointError(null);
  }

  if (!response.ok) {
    throw new OptionalCopilotKitEndpointError(response.status);
  }

  try {
    await consumeAgUiSseResponse(response, onFrame);
  } catch {
    throw new OptionalCopilotKitEndpointError(response.status);
  }
}

export function openCopilotKitThreadStream({
  apiBase,
  threadId,
  onFrame,
}: {
  apiBase: string;
  threadId: string;
  onFrame: (frame: AgUiFrame) => void;
}): CopilotKitThreadStream {
  const controller = new AbortController();
  const completed = consumeCopilotKitThreadStream({
    apiBase,
    threadId,
    onFrame,
    signal: controller.signal,
  });

  return {
    completed,
    stop: () => {
      controller.abort();
    },
  };
}
