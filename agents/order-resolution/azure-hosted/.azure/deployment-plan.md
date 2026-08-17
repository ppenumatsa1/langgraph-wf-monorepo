# Order Resolution Azure-hosted Deployment Plan

**Status:** Ready for Validation

## Target

- Subscription: `7df95e88-701c-4693-af77-3159f83b558d`
- Resource group: `rg-langgraph-ora-azure-hosted`
- Region: `eastus2`
- AZD environment: `order-resolution-azure-hosted`

## Runtime topology

Browser -> external React/Nginx Container App -> same-origin SSE-safe `/api`
proxy -> internal FastAPI Container App -> shared LangGraph `StateGraph` ->
PostgreSQL Flexible Server.

Microsoft Foundry supplies model inference and optional report-only evaluation.
It is not an application host. The lane has no `azure.ai.agent` service,
hosted-agent image, hosted version, or hosted invocation endpoint.

## Infrastructure lifecycle

1. Subscription-scope Bicep asserts the exact subscription, resource group, and
   region.
2. Reviewed bootstrap creates the resource group, ACR, monitoring, Container
   Apps environment/apps, PostgreSQL, Foundry account/project/models, identities,
   and least-privilege RBAC.
3. PostgreSQL DDL and runtime-role grants are administrator-owned.
   Dual authentication supports Entra administration and the restricted
   password runtime role; the server bootstrap password stays in local AZD
   state. The public-POC Azure-services firewall is accepted only with TLS and
   blocks production promotion until private networking or controlled egress.
4. Routine releases are app-only: validate, build immutable images, deploy the
   two Container Apps, verify, smoke, run domain/browser E2E, report-only
   evaluation, telemetry correlation, and aggregate secret-free evidence.
5. Routine release commands never provision or delete Azure resources.

## Validation

- `make test-skills`
- `make test-deployment-profile`
- `make test-scripts`
- `make azure-iac-build`
- `make test`
- `make eval-backend`
- `make test-e2e`
- `make azure-package`
