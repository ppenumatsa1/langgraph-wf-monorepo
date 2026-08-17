# Underwriting frontend

React + Vite operator console for the underwriting LangGraph lane.

## Preserved browser contract

The frontend continues to provide:

- application-form entry,
- scenario start for happy, retry, and crash flows,
- run history selection and refresh,
- checkpoint timeline and resume affordance,
- four-check fan-in visibility,
- idempotency-skip evidence,
- same-origin `/api` and `/backend-health` calls only, and
- a strict selected-run CopilotKit allowlist.

## Commands

```bash
npm run lint
npm run build
npm run test:e2e
```

`npm run test:e2e` starts the Vite dev server automatically. The backend must be reachable at `http://127.0.0.1:8000` unless `PLAYWRIGHT_BASE_URL` is set for hosted validation.

## Runtime notes

- AG-UI stream updates remain additive to durable run, state, event, and checkpoint APIs.
- The browser never calls Foundry or PostgreSQL directly.
- CopilotKit reads only safe selected-run metadata from `/api/v1/underwriting/copilotkit`.
