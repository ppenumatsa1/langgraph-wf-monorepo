type RuntimeConfig = {
  API_BASE?: string;
  AG_UI_URL?: string;
  COPILOTKIT_URL?: string;
};

declare global {
  interface Window {
    __APP_CONFIG__?: RuntimeConfig;
  }
}

function trimTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, "");
}

export function getInitialApiBase(): string {
  const runtimeBase = window.__APP_CONFIG__?.API_BASE?.trim();
  const viteBase =
    import.meta.env.VITE_API_BASE_URL?.trim() ?? import.meta.env.VITE_API_BASE?.trim();
  return trimTrailingSlashes(runtimeBase || viteBase || "");
}

function getOptionalEndpoint(
  runtimeValue: string | undefined,
  viteValue: string | undefined,
  fallback: string,
): string {
  return trimTrailingSlashes(runtimeValue?.trim() || viteValue?.trim() || fallback);
}

export function getAgUiEndpoint(apiBase: string, threadId: string): string {
  const endpointTemplate = getOptionalEndpoint(
    window.__APP_CONFIG__?.AG_UI_URL,
    import.meta.env.VITE_AG_UI_URL,
    `${apiBase}/api/chat/stream/{threadId}/ag-ui`,
  );
  return endpointTemplate.replace("{threadId}", encodeURIComponent(threadId));
}

export function getCopilotKitEndpoint(apiBase: string): string {
  return getOptionalEndpoint(
    window.__APP_CONFIG__?.COPILOTKIT_URL,
    import.meta.env.VITE_COPILOTKIT_URL,
    `${apiBase}/api/copilotkit`,
  );
}
