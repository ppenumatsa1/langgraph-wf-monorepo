# Tech Stack

## Backend

- Python 3.11+ for API, worker, and hosted runtime surfaces
- FastAPI + Uvicorn
- Pydantic v2
- LangGraph `StateGraph` for orchestration
- LangGraph PostgreSQL checkpointer support for durable resume state
- OpenTelemetry SDK + Azure Monitor / Application Insights exporter

## Frontend

- React 19 + Vite + TypeScript
- Fetch-based durable API client for runs, history, state, events, and checkpoints
- AG-UI stream consumption for additive live timeline updates
- Optional `@copilotkit/react-core` selected-run view with strict redaction

## Data and durability

- PostgreSQL as the durable source of truth
- Native LangGraph checkpoint persistence for workflow resume
- Separate audit projections for workflow runs, workflow events, checkpoint summaries, underwriting results, idempotency records, and release evidence

## Integration and hosting

- Azure AI Foundry Responses 2.0 container hosting for the public hosted agent
- Azure Container Apps for the external frontend and internal FastAPI wrapper
- Same-origin Nginx proxy from the frontend to the internal backend
- Managed identity and project `CustomKeys` runtime-secret resolution for hosted execution

## Observability

- Application Insights is required for workflow, Foundry, model, and recovery telemetry
- Health and long-lived stream requests stay filtered from request telemetry in the public lane
- LangSmith is not required for this lane

## Reference baseline

- Historical MAF design docs and ledgers provide migration provenance only.
- The approved runtime primitives are LangGraph graph composition, native PostgreSQL checkpointing, Foundry Responses 2.0 hosting, and Application Insights correlation.
