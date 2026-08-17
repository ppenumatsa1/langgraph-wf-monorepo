# Copilot Instructions

This lane hosts the order-resolution LangGraph application directly on Azure
Container Apps.

- Keep one shared `StateGraph`; deterministic model fallback is a graph node,
  never a second orchestrator.
- Native PostgreSQL checkpoints are authoritative for HITL resume.
- Keep one unresolved interrupt per thread and preserve idempotent side effects.
- Production DDL is administrator-owned; runtime credentials have no `CREATE`.
- Preserve the six native SSE event types and the redacted, read-only
  AG-UI/CopilotKit boundary.
- Public topology is external frontend -> same-origin `/api` -> internal
  FastAPI -> LangGraph -> PostgreSQL.
- Foundry is model inference and report-only evaluation only. Never add
  `azure.ai.agent`, Responses hosted application hosting, agent versions, or
  hosted invocation behavior.
- Application Insights is required; LangSmith is not.
- Use approved CFS package feeds, non-root containers, managed-identity ACR
  pull, health probes, immutable image digests, and secret-free evidence.
- Bootstrap and routine app-only release are separate. GitHub Actions is
  credential-free and non-mutating.

Before LangGraph changes read `langgraph-docs` and `langgraph-foundry-py`.
Before Foundry inference/evaluation/telemetry changes read `microsoft-foundry`.
