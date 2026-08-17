# Agents Guide

## Product contract

- One shared LangGraph `StateGraph` runs locally and in the internal FastAPI
  Container App.
- Foundry provides model inference and report-only evaluation only.
- The browser reaches only the external frontend and its same-origin `/api`
  proxy; the backend has internal ingress.
- Native PostgreSQL checkpoints are authoritative. Durable workflow, event,
  approval, transcript, and evidence rows are derived audit projections.
- At most one unresolved interrupt exists per thread.
- Resume uses `Command(resume=...)` against the same checkpoint/thread.
- Side effects remain idempotent and production DDL remains administrator-owned.

Do not add an `azure.ai.agent` service, Responses hosted-agent wrapper,
hosted-agent image/version/invocation path, or a second workflow orchestrator.

## Stable boundaries

- API/SSE: `backend/app/api/v1/routers`
- Schemas: `backend/app/api/v1/schemas`
- Domain/projections: `backend/app/modules/order_resolution`
- Configuration/database/telemetry: `backend/app/core`
- Adapters: `backend/app/infrastructure`
- LangGraph: `backend/app/langgraph`

Preserve `workflow.stage`, `tool.call`, `checkpoint.created`, `hitl.request`,
`hitl.response`, and `workflow.output`.

## Hosting and delivery

- External frontend Container App; internal backend Container App.
- ACR pull uses managed identities.
- Backend identity receives least-privilege Foundry model inference access.
- Application Insights and Log Analytics are required; LangSmith is not.
- Deployment profiles are parsed as data and contain no secrets.
- Bootstrap is explicitly approved; routine release is app-only.
- Immutable image digests are mandatory.
- GitHub Actions cannot authenticate to or mutate Azure.

## Required validation

```bash
make test-skills
make test-deployment-profile
make test-scripts
make azure-iac-build
make test
make eval-backend
make test-e2e
./scripts/skills/design-review-skill.sh
```
