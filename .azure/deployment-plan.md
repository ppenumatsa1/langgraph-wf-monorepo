# Order Resolution Foundry-Private Deployment Plan

**Status:** Validated
**Approval source:** The user approved the Foundry-private Order Resolution
plan and requested autonomous implementation through local proof, IaC,
deployment, smoke, E2E, evaluations, telemetry, evidence, review, and commit.

## Scope

Create and prove `agents/order-resolution/foundry-private` as an independently
deployable LangGraph lane. Preserve the proven business workflow, native
API/SSE event contract, PostgreSQL checkpoint authority, deterministic HITL,
idempotent side effects, redacted AG-UI/CopilotKit boundary, and Application
Insights observability.

## Azure context

- Subscription: `7df95e88-701c-4693-af77-3159f83b558d`
- Region: `eastus2`
- Resource group: `rg-langgraph-ora-foundry-private`
- AZD environment: `order-resolution-foundry-private`
- VNet: `10.74.0.0/16`
- Foundry subnet: `10.74.0.0/24`
- Container Apps subnet: `10.74.2.0/23`
- Private endpoint subnet: `10.74.4.0/24`
- Private runner subnet: `10.74.5.0/27`

## Architecture

- External React/Nginx Container App; the only public application ingress.
- Internal FastAPI wrapper Container App.
- Private network-injected Microsoft Foundry project and Responses 2.0 hosted
  LangGraph agent.
- Private PostgreSQL Flexible Server and native `AsyncPostgresSaver`.
- Private Premium ACR.
- Standard Agent Setup Storage, Cosmos DB, and AI Search dependencies.
- Application Insights, Log Analytics, and Azure Monitor private link scope.
- No-public-IP VM invoked through Managed Run Command.
- Managed identities and resource-scoped RBAC.

## Source and runner bootstrap

The exact committed release is pushed to the private
`ppenumatsa1/langgraph-wf-monorepo` GitHub repository. Managed Run Command
passes the GitHub credential and local AZD environment only as protected
parameters. The runner clones the exact commit without embedding credentials,
installs pinned dependencies, authenticates with managed identity, and removes
the managed Run Command resource after bootstrap. Images build and push from
the VNet runner through the private ACR endpoint; public ACR access is never
enabled.

## Safety and evidence

- Bootstrap may create the isolated lane; routine release is app-only.
- Noninteractive what-if must reject delete or replace operations.
- Foundry, ACR, PostgreSQL, backend, and runner public access remains disabled.
- PostgreSQL DDL is administrator-owned; runtime credentials are least
  privilege and TLS-only.
- Images and hosted versions are immutable.
- GitHub Actions remains credential-free validation and cannot mutate Azure.
- Secrets, tokens, resolved database URLs, and connection strings are excluded
  from source, logs, and evidence.
- Business HITL remains mandatory; deployment automation has no human approval
  flags or prompts.

## Execution gates

1. Local backend, frontend, deterministic evaluation, Docker, Playwright,
   skill, profile, IaC, and design-review gates.
2. Provider, quota, policy, RBAC, CIDR, Bicep, and deployment validation.
3. Fail-closed Azure what-if.
4. One-time isolated provisioning and reconciliation.
5. Protected private-runner source/dependency/AZD bootstrap.
6. PostgreSQL schema, least-privilege runtime credentials, and readiness.
7. VNet-side package build and private ACR push using immutable digests.
8. Backend, frontend, and hosted-agent deployment and activation.
9. Private DNS, endpoint, ingress, identity, digest, and version verification.
10. Smoke, three-scenario hosted E2E, and browser E2E.
11. Deterministic and Foundry report-only evaluations.
12. Correlated Application Insights telemetry and exception verification.
13. Atomic secret-free evidence with stage counts and durations.
14. Integrated Rubber Duck review, remediation, and final commit.

## All validation checks pass

- [x] 1. AZD installation
- [x] 2. `azure.yaml` schema validation
- [x] 3. Canonical AZD environment setup
- [x] 4. Azure CLI and AZD authentication
- [x] 5. Subscription, location, provider, quota, and CIDR checks
- [x] 6. Aspire pre-provisioning checks (not applicable)
- [x] 7. Fail-closed provision preview and what-if review
- [x] 8. Backend/frontend/local build verification
- [x] 9. Docker build-context and lockfile validation
- [x] 10. Private runner packaging-contract validation
- [x] 11. Azure Policy validation
- [x] 12. Aspire post-provisioning checks (not applicable)
- [x] 13. Bicep build, lint, target-scope validation, and private-network contract
- [x] 14. Runner NAT, no-public-NIC, managed identity, protected bootstrap, and
      scoped RBAC validation
- [x] 15. Secret, stale-public-identifier, generated-artifact, and Git diff
      checks

Validation results:

- `azure.yaml` passed the official stable schema.
- Azure CLI and AZD are authenticated to subscription
  `7df95e88-701c-4693-af77-3159f83b558d`; all required providers are
  registered in `eastus2`.
- Assigned subscription and management-group policies were inventoried. The
  fail-closed preview returned no policy denial.
- The preview initially exposed three configuration/capacity defects. The
  private lane now uses 50K TPM for chat, 50K TPM for evaluation, and 10K TPM
  for embeddings; `Standard_D2as_v7` for the 2-vCPU/8-GiB runner; and a
  Consumption workload profile without unsupported min/max fields.
- The final preview completed in 31 seconds with only planned creates and no
  delete or replace operations.
- Static role verification covers the backend, frontend, Foundry project, and
  private runner identities with resource- or resource-group-scoped roles;
  the runner's custom role grants only deployment-record operations.
- Private release contracts, deployment-profile contracts, Bicep compilation,
  Bicep lint, and private-network contracts passed after remediation.

## Section 7: Validation Proof

Recorded at `2026-08-20T15:54:41Z`.

| Validation | Command or tool | Result |
| --- | --- | --- |
| AZD installation | `azd version` | Passed with AZD `1.31.1`. |
| AZD authentication | `azd auth login --check-status --no-prompt` | Authenticated to the selected Azure account. |
| Environment | `make foundry-private-bootstrap-env` plus sanitized `azd env get-values` key inspection | Canonical `order-resolution-foundry-private` environment contains every required non-secret and generated secret key. |
| Azure YAML schema | Azure MCP `azd.validate_azure_yaml` | Passed the official stable schema. |
| Subscription/providers | `az account show` and `az provider show` for every required namespace | Target subscription is enabled and all required providers are registered in `eastus2`. |
| Policy | Azure MCP `policy.policy_assignment_list` | Subscription and inherited management-group assignments inventoried; final preview returned no policy denial. |
| VM capacity | `az vm list-skus --location eastus2 --resource-type virtualMachines --all` and `az vm list-usage --location eastus2` | `Standard_D2as_v7` is unrestricted, requires 2 of 100 available family vCPUs, and 2 of 96 available regional vCPUs. |
| Model capacity | `azd provision --preview --no-prompt` | Quota-safe values validated: 50K chat TPM, 50K evaluator TPM, and 10K embedding TPM. |
| Bicep/contracts | `make foundry-private-iac-build` | Bicep compiled and all private-network, target-port, runner, identity, and RBAC contracts passed. |
| Bicep lint | `az bicep lint --file infra/foundry-hosted/iac/main.bicep --no-restore --diagnostics-format sarif` | Zero errors, warnings, or notes. |
| Release automation | `make test-scripts test-deployment-profile` | Evidence tests and private release/profile contracts passed. |
| Backend | `make test` | Ruff passed and `144/144` pytest tests passed. |
| Frontend | `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint`, and `npm --prefix frontend run build` | Typecheck, lint, and production build passed. |
| Docker/local E2E | Existing integrated private-lane Docker and Playwright gates | Docker workflow `7/7`, workflow Playwright `7/7`, and selected-thread Playwright `7/7` passed before Azure validation. |
| Provision preview | `make foundry-private-what-if` | Passed in 31 seconds with planned creates only and no delete or replace operations. |
| Git/shell hygiene | `git diff --check`, `git diff --cached --check`, and `bash -n scripts/foundry-private/*.sh` | Passed. Generated runtime state and test scratch files remain excluded. |

Preview remediation history:

1. Reduced the initially overcommitted model capacities to the exact remaining
   Standard quota split.
2. Replaced unavailable `Standard_B2s` with unrestricted
   `Standard_D2as_v7`.
3. Removed unsupported min/max fields from the Container Apps Consumption
   workload profile.

## Stop conditions

Stop on destructive what-if output, unexpected existing state, public
resolution or exposure, unapproved private endpoints, missing private DNS,
unsupported capacity, privilege broadening, contaminated Foundry subnets,
mutable images, dirty or unpushed source, stale evidence, failed E2E/evaluation,
missing telemetry, or secrets in output.
