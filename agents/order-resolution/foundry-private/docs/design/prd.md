# PRD - Private Customer Order Resolution LangGraph Workflow

## Objective

Build a demo-ready order-resolution workflow on **one shared LangGraph
StateGraph** while preserving existing business behavior, browser contracts,
privacy boundaries, and private Foundry hosting.

## Core features

- Sequential business flow: triage -> policy retrieval -> resolution ->
  explanation or follow-up.
- Native LangGraph human approval with `interrupt()` and
  `Command(resume=...)`.
- Durable PostgreSQL checkpointing through `AsyncPostgresSaver`.
- Separate PostgreSQL audit projections for workflow runs, events, approvals,
  transcripts, and release evidence.
- Stable FastAPI and SSE contracts for the browser and Playwright suites.
- Same-origin frontend wrapper: the browser calls `/api`; only the internal
  wrapper uses managed identity to invoke private Foundry and PostgreSQL.
- Optional MCP integration and optional RAG integration behind backend-only
  ports.
- Application Insights observability and release evaluation evidence.
- Optional AG-UI and CopilotKit selected-thread projections that remain
  redacted and read only.
- Private ACR images and private-runner automation.

## Private-network requirements

The hosted lane uses an isolated primary BYO VNet with address space
`10.74.0.0/16` plus a globally peered `westus3` VNet for the Search
private endpoint.

| Component | Network contract |
| --- | --- |
| Foundry integration | `10.74.0.0/24`, private endpoint/integration |
| Container Apps | `10.74.2.0/23`; external frontend and internal wrapper |
| Private endpoints | `10.74.4.0/24` for Foundry, PostgreSQL, ACR, and approved services |
| Private runner | `10.74.5.0/27`, no public administrative ingress |
| Search private endpoint | `10.75.0.0/27`, same-region with Search and globally peered to the primary VNet |
| DNS and identity | Private DNS zones/links, managed identity, and least-privilege RBAC are mandatory |

Only the frontend is externally reachable. The wrapper, Foundry, PostgreSQL,
ACR, and runner remain private. A missing private prerequisite fails closed;
public endpoints are not fallback paths.

## Non-goals (v1)

- Parallel or branching business workflows.
- Browser-direct access to Foundry, MCP, RAG, PostgreSQL, ACR, or the runner.
- Production auth redesign.
- LangSmith adoption as a release prerequisite.
- Reusing historical architecture identifiers or success evidence as private
  lane proof.
- Interactive deployment prompts, confirmation tokens, or secret entry.

## Acceptance criteria

1. One customer request drives all business stages through one LangGraph graph.
2. The workflow emits stable native event names without breaking frontend or
   test consumers.
3. HITL pauses use native interrupts and durable PostgreSQL checkpointing.
4. Approval and rejection resume from saved checkpoint state with one
   idempotent outcome.
5. Low-risk cases complete without HITL.
6. The external frontend keeps a same-origin API/SSE contract while the
   internal wrapper delegates through private Foundry Responses 2.0.
7. The wrapper, Foundry, PostgreSQL, ACR, and runner are not browser reachable.
8. Private DNS, endpoint approval, managed identity, and least-privilege RBAC
   are validated before hosted smoke or E2E.
9. Telemetry exports to Application Insights with no LangSmith requirement.
10. Release automation runs noninteractively from the private runner and fails
    closed on unexpected targets, destructive plans, missing readiness, or
    secret-bearing evidence.
11. Business approval remains enforced through LangGraph `interrupt()` and
    `Command(resume=...)`; deployment gates cannot bypass it.
12. Release validation enforces least-privilege PostgreSQL access, immutable
    packaging, trace-age-aware evaluation, and evidence integrity.

## Delivery contract

Implementation authority and release evidence expectations are defined in
[engineering-operating-model.md](engineering-operating-model.md). The
[issues ledger](issues-changes-fixes.md) records adopted lessons and current
documentation changes without claiming live Azure success.
