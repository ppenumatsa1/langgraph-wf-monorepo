# Product Requirements

The product resolves customer order issues through one durable LangGraph
workflow with deterministic approval policy.

## Requirements

1. React browser experience behind same-origin `/api`.
2. Internal FastAPI executes the shared `StateGraph` directly.
3. PostgreSQL persists native checkpoints and durable audit projections.
4. Low-risk requests complete automatically; high-value and damaged-item
   actions pause for explicit review.
5. Decisions resume the same checkpoint and remain idempotent.
6. Foundry provides managed-identity model inference and report-only quality
   evaluation, never application hosting.
7. Application Insights provides correlation without recording sensitive
   content by default.
8. Bootstrap is guarded; routine release is immutable and app-only.
