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

- PostgreSQL as the durable source of truth
- `AsyncPostgresSaver` for graph thread checkpoints and resume state
- Separate audit projections for workflow runs, workflow events, approvals,
  transcripts, idempotency keys, and release evidence

## Integration and hosting

- Azure AI Foundry Responses 2.0 container hosting for the public hosted agent
- Container Apps for the external frontend and internal FastAPI wrapper
- Managed identity between the wrapper and Foundry
- MCP over streamable HTTP when configured
- Optional RAG behind backend-only adapters

## Observability

- Application Insights is required for workflow, Foundry, model, and HITL
  telemetry
- FastAPI health and SSE request spans are filtered from request telemetry in
  the public lane
- LangSmith is optional in the wider ecosystem but **not required for this
  lane**

## Package acquisition policy

- Python packages in release images must use
  `https://packagefeedproxy.microsoft.io/pypi/simple`
- Frontend and Playwright package installs must use
  `https://packagefeedproxy.microsoft.io/npm/`

## Reference baseline

- Imported MAF design docs and ledger entries provide migration provenance and
  release lessons learned.
- LangGraph documentation defines the approved runtime primitives:
  `StateGraph`, `interrupt()`, `Command(resume=...)`, and
  `AsyncPostgresSaver`.
