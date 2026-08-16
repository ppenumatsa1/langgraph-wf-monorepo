# Frontend - React + Vite

```bash
cd frontend
npm install
npm run dev
```

The app defaults to backend `http://localhost:8000` during Vite development.
Container deployments use the built-in same-origin `/api` base. At startup,
Nginx renders its `/api/` proxy from the required `NGINX_API_UPSTREAM`; Docker
Compose points it to `http://backend:8000`, while Azure points it to the
internal backend ACA HTTPS URL.

For isolated local Playwright runs, `make test-e2e` sets Vite's
`VITE_PROXY_TARGET` to the dedicated dynamically selected backend port. Regular
development continues to default to `http://localhost:8000`. The same Make
gate also runs `tests/e2e/selected-thread-integrations.spec.ts` against that
dynamic Vite URL. Run `make test-e2e-selected-thread` to execute only that
mocked integration test; its Playwright configuration starts Vite on
`127.0.0.1:4175` when no `PLAYWRIGHT_BASE_URL` is supplied.

Workflow Studio runtime info:

- Runtime badge reads backend `/health` metadata to display active environment/mode.
- In deployed frontend containers the badge uses proxied `/api/health` first so
  it does not read the frontend container's own `/health` endpoint.

UI highlights:

- Workflow history uses paginated API calls (`/api/workflows?page=<n>&page_size=<n>`).
- Event timeline uses rich SSE (`/api/chat/stream/{thread_id}/rich`) for live updates, while polling details remains as fallback.
- Right panel includes a RAG Evidence view that surfaces retrieved policy evidence and chunk IDs from workflow events/details when available.

## Hosted runtime

The public frontend is externally reachable at
the `WEB_URL` hydrated into the selected `infra/foundry-hosted` AZD environment.
It is the only browser entrypoint: Nginx proxies same-origin `/api` requests to
the internal backend Container App, and the browser never receives a Foundry
endpoint or credential.

Foundry Responses work can take longer than local workflow execution. For an
HTTPS `PLAYWRIGHT_BASE_URL`, the Playwright configuration uses 60-second
assertions and 120-second test timeouts; local defaults remain 10 and 45
seconds. Both are configurable through the existing Playwright environment.
