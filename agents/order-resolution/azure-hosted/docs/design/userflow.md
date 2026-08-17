# User Flow

1. The browser posts to same-origin `/api/chat/run`.
2. Nginx forwards the request to the internal FastAPI Container App.
3. FastAPI admits one turn for the thread and starts the shared LangGraph.
4. The graph retrieves order/policy context and emits durable projections.
5. Low-risk work completes and emits `workflow.output`.
6. High-risk or damaged-item work records `checkpoint.created` and
   `hitl.request`, then pauses with `interrupt()`.
7. A reviewer posts a decision to `/api/hitl/respond`.
8. FastAPI reconciles the pending projection with checkpoint state and resumes
   the same thread with `Command(resume=...)`.
9. Approval completes; rejection escalates; duplicate decisions are idempotent.

The browser never calls Foundry, PostgreSQL, MCP, or RAG services directly.
