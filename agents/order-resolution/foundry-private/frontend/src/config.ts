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

function sameOriginPath(value: string, name: string): string {
  const trimmed = trimTrailingSlashes(value.trim());
  if (!trimmed) {
    return "";
  }

  const resolved = new URL(trimmed, window.location.origin);
  if (resolved.origin !== window.location.origin) {
    throw new Error(`${name} must be a same-origin path for the private frontend.`);
  }

  const path = `${resolved.pathname}${resolved.search}${resolved.hash}`;
  return path === "/" ? "" : trimTrailingSlashes(path);
}

function configuredSameOriginPath(
  values: Array<string | undefined>,
  name: string,
): string {
  for (const value of values) {
    if (!value?.trim()) {
      continue;
    }
    try {
      return sameOriginPath(value, name);
    } catch (error) {
      console.warn(error instanceof Error ? error.message : `${name} is invalid.`);
      return "";
    }
  }
  return "";
}

export function getInitialApiBase(): string {
  return configuredSameOriginPath(
    [
      window.__APP_CONFIG__?.API_BASE,
      import.meta.env.VITE_API_BASE_URL,
      import.meta.env.VITE_API_BASE,
    ],
    "API_BASE",
  );
}

function getOptionalEndpoint(
  runtimeValue: string | undefined,
  viteValue: string | undefined,
  fallback: string,
  name: string,
): string {
  return configuredSameOriginPath([runtimeValue, viteValue, fallback], name);
}

export function getAgUiEndpoint(apiBase: string, threadId: string): string {
  const threadPlaceholder = "__THREAD_ID__";
  const endpointTemplate = getOptionalEndpoint(
    window.__APP_CONFIG__?.AG_UI_URL?.replace("{threadId}", threadPlaceholder),
    import.meta.env.VITE_AG_UI_URL?.replace("{threadId}", threadPlaceholder),
    `${apiBase}/api/chat/stream/${threadPlaceholder}/ag-ui`,
    "AG_UI_URL",
  );
  return endpointTemplate.replace(threadPlaceholder, encodeURIComponent(threadId));
}

export function getCopilotKitEndpoint(apiBase: string): string {
  return getOptionalEndpoint(
    window.__APP_CONFIG__?.COPILOTKIT_URL,
    import.meta.env.VITE_COPILOTKIT_URL,
    `${apiBase}/api/copilotkit`,
    "COPILOTKIT_URL",
  );
}
