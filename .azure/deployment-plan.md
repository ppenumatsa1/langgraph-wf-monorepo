# LangGraph Workflow Monorepo Deployment Plan

**Status:** Approved
**Approval source:** User explicitly requested autonomous local and Azure
deployment, validation, timing, evidence, and commits for order resolution and
underwriting on 2026-08-16.

## Scope

1. Complete order-resolution local gates:
   lint/tests, deterministic evals, Docker smoke, browser E2E, and design review.
2. Validate and deploy the order-resolution public Microsoft Foundry lane:
   Bicep/azd readiness, bootstrap when the target does not exist, PostgreSQL
   administrator schema setup and least-privilege runtime credentials, immutable
   backend/frontend/hosted-agent artifacts, smoke, hosted E2E, Foundry evals,
   Application Insights telemetry, and secret-free evidence.
3. Record measured duration and result for every local and Azure stage.
4. Commit the verified order-resolution changes and evidence.
5. Create the underwriting LangGraph public lane from the reference
   underwriting agent, preserving its business contract while replacing MAF
   orchestration with LangGraph.
6. Run the same local and Azure lifecycle for underwriting, record timings and
   fresh evidence, and commit the verified changes.

If order-resolution hosted E2E is blocked, record the exact failure and proceed
with underwriting rather than stopping the overall program.

## Azure context

- Subscription: `7df95e88-701c-4693-af77-3159f83b558d`
- Region: `eastus2`
- Order-resolution resource group: `rg-langgraph-ora-foundry-public`
- Underwriting resource group: derive a distinct deterministic LangGraph name
  from the underwriting lane and validate it before provisioning.

## Architecture

- External React/Nginx Container App
- Internal FastAPI wrapper Container App
- Microsoft Foundry Responses 2.0 hosted LangGraph agent
- Azure Database for PostgreSQL Flexible Server
- Azure Container Registry
- Application Insights and Log Analytics
- Managed identities and least-privilege RBAC
- Foundry model deployments, project connections, evaluations, and telemetry

## Safety and evidence

- Bootstrap may create missing lane-owned resources; reuse must be non-mutating.
- No stateful resource deletion or replacement is authorized.
- PostgreSQL DDL remains administrator-owned; runtime identities receive only
  required DML/sequence access.
- Deploy immutable image digests.
- Keep secrets and resolved database URLs out of source, metadata, logs, and
  committed evidence.
- Historical MAF deployment IDs and results are migration input only, never
  evidence for this repository.
- A lane is complete only after fresh local and hosted evidence is recorded.

## Execution gates

For each lane:

1. Prepare and package.
2. Local backend tests and deterministic evals.
3. Local Docker smoke and Playwright E2E.
4. Design/release review.
5. Azure validation and what-if.
6. Provision missing infrastructure or confirm non-mutating reuse.
7. Deploy immutable application and hosted-agent artifacts.
8. Verify deployment and run smoke.
9. Run hosted low-risk and HITL E2E.
10. Run Foundry evaluation.
11. Correlate Application Insights telemetry and exceptions.
12. Aggregate secret-free evidence and stage durations.
13. Commit changes with required Copilot trailers.
