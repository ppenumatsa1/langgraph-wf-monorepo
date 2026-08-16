# Project Structure

This document describes the **approved LangGraph target structure**. Legacy
MAF-named directories may still exist during migration, but they are not the
intended steady-state architecture.

```text
order-resolution/
  backend/
    app/
      api/v1/
        routers/
        schemas/
      core/
      infrastructure/
        events/
        foundry/
        mcp/
        persistence/
        rag/
      langgraph/
        graph.py
        state.py
        nodes/
        prompts/
        tools/
        runtime.py
      modules/order_resolution/
        agui.py
        durable_events.py
        projections.py
        rich_events.py
        service.py
      main.py
    foundry/
      main.py
    tests/
    .foundry/
      datasets/
      evaluators/
      suites/
    Dockerfile.hosted
    eval.yaml
  frontend/
    src/
  infra/
    foundry-hosted/
  scripts/
    foundry/
    playwright/
    skills/
  docs/
    design/
```

## Boundary ownership

- `backend/app/api/v1/*`: stable HTTP and SSE contracts.
- `backend/app/modules/order_resolution/*`: application service, business
  ports, durable event replay, audit projections, and redacted AG-UI /
  CopilotKit projection logic.
- `backend/app/langgraph/*`: the single shared `StateGraph`, state schema,
  nodes, prompts, tools, and runtime wiring.
- `backend/app/infrastructure/*`: PostgreSQL repositories, checkpointer
  integration, MCP/RAG adapters, idempotency storage, and Foundry wrapper
  clients.
- `backend/foundry/main.py`: thin Foundry Responses 2.0 host that invokes the
  shared application/runtime path rather than a second workflow.
- `frontend/src/*`: native SSE timeline, approval UI, and optional selected
  thread projections.

## Structural rules

- Keep one runtime namespace for the business graph.
- Keep `AsyncPostgresSaver` responsibilities separate from audit projections:
  the checkpointer stores graph state; projections store history and operator
  views.
- Treat the generated hosted package as deployment output, not source of truth.
  Sync it from canonical backend sources before `azd package`.
