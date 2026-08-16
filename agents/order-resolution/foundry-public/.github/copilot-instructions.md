# Copilot Instructions

This lane implements a LangGraph customer order-resolution workflow with
durable PostgreSQL checkpoints and human approval.

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

## Hosting and telemetry

- Public topology: external frontend Container App -> same-origin `/api` ->
  internal FastAPI wrapper -> Foundry Responses hosted agent -> PostgreSQL.
- Only managed identities call Foundry and Azure resources.
- Hosted database values use the deterministic project `CustomKeys`
  connection placeholder; never persist the resolved URL in metadata/evidence.
- Application Insights is the required observability backend. LangSmith is not
  required. Content recording remains disabled by default.
- Health and SSE request spans stay excluded so graph/model/HITL signal remains
  visible.

## Delivery

- Target subscription: `7df95e88-701c-4693-af77-3159f83b558d`
- Target region: `eastus2`
- Order resource group: `rg-langgraph-ora-foundry-public`
- GitHub Actions is credential-free CI only.
- Bootstrap creates missing lane-owned resources after reviewed validation.
- Routine releases are app-only and deploy immutable image digests.
- Preserve approved package feeds.
- Do not copy historical MAF deployment IDs or success claims as evidence.

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
