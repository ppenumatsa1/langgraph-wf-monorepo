---
name: e2e-rubric
description: Preserve the Order Resolution operator rubric for native SSE, durable HITL resume, optional AG-UI, safe CopilotKit context, privacy, and wrapper boundaries.
---

# E2E Rubric (Order Resolution)

Use this skill when editing UI behavior, API responses, workflow events, HITL,
AG-UI, CopilotKit, or selected-thread contracts.

## Rubric sources

- `frontend/tests/e2e/*`
- `backend/tests/test_order_resolution_boundaries.py`
- `backend/tests/test_workflow.py`
- `backend/tests/test_api.py`

## Automated criteria

Keep coverage for:

1. a low-risk `ORD-1001` workflow completing without HITL unless an explicit
   damaged-item or manual-review condition applies;
2. a high-risk `ORD-1009` workflow creating a durable HITL request and
   completing after its checkpoint-keyed approval or rejection;
3. the stable native SSE event types, ordering, and durable-history replay;
4. wrapper behavior in which initial dispatch is non-streaming and the browser
   receives state through durable reads and persisted-event SSE;
5. optional AG-UI selected-thread failures that leave the native timeline and
   operator controls available;
6. CopilotKit's selected-thread allowlist and redaction boundary, including no
   browser access to Foundry, PostgreSQL, MCP/RAG data, credentials, or secrets;
7. correlation identifiers and safe terminal/error state visibility without
   exposing raw payloads.
8. static, redacted `GET /api/copilotkit/info` discovery and a `POST
   /api/copilotkit` bridge that accepts only an existing selected `threadId` as
   meaningful input; supplied messages, state, tools, context, and forwarded
   props must not affect the workflow.
9. admission control that prevents more than one active interrupt for the same
   thread and reuses or surfaces the existing pending approval state.
10. replay-safe approval and terminal event behavior so resume does not emit
    duplicated once-only business outcomes from the replayed interrupt node.
11. durable-state reconciliation in which checkpoint-backed graph state remains
    authoritative and approval/history projections stay idempotent summaries.
12. private-boundary behavior in which only the frontend is externally
     reachable; the wrapper, Foundry, PostgreSQL, ACR, and runner stay private.
     Hosted browser checks use the external frontend URL while dependency
     assertions run from the private runner.

## Guardrails

- Do not weaken native SSE, durable HITL, or privacy coverage merely because an
  additive AG-UI or CopilotKit surface is unavailable.
- CopilotKit is the selected assistant UI integration, not the GitHub Copilot
  SDK. Test its read-only selected-thread behavior independently of the
  workflow path.
- Do not treat source configuration or local tests as evidence of a deployed
  endpoint, private DNS, private endpoint, or successful Azure release. Use an
  existing hosted gate only when the task explicitly requires hosted
  validation.
- Never bypass private dependencies with public endpoints during E2E. Missing
  private DNS, endpoint approval, identity/RBAC, or runner reachability is a
  blocker.
- If a criterion changes intentionally, update its tests and the relevant
  source-contract documentation in the same change.
- Keep checkpoint-retained PII off browser-visible workflow history, assistant
  payloads, and approval summaries unless a redacted contract explicitly
  allows it.

## Required verification

```bash
# Runs the existing workflow suite plus the frontend selected-thread integration.
make test-e2e

# Focused selected-thread integration test; Vite starts on 127.0.0.1:4175
# when PLAYWRIGHT_BASE_URL is not supplied.
make test-e2e-selected-thread

# Retained, separate Docker workflow-E2E profile.
make docker-test
```

Credential-free CI runs `make test-e2e-selected-thread` directly and retains
`make docker-test`; it does not treat the Docker workflow suite as a substitute
for the frontend selected-thread integration.
