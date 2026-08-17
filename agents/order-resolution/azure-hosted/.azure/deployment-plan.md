# Order Resolution Azure-hosted Deployment Plan

**Status:** Validated

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

- [x] All validation checks pass
  - [x] 1. AZD installation
  - [x] 2. `azure.yaml` schema validation
  - [x] 3. AZD environment setup
  - [x] 4. Azure authentication
  - [x] 5. Subscription and location validation
  - [x] 6. Aspire pre-provisioning checks (not applicable)
  - [x] 7. Provision preview
  - [x] 8. Build verification
  - [x] 9. Docker build-context validation
  - [x] 10. Package validation
  - [x] 11. Azure Policy validation
  - [x] 12. Aspire post-provisioning checks (not applicable)

Lane validation also runs `make test-skills test-deployment-profile
test-scripts azure-iac-build test eval-backend test-e2e azure-package`.

## Section 7: Validation Proof

Validated at `2026-08-17T19:06:31Z`.

| Check | Command or evidence | Result |
|---|---|---|
| AZD and authentication | `azd version`; `azd auth login --check-status` | Passed; AZD 1.31.1 and `ppenumatsa@microsoft.com` authenticated |
| Azure YAML | Azure MCP `validate_azure_yaml` | Passed against the stable schema |
| Target environment | `make azure-profile-apply`; `azd env get-values` | Passed for subscription `7df95e88-701c-4693-af77-3159f83b558d`, resource group `rg-langgraph-ora-azure-hosted`, region `eastus2` |
| Local build and contracts | `make validate-full test-scripts test-skills test-deployment-profile azure-iac-build azure-package` | Passed: 78 backend tests, 11/11 deterministic evaluations, 10/10 Playwright tests, scripts, skills, profile, Bicep, and both Docker images |
| Provision preview | `azd provision --preview --no-prompt` | Passed; 14 creates, no modify/delete/replace operations |
| Model quota | Preview after embedding capacity adjustment from 120K to 100K TPM | Passed within the available 110K TPM quota |
| Azure Policy | Azure MCP `policy_assignment_list` at subscription scope | Reviewed; preview passed under effective deny/deploy/audit assignments |
| Static RBAC | Bicep review | Passed: backend/frontend receive `AcrPull` only at ACR scope; backend receives Cognitive Services OpenAI User only at the Foundry account scope |
