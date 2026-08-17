# Project Structure

This document describes the **approved LangGraph target structure**. Legacy
MAF-named directories may still exist during migration, but they are not the
intended steady-state architecture.

```text
foundry-public/
  README.md
  backend/
    app/
      api/v1/
        routes/
        schemas/
      core/
      infrastructure/
        checkpointing/
        db/
        llm/
        repositories/
      langgraph/
        graph.py
        state.py
        nodes/
        prompts/
        tools/
        runtime.py
      modules/underwriting/
        agui.py
        projections.py
        service.py
      main.py
      server.py
    foundry/main.py
    tests/
    .foundry/
      datasets/
      results/
    Dockerfile.hosted
    eval.yaml
  frontend/
    src/
    tests/e2e/
  infra/
    foundry-hosted/
  scripts/
    foundry/
  docs/
    design/
```

## Boundary ownership

- `backend/app/api/v1/*`: stable HTTP, AG-UI, and CopilotKit contracts.
- `backend/app/modules/underwriting/*`: application service, business ports, durable projections, and safe selected-run projection logic.
- `backend/app/langgraph/*`: the single shared underwriting `StateGraph`, state schema, nodes, prompts, tools, and runtime wiring.
- `backend/app/infrastructure/*`: PostgreSQL repositories, checkpointer integration, idempotency storage, telemetry helpers, and Foundry wrapper clients.
- `backend/foundry/main.py`: thin Foundry Responses 2.0 host that invokes the shared application runtime rather than a second workflow.
- `frontend/src/*`: application form, run history, event timeline, recovery UI, and optional selected-run assistant projection.

## Structural rules

- Keep one runtime namespace for the business graph.
- Keep native checkpoint responsibilities separate from audit projections: the checkpointer stores workflow state; projections store operator history and release evidence.
- Treat generated hosted package output as deployment output, not source of truth. Sync it from canonical backend sources before packaging.
