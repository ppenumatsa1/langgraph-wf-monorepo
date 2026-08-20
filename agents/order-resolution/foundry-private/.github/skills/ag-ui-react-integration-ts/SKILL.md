---
name: ag-ui-react-integration-ts
description: Implement and review the React TypeScript selected-thread experience for Order Resolution's additive AG-UI projection, durable history, and safe CopilotKit assistant context.
---

# AG-UI React Integration (Order Resolution)

Use this skill when changing frontend streaming consumption or operator behavior
that depends on workflow events.

## Scope

- `frontend/src/App.tsx`, `frontend/src/main.tsx`, and `frontend/src/config.ts`
- `frontend/src/copilot.ts` and `frontend/src/lib/agUiClient.ts`
- `frontend/src/components/studio/*`
- `frontend/tests/e2e/*`

## Invariants

- The native legacy SSE timeline and durable workflow APIs are the operator
  source of truth. AG-UI is an optional, additive selected-thread view; a
  connection or parsing failure must leave the native timeline usable.
- The browser calls the external frontend's same-origin API wrapper only. It
  must not call Foundry, PostgreSQL, MCP/RAG services, or secret-bearing
  endpoints directly.
- Use **CopilotKit** (`@copilotkit/react-core`) for the selected-thread
  assistant experience. It is distinct from, and must not be replaced with or
  described as, the GitHub Copilot SDK, which is not this application's runtime
  integration. Discover the runtime with `GET /api/copilotkit/info` (the root
  `GET /api/copilotkit` is an alias) and stream one existing selected thread
  with `POST /api/copilotkit`.
- Keep the selected-thread context allowlisted in `frontend/src/copilot.ts`:
  opaque thread ID, normalized status, safe event metadata, pending-approval
  count, and output presence only. Do not add order details, policy/RAG data,
  raw event payloads, prompts, model output, checkpoint content, credentials,
  or secrets.
- Preserve the existing external frontend -> internal FastAPI wrapper boundary.
  Initial wrapper dispatch is non-streaming; live UI updates come from durable
  reads and SSE projections.
- Send only the selected `threadId` as meaningful bridge input. Compatibility
  fields such as `runId`, `messages`, `state`, `tools`, `context`, and
  `forwardedProps` are intentionally ignored by the backend and must not become
  a prompt, action, or state mutation channel.
- Keep accessibility and explicit error states for malformed, unavailable, or
  non-JSON optional stream responses.

## Required verification

1. `cd frontend && npm run build`
2. `cd frontend && npm run lint`
3. `make test-e2e` when UI, API, AG-UI, CopilotKit, or selected-thread behavior changes
