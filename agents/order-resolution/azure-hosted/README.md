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

## Accepted Azure release

Release `order-resolution-azure-20260817T210042Z-623966` completed on
2026-08-17 against commit `0d22e98`.

Frontend:
https://orderresolution-jed2e5qyaxlau-we.wittyriver-92c74877.eastus2.azurecontainerapps.io

| Gate | Result | Duration |
| --- | --- | ---: |
| Local validation and IaC build | 78 backend tests, 11/11 deterministic evaluations, 10/10 local browser tests | 2m 09s |
| Model preflight | Passed | 8.503s |
| Immutable image builds | Passed | 2m 46.098s |
| Container App deployment | Passed | 1m 25.476s |
| Topology and security verification | Passed | 1m 01.723s |
| Azure smoke | Passed | 1.663s |
| Domain E2E | 3/3 passed, including low-risk and durable HITL | 10.561s |
| Azure browser E2E | 10/10 passed | 22.102s |
| Foundry report-only evaluation | 3/3 passed; zero failed or errored | 31.496s |
| Application Insights telemetry | 3/3 conversations, 92 rows, zero exceptions | 11.697s |
| Total release | Succeeded | 8m 39.427s |

Immutable images:

- Backend: `sha256:0a176c1d27d122772619cc35517802ae22c8e56f12dc66c70aede5f8d85c436b`
- Frontend: `sha256:f509b4ff56a07ba0af26f73ed81b302d50d0afdea26b1199da36935c1dc68ff0`
