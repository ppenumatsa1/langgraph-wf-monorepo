import { getAgUiEndpoint } from "../config";
import { assertEventStreamResponse } from "./apiClient";

export type AgUiFrame = {
  id: string;
  type: string;
  timestamp: string | null;
  text: string | null;
};

export class OptionalAgUiEndpointError extends Error {
  readonly status: number | null;

  constructor(status: number | null, reason: "status" | "content-type" = "status") {
    super(
      status === null
        ? "The optional AG-UI endpoint could not be reached."
        : reason === "content-type"
          ? "The optional AG-UI endpoint returned a non-event-stream response."
        : `The optional AG-UI endpoint returned ${status}.`,
    );
    this.name = "OptionalAgUiEndpointError";
    this.status = status;
  }
}

export type AgUiThreadStream = {
  completed: Promise<void>;
  stop: () => void;
};

function createClientId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function frameForEvent(event: unknown): AgUiFrame | null {
  if (!event || typeof event !== "object" || Array.isArray(event)) {
    return null;
  }
  const candidate = event as { type?: unknown; timestamp?: unknown; delta?: unknown };
  if (typeof candidate.type !== "string" || !candidate.type) {
    return null;
  }
  return {
    id: createClientId("frame"),
    type: candidate.type,
    timestamp: typeof candidate.timestamp === "string" ? candidate.timestamp : null,
    text: typeof candidate.delta === "string" ? candidate.delta : null,
  };
}

function nextSseMessage(buffer: string): { message: string; remainder: string } | null {
  const separators = ["\r\n\r\n", "\n\n"];
  const separator = separators
    .map((value) => ({ value, index: buffer.indexOf(value) }))
    .filter((candidate) => candidate.index >= 0)
    .sort((left, right) => left.index - right.index)[0];
  if (!separator) {
    return null;
  }

  return {
    message: buffer.slice(0, separator.index),
    remainder: buffer.slice(separator.index + separator.value.length),
  };
}

function parseSseMessage(message: string, onFrame: (frame: AgUiFrame) => void): void {
  const data = message
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice("data:".length).trimStart())
    .join("\n");
  if (!data) {
    return;
  }

  try {
    const frame = frameForEvent(JSON.parse(data) as unknown);
    if (frame) {
      onFrame(frame);
    }
  } catch {
    // A malformed optional AG-UI frame must not alter the native workflow view.
  }
}

export async function consumeAgUiSseResponse(
  response: Response,
  onFrame: (frame: AgUiFrame) => void,
): Promise<void> {
  assertEventStreamResponse(response, "AG-UI stream");
  if (!response.body) {
    throw new Error("Expected an AG-UI event stream response body.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      let message = nextSseMessage(buffer);
      while (message) {
        parseSseMessage(message.message, onFrame);
        buffer = message.remainder;
        message = nextSseMessage(buffer);
      }
      if (done) {
        break;
      }
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return;
    }
    throw error;
  }
}

async function consumeAgUiThreadStream({
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
    response = await fetch(getAgUiEndpoint(apiBase, threadId), {
      headers: { Accept: "text/event-stream" },
      credentials: "same-origin",
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return;
    }
    throw new OptionalAgUiEndpointError(null);
  }

  if (!response.ok) {
    throw new OptionalAgUiEndpointError(response.status);
  }
  try {
    await consumeAgUiSseResponse(response, onFrame);
  } catch {
    throw new OptionalAgUiEndpointError(response.status, "content-type");
  }
}

export function openAgUiThreadStream({
  apiBase,
  threadId,
  onFrame,
}: {
  apiBase: string;
  threadId: string;
  onFrame: (frame: AgUiFrame) => void;
}): AgUiThreadStream {
  const controller = new AbortController();
  const completed = consumeAgUiThreadStream({
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
