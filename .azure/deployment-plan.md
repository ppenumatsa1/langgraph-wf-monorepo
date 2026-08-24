# Order Resolution Foundry-Private Deployment Plan

**Status:** Blocked on Foundry hosted-compute activation
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
- Azure AI Search dependency region: `westus3`; Microsoft Learn currently
  marks `eastus2` as unavailable for new Search services and scaling. Search
  and its private endpoint use a small same-region VNet globally peered to the
  primary `eastus2` lane VNet.
- Resource group: `rg-langgraph-ora-foundry-private`
- AZD environment: `order-resolution-foundry-private`
- Primary VNet: `10.74.0.0/16`
- Foundry VNet: `10.76.0.0/16`
- Foundry subnet: `10.76.0.0/24`
- Foundry dependency endpoint subnet: `10.76.1.0/24`
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

## Live deployment status

The isolated Azure infrastructure, private endpoints and DNS, account and
project capability hosts, model deployments, private runner, PostgreSQL
bootstrap, immutable ACR packaging, and backend/frontend deployments are
complete. The remaining release stages are blocked because Foundry fails every
hosted version before creating a session.

The blocker is reproduced with immutable control images that use Microsoft's
official `azure-ai-agentserver-responses` host pattern and have no LangGraph,
PostgreSQL, runtime connection, telemetry override, or application
initialization. Control versions 4 and 5 failed after successful private ACR
pulls, including after:

- applying the current Standard Agent account-scoped Storage data roles;
- reconciling the project capability host through `2025-04-01-preview`;
- verifying both capability hosts are `Succeeded`;
- verifying account network injection targets the dedicated delegated subnet;
- verifying the project host references the expected private Storage, Cosmos
  DB, and Search connections.

Standalone control version 6 also failed using Microsoft's current sample
Docker shape and exact sample prerelease SDK versions installed through the
approved Microsoft feed. Private-runner Log Analytics queries confirmed
repeated pulls of its exact digest by the project identity from private
`10.74.0.x` addresses. This rules out production-image inheritance and stable
SDK-version drift.

The local-auth hypothesis is disproved. Both the known-good MAF private account
and the failing LangGraph accounts have `disableLocalAuth=true` with public
network access disabled. No policy exemption is required or justified.

The same standalone Microsoft Responses control became active and created a
session in the existing MAF private account and in a fresh account injected
into a new subnet in the MAF VNet. In the LangGraph VNet, it failed in the
original project, a fresh project, and two fresh accounts on independent
delegated `/24` subnets. Matching the MAF NAT, Cognitive Services service
endpoint, NSG, project RBAC, project connections, and exact Storage, Cosmos DB,
and Search dependencies did not resolve activation. The strongest failures
returned `invalid_configuration` and request IDs
`1e32f26f360f4fc0573cee5696f0a1df`,
`b1d31ec65ad691240ea08a83b8754038`, and
`53075aa912bf7ced00d9405fb0da07ef`.

The blocker is isolated to Foundry's managed network-injection/service-link
path for the LangGraph VNet even though ARM reports the account, capability
hosts, service association, and subnet as `Succeeded`. Microsoft must inspect
that service-side state before a production hosted version can be accepted.

The source now preserves the official Storage role contract, removes the
unnecessary per-version ACR role-assignment capability, and classifies hosted
and wrapper execution as `foundry-private-*`. A fresh full release must not run
until Microsoft resolves or explains the service-side hosted activation
failure. The sanitized reproduction and support handoff are tracked in
[repository issue #1](https://github.com/ppenumatsa1/langgraph-wf-monorepo/issues/1).

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

Recorded at `2026-08-20T15:54:41Z`; Search-region and two-phase Foundry
remediation revalidated at `2026-08-20T20:26:00Z`.

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
| Provision preview | `make foundry-private-what-if` with `DEPLOY_FOUNDRY_READY_RESOURCES=false`, then `true` | Phase-one and phase-two previews passed in 35 and 31 seconds with no delete or replace operations. |
| Git/shell hygiene | `git diff --check`, `git diff --cached --check`, and `bash -n scripts/foundry-private/*.sh` | Passed. Generated runtime state and test scratch files remain excluded. |

Preview remediation history:

1. Reduced the initially overcommitted model capacities to the exact remaining
   Standard quota split.
2. Replaced unavailable `Standard_B2s` with unrestricted
   `Standard_D2as_v7`.
3. Removed unsupported min/max fields from the Container Apps Consumption
   workload profile.
4. Moved the lane-owned S1 Search service and its private endpoint to
   `westus3`, where Search creation is supported, using a small same-region
   VNet globally peered to the primary `eastus2` VNet and private DNS linked
   to both.
5. Split Foundry bootstrap into two fail-closed previews/deployments with a
   bounded account and account-capability-host `Succeeded` gate between them.

## Stop conditions

Stop on destructive what-if output, unexpected existing state, public
resolution or exposure, unapproved private endpoints, missing private DNS,
unsupported capacity, privilege broadening, contaminated Foundry subnets,
mutable images, dirty or unpushed source, stale evidence, failed E2E/evaluation,
missing telemetry, or secrets in output.
