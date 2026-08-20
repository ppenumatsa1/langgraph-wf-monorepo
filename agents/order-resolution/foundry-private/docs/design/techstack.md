# Tech Stack

## Backend

- Python 3.12+ for the API and hosting surfaces
- FastAPI + Uvicorn
- Pydantic v2
- LangGraph `StateGraph` for orchestration
- LangGraph PostgreSQL checkpointer support via `AsyncPostgresSaver`
- httpx for MCP HTTP calls
- OpenTelemetry SDK + Azure Monitor / Application Insights exporter

## Frontend

- React + Vite + TypeScript
- Native SSE timeline as the primary operator contract
- Optional `@copilotkit/react-core` selected-thread view with redacted data only

## Data and durability

- Private PostgreSQL as the durable source of truth
- `AsyncPostgresSaver` for graph thread checkpoints and resume state
- Separate audit projections for workflow runs, workflow events, approvals,
  transcripts, idempotency keys, and release evidence
- TLS, private endpoint, private DNS, managed identity, and least-privilege
  runtime grants for hosted PostgreSQL access

## Integration and hosting

- Azure AI Foundry Responses 2.0 private hosted agent
- Container Apps for the external frontend and internal FastAPI wrapper
- Managed identity between the wrapper and private Foundry
- Private ACR for immutable runtime images
- Private runner for noninteractive validation, packaging, and approved Azure
  mutation
- MCP over streamable HTTP when configured
- Optional RAG behind backend-only adapters

The hosted topology is:

```text
External frontend
  -> internal FastAPI wrapper
  -> private Foundry
  -> private PostgreSQL

Private ACR -> immutable images
Private runner -> validation and approved Azure mutation
```

The isolated BYO VNet is `10.74.0.0/16`:

- Foundry integration: `10.74.0.0/24`
- Container Apps: `10.74.2.0/23`
- Private endpoints: `10.74.4.0/24`
- Private runner: `10.74.5.0/27`

Only the frontend has external ingress. Private DNS zones/links and endpoint
approval are mandatory; public dependency endpoints are not fallback paths.

## Observability

- Application Insights is required for workflow, Foundry, model, and HITL
  telemetry.
- Workflow and dependency spans are correlated by thread, run, checkpoint,
  and event identifiers.
- Health and long-lived SSE requests may be filtered from request telemetry
  when they obscure workflow signal, but workflow, Foundry, model, and HITL
  spans remain required.
- LangSmith is not required for runtime, release, or evaluation gating.

## Package acquisition policy

- Python packages in release images must use
  `https://packagefeedproxy.microsoft.io/pypi/simple`.
- Frontend and Playwright package installs must use
  `https://packagefeedproxy.microsoft.io/npm/`.

## Reference baseline

- Imported architecture material provides adopted operational lessons only.
- LangGraph documentation defines the approved runtime primitives:
  `StateGraph`, `interrupt()`, `Command(resume=...)`, and
  `AsyncPostgresSaver`.
- Microsoft Foundry documentation defines hosted-agent, identity, network,
  and Application Insights integration behavior.
- Repository configuration expresses target intent; it is not live Azure
  evidence.
