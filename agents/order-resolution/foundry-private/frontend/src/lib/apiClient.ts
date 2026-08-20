export class ApiContentTypeError extends Error {
  readonly contentType: string;
  readonly expected: string;
  readonly route: string;

  constructor(route: string, expected: string, contentType: string | null) {
    const actual = contentType?.split(";")[0].trim().toLowerCase() || "missing";
    super(`Expected ${expected} from ${route}, received ${actual}.`);
    this.name = "ApiContentTypeError";
    this.contentType = actual;
    this.expected = expected;
    this.route = route;
  }
}

export class ApiResponseError extends Error {
  readonly status: number;
  readonly route: string;

  constructor(method: string, route: string, status: number) {
    super(`${method.toUpperCase()} ${route} failed (${status}).`);
    this.name = "ApiResponseError";
    this.status = status;
    this.route = route;
  }
}

function trimTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, "");
}

function routeLabel(url: string): string {
  const resolved = new URL(url, window.location.origin);
  return `${resolved.pathname}${resolved.search}`;
}

function buildApiUrl(apiBase: string, apiRoute: string): string {
  if (!apiRoute.startsWith("/api/") && apiRoute !== "/api") {
    throw new Error(`API route must start with /api: ${apiRoute}`);
  }

  const base = trimTrailingSlashes(apiBase);
  const url = `${base}${apiRoute}`;
  const resolved = new URL(url, window.location.origin);
  if (resolved.origin !== window.location.origin) {
    throw new Error(`API route must remain same-origin: ${apiRoute}`);
  }
  return `${resolved.pathname}${resolved.search}`;
}

function isJsonContentType(contentType: string | null): boolean {
  const mimeType = contentType?.split(";")[0].trim().toLowerCase();
  return Boolean(
    mimeType &&
      (mimeType === "application/json" || mimeType.endsWith("+json")),
  );
}

export function assertJsonResponse(response: Response, route: string): void {
  const contentType = response.headers.get("content-type");
  if (!isJsonContentType(contentType)) {
    throw new ApiContentTypeError(route, "application/json", contentType);
  }
}

export function assertEventStreamResponse(
  response: Response,
  route: string,
): void {
  const contentType = response.headers.get("content-type");
  if (
    contentType?.split(";")[0].trim().toLowerCase() !== "text/event-stream"
  ) {
    throw new ApiContentTypeError(route, "text/event-stream", contentType);
  }
}

export async function fetchApiJson<T>(
  apiBase: string,
  apiRoute: string,
  init?: RequestInit,
  options?: { allowNoContent?: boolean },
): Promise<T> {
  const url = buildApiUrl(apiBase, apiRoute);
  const headers = new Headers(init?.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const response = await fetch(url, {
    ...init,
    credentials: "same-origin",
    headers,
  });
  const label = routeLabel(url);
  if (options?.allowNoContent && response.status === 204) {
    if (!response.ok) {
      throw new ApiResponseError(init?.method ?? "GET", label, response.status);
    }
    return undefined as T;
  }
  assertJsonResponse(response, label);
  const payload = (await response.json()) as T;
  if (!response.ok) {
    throw new ApiResponseError(init?.method ?? "GET", label, response.status);
  }
  return payload;
}
