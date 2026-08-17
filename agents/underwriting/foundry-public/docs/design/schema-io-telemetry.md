# Schema, I/O, and Telemetry

## Stable API contracts

### Start run

- Method/path: `POST /api/v1/underwriting/runs`
- Request shape:

```json
{
  "application": {
    "application_id": "UW-1001",
    "applicant_name": "Asha Patel",
    "age": 42,
    "income": 125000,
    "requested_coverage": 500000,
    "health_disclosures": "none",
    "driving_history": "minor-violation-2022",
    "credit_score": 742
  },
  "workflow_run_id": "optional-run-id",
  "fail_risk_once": false,
  "fail_credit_randomly": false,
  "crash_after_executor": "optional"
}
```

- Response shape:

```json
{
  "workflow_run_id": "run-1234abcd",
  "status": "COMPLETED",
  "outputs": []
}
```

### Resume run

- Method/path: `POST /api/v1/underwriting/runs/{run_id}/resume`
- Response shape:

```json
{
  "workflow_run_id": "run-1234abcd",
  "status": "COMPLETED",
  "outputs": []
}
```

### Durable read models

- `GET /api/v1/underwriting/runs?search=&status=&limit=&offset=`
- `GET /api/v1/underwriting/runs/{run_id}`
- `GET /api/v1/underwriting/runs/{run_id}/state`
- `GET /api/v1/underwriting/runs/{run_id}/events`
- `GET /api/v1/underwriting/runs/{run_id}/checkpoints`

These routes remain the source of truth for refresh, replay, and selected-run views.

## AG-UI stream contract

- Method/path: `POST /api/v1/underwriting/ag-ui`
- Content type: `text/event-stream`
- Usage: stream live start or resume updates while durable run, state, event, and checkpoint APIs remain authoritative.

### Frontend request envelope

The frontend posts one AG-UI request with a user message whose `content` JSON contains:

```json
{
  "action": "start | resume",
  "workflow_run_id": "run-1234abcd",
  "application": {},
  "fail_risk_once": false,
  "fail_credit_randomly": false,
  "crash_after_executor": "medical_check"
}
```

### Frontend-consumed event envelope

The frontend preserves the existing additive stream contract:

```json
{
  "type": "CUSTOM",
  "name": "underwriting.event",
  "value": {
    "workflowRunId": "run-1234abcd",
    "eventType": "workflow_start",
    "executorName": "init_context",
    "createdAt": "2026-08-16T00:00:00Z"
  }
}
```

## Stable durable event names

The UI, Playwright rubric, and docs depend on these durable event names staying stable unless the same change set updates every consumer:

- `workflow_start`
- `init_context`
- `retry_attempt`
- `retry_backoff`
- `retry_exhausted`
- `check_completed`
- `fan_in_result_received`
- `final_decision`
- `workflow_completed`
- `workflow_crashed`
- `resume_requested`
- `resume_completed`
- `idempotency_skip`

## CopilotKit contract

- Runtime discovery: `GET /api/v1/underwriting/copilotkit/info`
- Run route: `POST /api/v1/underwriting/copilotkit/agent/underwriting-run-assistant/run`
- The browser uses relative `/api` paths on the frontend origin.
- `/backend-health` is the same-origin verification path for backend health.

### Safe selected-run allowlist

The bridge may expose only:

- selected run id
- normalized status
- safe event names
- safe executor names and timestamps
- checkpoint count and latest checkpoint timestamp
- categorical final decision

It excludes application, applicant, health, credit, income, prompts, raw model output, checkpoint payloads, credentials, and secrets.

## No-shims rules

- Browser traffic stays on the external frontend's same-origin proxy contract.
- The internal backend starts or resumes hosted Responses work; it must not grow a second production orchestration contract.
- Durable reads for refresh, replay, and assistant explanation come from PostgreSQL-backed projections.
- Local-only validation settings must not leak into deployed public-lane behavior.

## Durability model

Production backend and hosted-agent environments set `DB_SCHEMA_MANAGED_EXTERNALLY=true`.

### Workflow state vs operator projections

- Native LangGraph PostgreSQL checkpoint state is the workflow-state source of truth for resume.
- Separate projections own run history, ordered workflow events, checkpoint summaries, underwriting results, idempotency evidence, and release evidence.
- Browser `/checkpoints` responses expose safe checkpoint metadata only.
- Projections must not duplicate authoritative checkpoint payloads.

## Hosted runtime secret contract

- The deterministic Foundry project connection is `underwritingruntimesecrets`, category or auth type `CustomKeys`.
- Its `database_url` key contains the least-privilege TLS runtime URL.
- Hosted agent runtime database values are literal `connections.underwritingruntimesecrets.credentials.database_url` placeholders.
- Verification compares that literal placeholder only and never requests the resolved password-bearing value.

## Telemetry conventions

- Application Insights is the required telemetry sink.
- Key browser and workflow correlation attributes remain:
  - `workflow.run_id`
  - `workflow.action`
  - `workflow_run_id`
  - `executor_name`
  - `checkpoint_id`
- Hosted telemetry must preserve request, retry, fan-in, checkpoint, idempotency, and final-decision correlation.
- Health and long-lived stream noise should stay filtered from request telemetry so workflow signal remains visible.

## Safe hosted evaluation evidence

- `foundry.responses.invoke` may contain redacted `gen_ai.input.messages` and `gen_ai.output.messages` only when required for report-only evaluation.
- Those summaries must contain only safe action, terminal-status, and decision information.
- They must not contain applicant input, checkpoint payloads, raw model output, or credentials.

## Operational checks

- Same-origin `/api` routes must return JSON or SSE, not HTML fallback content.
- Query Application Insights using `workflow.run_id` correlation first; portal newest-first lists are not sufficient release evidence.
- Fresh hosted evaluation evidence belongs in [issues-changes-fixes.md](issues-changes-fixes.md), not in repository configuration alone.
