# Copilot Instructions

This lane implements a LangGraph customer order-resolution workflow with
durable PostgreSQL checkpoints and human approval. Its hosted target is an
isolated private-network deployment; Foundry hosting is not a browser-facing
public application surface.

## Runtime contract

- Keep one shared LangGraph `StateGraph` for local FastAPI and Microsoft
  Foundry Responses 2.0 hosting.
- Model-unavailable deterministic triage is a node-level fallback inside the
  same graph, never a second orchestrator.
- `AsyncPostgresSaver` checkpoint state is authoritative for workflow state.
  Application tables provide audit/history/SSE projections.
- Allow only one unresolved interrupt per thread. Reject or explicitly defer
  normal turns while approval is pending.
- Emit `checkpoint.created` and `hitl.request` during idempotent approval
  preparation, not from the replayed interrupt node.
- Resume with `Command(resume=...)` on the same thread and reconcile the
  approval projection against graph state before applying a decision.
- Protect every side-effecting resolution with business idempotency.
- PostgreSQL DDL is administrator-owned. Hosted runtimes set
  `DB_SCHEMA_MANAGED_EXTERNALLY=true` and must not receive schema ownership or
  broad `CREATE`.

## Stable application boundaries

- HTTP/SSE: `backend/app/api/v1/routers/*`
- API schemas: `backend/app/api/v1/schemas/*`
- Domain/service/projections: `backend/app/modules/order_resolution/*`
- Configuration/database/telemetry: `backend/app/core/*`
- Adapters: `backend/app/infrastructure/*`
- LangGraph runtime: `backend/app/langgraph/*`
- Hosted entrypoint: `backend/foundry/main.py`

Do not remove or rename:

- `workflow.stage`
- `tool.call`
- `checkpoint.created`
- `hitl.request`
- `hitl.response`
- `workflow.output`

Native SSE and durable workflow APIs remain authoritative. AG-UI and
CopilotKit are additive, read-only, selected-thread projections. They must not
start/resume work or expose order/policy/MCP/RAG payloads, prompts, raw model
output, checkpoint state, credentials, or secrets.

## Private hosting and telemetry

- Private topology: external frontend Container App -> same-origin `/api` ->
  internal FastAPI wrapper -> private Foundry -> private PostgreSQL.
- Private ACR supplies immutable images to the frontend and wrapper. A private
  runner in the runner subnet performs authenticated automation; GitHub Actions
  remains credential-free CI only.
- The application BYO VNet is `10.74.0.0/16`; Foundry network injection uses
  the separate `10.76.0.0/16` VNet. The design reserves `10.76.0.0/24` for
  Foundry integration, `10.76.1.0/24` for Foundry dependency endpoints,
  `10.74.2.0/23` for Container Apps,
  `10.74.4.0/24` for private endpoints, and `10.74.5.0/27` for the runner.
- Private endpoints and private DNS are required for Foundry, PostgreSQL, and
  ACR. Only the frontend has external ingress; the wrapper has internal
  ingress and the private services have no browser path.
- Only managed identities call Foundry, ACR, PostgreSQL, and other Azure
  resources. Hosted database values use the deterministic project `CustomKeys`
  connection placeholder; never persist a resolved URL in metadata or evidence.
- Application Insights is the required observability backend. LangSmith is not
  required. Content recording remains disabled by default.
- Health and SSE request spans stay excluded so graph/model/HITL signal remains
  visible.

## Automation safety

- Azure previews, bootstrap, and release automation run without prompts,
  confirmation tokens, or interactive secret entry.
- Automation fails closed on an unexpected target, missing private DNS or
  identity prerequisites, delete/replace operations, readiness failures, or
  secret-bearing evidence. It must report the blocker rather than continue.
- Deployment safety gates are not business approval. The workflow's native
  `interrupt()` and `Command(resume=...)` HITL path remains mandatory for
  risky order resolutions.

## Delivery

- Subscription, resource group, region, and names come from the selected
  secret-free private deployment profile; do not hard-code them in source,
  skills, or evidence.
- The private runner is the only approved location for authenticated Azure
  mutation. GitHub Actions is credential-free CI only.
- Bootstrap creates missing lane-owned resources only after a noninteractive
  preview passes. Routine releases are app-only and deploy immutable image
  digests without reconciling infrastructure.
- Preserve approved package feeds.
- Do not copy historical MAF resource IDs, deployment IDs, endpoints, or
  success claims as evidence.

Required local gates:

```bash
make test
make eval-backend
make test-e2e
make docker-test
./scripts/skills/design-review-skill.sh
```

Required deployment gates:

```bash
make test-deployment-profile
make test-scripts
make foundry-iac-build
make foundry-package
make foundry-verify
make foundry-evidence
```

Read the lane-local `langgraph-docs` and `langgraph-foundry-py` skills before
changing graph code. Read `microsoft-foundry` before changing hosted-agent
deployment, evaluation, or telemetry behavior.
