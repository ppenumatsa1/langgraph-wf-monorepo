# Customer Q&A: Underwriting LangGraph Migration

This document summarizes how the underwriting lane answers common architecture, durability, privacy, and release questions after the UI, documentation, and skill migration.

## References

- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph checkpointers: https://docs.langchain.com/oss/python/langgraph/checkpointers
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph streaming: https://docs.langchain.com/oss/python/langgraph/streaming
- Foundry hosted LangGraph agents: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-hosted-agents
- LangGraph with Foundry Agent Service: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-agents

## What stays the same for operators?

The product contract stays the same:

- submit an application,
- pick happy, retry, or crash scenarios,
- inspect run history,
- watch four-check fan-in progress,
- inspect checkpoint and event timelines,
- resume a crashed run, and
- ask a selected-run assistant about safe execution metadata.

The migration changes the runtime explanation, not the operator workflow.

## What changes technically?

The authoritative runtime target changes from historical MAF provenance to:

- one shared LangGraph `StateGraph`,
- native PostgreSQL checkpoint durability,
- Foundry Responses 2.0 hosting, and
- Application Insights correlation.

The internal backend, same-origin proxy, and selected-run privacy boundary stay intact.

## How does four-check fan-in work after migration?

The approved graph shape is:

1. `init_context`
2. parallel risk, credit, medical, and driving checks
3. `fan_in_aggregator`
4. deterministic `final_decision`
5. optional rationale generation

Fan-in remains incremental and operator-visible. The UI still expects all four named checks to appear in shared state before the final decision is treated as complete.

## What is authoritative for resume?

Native PostgreSQL LangGraph checkpoint state is authoritative for workflow resume.

Separate application projections still exist for:

- run history,
- ordered workflow events,
- checkpoint summaries,
- underwriting results,
- idempotency evidence, and
- release evidence.

Those projections are durable operator views, not the source of truth for graph state.

## How do crash and resume avoid duplicate side effects?

Resume stays keyed by the durable underwriting run identity. The graph restores checkpointed state, continues only remaining work, and surfaces explicit `idempotency_skip` evidence whenever replay would otherwise repeat a completed side effect.

## What reaches the browser and CopilotKit?

The browser remains same-origin only and never receives Foundry or PostgreSQL credentials.

CopilotKit and AG-UI may expose only:

- selected run id,
- normalized status,
- safe event names,
- safe executor names and timestamps,
- checkpoint count and latest timestamp, and
- categorical final decision.

They must not expose application or applicant content, financial or medical fields, prompts, model output, checkpoint payloads, or secrets.

## How is telemetry validated?

Application Insights is the required telemetry backend. Release evidence must correlate:

- the public request,
- the hosted Foundry invocation,
- workflow and executor spans,
- retry or checkpoint behavior, and
- the durable `workflow.run_id`.

Evaluation remains report only and must use safe hosted evidence only.

## Can historical release success be reused?

No. Historical MAF release IDs, success claims, and deployment reports are migration provenance only. Fresh LangGraph-era smoke, Playwright, evaluation, and telemetry evidence must be regenerated after backend cutover.
