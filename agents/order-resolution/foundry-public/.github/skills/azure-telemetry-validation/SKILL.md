---
name: azure-telemetry-validation
description: Validate public Foundry hosted-agent telemetry in Application Insights after deployment.
---

# Azure Telemetry Validation Skill

Use this skill after public Foundry deployment to prove workflow, HITL,
dependency, trace, and exception telemetry is flowing into Application Insights.

## Required inputs

- Azure subscription/resource group context for the public Foundry project
- Application Insights component name
- `backend/.foundry/results/hosted-e2e-evidence.json`

## Hosted workflow stimulus

Run the hosted workflow cases before querying telemetry:

```bash
./scripts/foundry/hosted_e2e.sh
```

The hosted E2E covers low-risk, approval, rejection, and duplicate HITL
responses. Wait for Application Insights ingestion before querying.

## KQL checks

Use `az monitor log-analytics query --workspace "$AZURE_LOG_ANALYTICS_WORKSPACE_ID" --analytics-query '<KQL>'`.

### Table row counts

```kusto
let lookback=2h;
print
  AppRequestsRows=toscalar(AppRequests | where TimeGenerated > ago(lookback) | count),
  AppDependenciesRows=toscalar(AppDependencies | where TimeGenerated > ago(lookback) | count),
  AppTracesRows=toscalar(AppTraces | where TimeGenerated > ago(lookback) | count),
  AppEventsRows=toscalar(AppEvents | where TimeGenerated > ago(lookback) | count),
  AppExceptionsRows=toscalar(AppExceptions | where TimeGenerated > ago(lookback) | count)
```

### Workflow and HITL dependency spans

```kusto
let lookback=2h;
AppDependencies
| where TimeGenerated > ago(lookback)
| where Name in (
  "workflow.run",
  "workflow.hitl_waiting",
  "workflow.hitl_resume",
  "workflow.resolution_submit",
  "workflow.checkpoint_created",
  "workflow.hitl_request",
  "workflow.hitl_response",
  "workflow.workflow_output"
)
| project TimeGenerated, Name, OperationId, ParentId, Id,
    workflow_thread_id=tostring(Properties["workflow.thread_id"]),
    workflow_run_id=tostring(Properties["workflow.run_id"]),
    checkpoint_id=tostring(Properties["workflow.checkpoint_id"])
| order by TimeGenerated desc
```

Treat the business spans as the required correlation signal:
`workflow.run`, `workflow.hitl_waiting`, `workflow.hitl_resume`,
`workflow.hitl_response`, and `workflow.resolution_submit`. Event-specific
short spans such as `workflow.hitl_request` and `workflow.workflow_output` are
useful when exported, but Application Insights may ingest/drop very short child
spans differently. The persisted workflow event store remains the source of
truth for emitted SSE event contracts.

### HITL operation correlation

```kusto
let lookback=2h;
AppDependencies
| where TimeGenerated > ago(lookback)
| where Name in ("workflow.hitl_waiting", "workflow.hitl_resume", "workflow.hitl_request", "workflow.hitl_response", "workflow.workflow_output")
| extend workflow_thread_id=tostring(Properties["workflow.thread_id"])
| where isnotempty(workflow_thread_id)
| summarize
    names=make_set(Name),
    operations=make_set(OperationId),
    parents=make_set(ParentId),
    count=count()
  by workflow_thread_id
| where set_has_element(names, "workflow.hitl_request") and set_has_element(names, "workflow.hitl_response")
| order by count desc
```

### Request telemetry

```kusto
let lookback=2h;
AppRequests
| where TimeGenerated > ago(lookback)
| where Url !has "/health"
| where Url !has "/api/chat/stream/"
| project TimeGenerated, Name, Url, ResultCode, Success, OperationId, DurationMs
| order by TimeGenerated desc
```

Public FastAPI health and SSE request spans are intentionally excluded. Do not
fail this check because those paths are absent; use workflow dependencies and
Foundry readiness/invocation spans as the required signal.

### Attribute hygiene and exceptions

```kusto
let lookback=2h;
AppTraces
| where TimeGenerated > ago(lookback)
| where Message has "Invalid type NoneType for attribute"
| summarize count()
```

```kusto
let lookback=2h;
AppExceptions
| where TimeGenerated > ago(lookback)
| project TimeGenerated, Type, Message, OperationId
| order by TimeGenerated desc
```

## Pass/fail behavior

- Pass when Foundry E2E evidence exists, dependencies include
  workflow/LangGraph/Foundry/HITL business spans, HITL wait/resume/response spans share
  `workflow.thread_id` and the same trace operation after persisted trace-context
  restore, no new `NoneType` attribute warnings are present, and no new workflow
  exceptions appear.
- If HITL spans are split across operations, inspect checkpoint state persistence for `telemetry_trace_context` and confirm the approval path uses it as parent trace context.
