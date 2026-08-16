# Order Resolution LangGraph Public Deployment Plan

**Status:** Validated
**Scope:** `agents/order-resolution/foundry-public`
**Approval:** User explicitly requested autonomous local validation, Azure
provision/deploy, hosted smoke/E2E/evals/telemetry, timing, evidence, and commit.

## Target

| Setting | Value |
| --- | --- |
| Subscription | `7df95e88-701c-4693-af77-3159f83b558d` |
| Resource group | `rg-langgraph-ora-foundry-public` |
| Location | `eastus2` |
| Bootstrap environment | `order-resolution-bootstrap` |
| Reuse environment | `order-resolution-foundry-public` |
| Name prefix | `orderresolution` |
| Hosted agent | `order-resolution-hosted` |

The target resource group does not currently exist. Validation must review the
bootstrap what-if before creation. No stateful deletion or replacement is
authorized.

## Application topology

```text
browser
  -> external React/Nginx Container App
  -> same-origin /api proxy
  -> internal FastAPI wrapper Container App
  -> Microsoft Foundry Responses 2.0 hosted LangGraph agent
  -> Azure Database for PostgreSQL Flexible Server
```

The lane also provisions or connects Azure Container Registry, Log Analytics,
Application Insights, Foundry account/project/model deployments, managed
identities, project connections, evaluation storage, and least-privilege RBAC.

## Runtime contracts

- One shared LangGraph `StateGraph` serves local and hosted execution.
- `AsyncPostgresSaver` owns graph checkpoints; administrator bootstrap owns its
  DDL and the application audit schema.
- Runtime identities receive only required DML and sequence privileges.
- One unresolved interrupt is allowed per thread.
- Native checkpoint state is authoritative; approval UUID rows are idempotent
  audit/reconciliation projections.
- Stable browser events remain `workflow.stage`, `tool.call`,
  `checkpoint.created`, `hitl.request`, `hitl.response`, and
  `workflow.output`.
- AG-UI/CopilotKit remain redacted read-only selected-thread projections.
- Application Insights is the required telemetry backend; content recording is
  disabled by default.

## Preparation completed

- Backend migrated from MAF to LangGraph.
- Approved package feed versions are pinned, including `langgraph==1.2.10`.
- Backend tests, deterministic evals, frontend build, targeted Playwright, and
  Docker image builds have passed during implementation.
- Bicep build, profile tests, and release-script tests have passed.
- `make foundry-package` now seeds a dedicated local-only
  `order-resolution-package-validation` AZD environment, derives the
  deterministic non-secret lane names, and runs `azd package` without Azure
  hydration or provisioning.
- The final full local gate passed in `141.40s`: 124 backend tests, 11/11
  deterministic evaluations, 7 workflow E2E tests, 3 selected-thread E2E
  tests, and the deterministic design review.
- Deployment/profile/script/Bicep/package validation passed in `84.31s`.
- The exact `azd provision --preview` completed in `30.21s` with 14
  create-only resources and no deletion or replacement.
- Standard GPT-4.1-mini capacity was reduced to 1,750K TPM for chat plus 250K
  TPM for evaluation because subscription usage is 2,750K/5,000K; the
  validated target leaves a 250K TPM safety margin after provisioning.
- Subscription policy assignments were reviewed. The enforced classic-resource
  deny policy does not apply to this architecture, and `eastus2` is allowed.

## Validation and deployment sequence

1. Complete full local timed gates and deterministic design review.
2. Run Azure validation workflow and bootstrap what-if.
3. Confirm providers, quota/capacity, identities, RBAC, model deployment set,
   PostgreSQL SKU/network/TLS, and Application Insights connection.
4. Provision the missing lane-owned public resources.
5. Run administrator schema and runtime credential/readiness gates.
6. Package and deploy backend, frontend, and hosted agent by immutable digest.
7. Verify exact revisions/images, ingress topology, connections, RBAC,
   placeholders, health, and readiness.
8. Run hosted smoke.
9. Run fresh low-risk, high-risk approval/resume, and damaged-item E2E.
10. Run Foundry evaluation only against fresh eligible traces.
11. Correlate Application Insights requests/dependencies/traces/exceptions.
12. Generate one secret-free release evidence report with stage durations.

### All validation checks pass

- [x] 1. AZD Installation
- [x] 2. Schema Validation
- [x] 3. Environment Setup
- [x] 4. Authentication Check
- [x] 5. Subscription/Location Check
- [x] 6. Aspire Pre-Provisioning Checks (not applicable)
- [x] 7. Provision Preview
- [x] 8. Build Verification
- [x] 9. Docker Build Context Validation
- [x] 10. Package Validation
- [x] 11. Azure Policy Validation
- [x] 12. Aspire Post-Provisioning Checks (not applicable)

## Section 7: Validation Proof

Validated on `2026-08-16` against subscription
`7df95e88-701c-4693-af77-3159f83b558d` in `eastus2`.

| Command/check | Result |
| --- | --- |
| `azd version`, `az version`, `az bicep version`, `docker --version` | Passed; required CLIs are installed. |
| Azure MCP `validate_azure_yaml` for `infra/foundry-hosted/azure.yaml` | Passed against the stable schema. |
| `az account show`, `azd auth login --check-status` | Passed for `ppenumatsa@microsoft.com` and the approved subscription. |
| Subscription role assignment check | Passed; deployer has `Owner` and `Foundry User`. |
| Azure Policy assignment/rule review | Passed; no applicable deny blocks the planned resource types or `eastus2`. |
| GPT-4.1-mini and embedding quota review | Passed after setting chat capacity to 1,750K TPM and evaluator capacity to 250K TPM, leaving 250K Standard GPT capacity after deployment. |
| `azd provision --preview --no-prompt` | Passed in `30.21s`; 14 create-only resources, no deletion or replacement. |
| Timed `make validate-full` | Passed in `141.40s`; 124 backend tests, 11/11 deterministic evals, 7 workflow E2E tests, 3 selected-thread E2E tests, and design review. |
| `make test-deployment-profile test-scripts foundry-iac-build foundry-package` | Passed in `84.31s`; 29 script tests, shell contracts, Bicep compilation, and local-only hosted packaging succeeded. |
| Static Bicep RBAC contract | Passed; 10 conditional scoped role assignments compile successfully. |

## Stop conditions

- Unexpected deletion/replacement or stateful mutation in what-if.
- Subscription, region, resource group, or environment mismatch.
- Package acquisition outside approved feeds.
- PostgreSQL runtime DDL or excessive privileges.
- Missing model/quota capacity.
- Failed immutable image, health, topology, RBAC, secret-placeholder, smoke,
  E2E, evaluation, telemetry, or evidence-integrity gate.

Local package validation must stay non-mutating: it may write only the local
AZD package-validation environment and Docker artifacts. Any attempt to query
or hydrate live Azure state is a blocker for the package gate.

If hosted E2E fails, record the exact blocker and continue implementation of
the underwriting lane as requested.
