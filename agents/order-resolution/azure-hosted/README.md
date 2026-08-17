# Order Resolution — Azure-hosted LangGraph

This lane runs the authoritative order-resolution LangGraph workflow directly
inside FastAPI on Azure Container Apps.

## Architecture

```text
Browser
  -> external React/Nginx Container App
  -> same-origin, SSE-safe /api proxy
  -> internal FastAPI Container App
  -> shared LangGraph StateGraph
  -> PostgreSQL Flexible Server
```

Microsoft Foundry is used only for model inference and optional report-only
evaluation. It does not host the application. There is no `azure.ai.agent`
service, hosted-agent version, hosted container, or hosted invocation path.

PostgreSQL native LangGraph checkpoints are authoritative for paused graph
state. Administrator-owned schema scripts create the checkpoint and durable
audit projection tables; the runtime credential receives only required
DML/sequence privileges.

## Local development

```bash
make bootstrap
make up
make test
make eval-backend
make test-e2e
```

The stable native API/SSE event types remain:

- `workflow.stage`
- `tool.call`
- `checkpoint.created`
- `hitl.request`
- `hitl.response`
- `workflow.output`

AG-UI and CopilotKit are additive, redacted, read-only projections.

## Azure lifecycle

Target: subscription `7df95e88-701c-4693-af77-3159f83b558d`, resource group
`rg-langgraph-ora-azure-hosted`, region `eastus2`, AZD environment
`order-resolution-azure-hosted`.

```bash
make azure-profile-apply
make test-skills test-deployment-profile test-scripts azure-iac-build
```

After setting the PostgreSQL administrator values:

```bash
make azure-bootstrap
make azure-postgres-schema azure-postgres-credentials
```

Bootstrap generates the PostgreSQL server-creation password only in local AZD
environment state. It previews infrastructure and stops automatically on
delete or replace operations. The POC database path is public with TLS and a
restricted runtime role; production requires private networking or controlled
egress.

Routine releases are app-only and immutable:

```bash
make azure-release
```

GitHub Actions is credential-free CI only and never mutates Azure resources.
