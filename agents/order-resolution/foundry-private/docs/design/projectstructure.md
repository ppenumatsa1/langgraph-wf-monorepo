# Project Structure

This document describes the target LangGraph source ownership and the private
hosted packaging boundary. Existing packaging directory names are retained
where the repository already depends on them; a path name is not a network
exposure policy.

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
  integration, MCP/RAG adapters, idempotency storage, and private Foundry
  wrapper clients.
- `backend/foundry/main.py`: thin private Foundry Responses 2.0 host that
  invokes the shared application/runtime path rather than a second workflow.
- `frontend/src/*`: native SSE timeline, approval UI, and optional selected
  thread projections.
- `infra/foundry-hosted/*`: existing hosted packaging and infrastructure
  boundary. It must express private endpoints, DNS, identities, and ingress
  policy when used by this lane.
- `scripts/*`: existing validation and release orchestration. The private
  runner is the only approved execution surface for authenticated Azure
  mutation.

## Structural rules

- Keep one runtime namespace for the business graph.
- Keep `AsyncPostgresSaver` responsibilities separate from audit projections:
  the checkpointer stores graph state; projections store history and operator
  views.
- Treat generated hosted package context as deployment output, not source of
  truth. Sync it from canonical backend sources before packaging.
- Keep private Foundry, PostgreSQL, and ACR access behind private endpoints and
  private DNS. Only the frontend is externally reachable.
- Keep deployment automation noninteractive and fail closed. It must not
  replace business HITL with an infrastructure approval prompt.
- Do not introduce a second workflow runtime or duplicate the graph in the
  hosted package.
