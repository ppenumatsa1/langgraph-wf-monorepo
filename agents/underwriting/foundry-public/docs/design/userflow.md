# User Flow

## Execution surfaces

The approved journey has three execution surfaces:

| Surface | Status | Meaning |
| --- | --- | --- |
| Local full stack | Contract baseline | React + FastAPI + LangGraph-target runtime + PostgreSQL define the stable UI, API, and AG-UI behavior. |
| Public Foundry-hosted agent | Approved target | Foundry Responses 2.0 hosts the same underwriting business flow. |
| Public browser wrapper | Approved target | External frontend proxies same-origin `/api` traffic to the internal FastAPI wrapper, which delegates to Foundry and replays durable events. |

Historical MAF-era releases are migration provenance only. Fresh LangGraph smoke, E2E, evaluation, and telemetry evidence must be generated after backend cutover.

## Runtime user flow

1. The operator selects a scenario and submits an application.
2. The browser opens the selected run and receives additive AG-UI updates.
3. The backend creates or reuses a durable `workflow_run_id` and starts one underwriting graph run.
4. The graph initializes shared underwriting context.
5. Risk, credit, medical, and driving checks run in parallel.
6. Fan-in aggregation merges check results as they arrive.
7. The deterministic final decision executes only after all four results are present.
8. Optional rationale generation enriches the final output.
9. The UI reads durable run details, events, state, and checkpoint summaries; the embedded assistant explains the selected run using only allowlisted metadata.

## Crash and resume flow

1. The operator runs the crash scenario (`crash_after_executor=medical_check`).
2. The selected run reaches `CRASHED` status with the same `workflow_run_id`.
3. The latest checkpoint remains durable in PostgreSQL.
4. The operator resumes that run from the UI.
5. The backend restores checkpointed workflow state and continues only remaining work.
6. Idempotency prevents duplicate side effects during replayed execution steps.
7. The UI shows resumed progress, checkpoint evidence, and any `idempotency_skip` events.

## Operator inspection flow

1. The operator searches or filters history (`GET /api/v1/underwriting/runs`).
2. The operator opens one run (`GET /api/v1/underwriting/runs/{run_id}`).
3. The operator inspects:
   - incremental state (`/state`),
   - ordered events (`/events`),
   - checkpoint summaries (`/checkpoints`).
4. The operator confirms completion status, decision output, four-check fan-in, and recovery evidence.

## Public hosted request flow

The public topology keeps the browser on one contract:

```text
Browser
  -> external frontend Container App
  -> same-origin /api proxy
  -> internal FastAPI wrapper
  -> Foundry Responses 2.0 hosted agent
  -> shared PostgreSQL checkpointer and audit projections
```

For the hosted wrapper path:

1. The wrapper records the dispatch and selects the workflow identity.
2. It sends the request to Foundry without browser-direct credentials.
3. The hosted agent runs the same underwriting graph shape.
4. The browser gets live updates from AG-UI and durable PostgreSQL projections.
5. Browser refresh, replay, AG-UI, and CopilotKit explanation all come from the same durable run identity.

## Stable operator outcomes

- Happy path: completed run with decision output and persisted checkpoint and event evidence.
- Retry path: retry-related events are present and final result appears once.
- Crash/resume path: crashed run completes from checkpoint without duplicate persistence.
- Public cutover path: browser, same-origin proxy, internal backend, hosted Responses workflow, and PostgreSQL all correlate on one `workflow_run_id`.
- Privacy path: selected-run assistant explanation stays on the allowlist and never exposes applicant content or checkpoint payloads.
