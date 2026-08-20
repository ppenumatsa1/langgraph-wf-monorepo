---
name: azure-telemetry-validation
description: Validate private Foundry workflow telemetry in Application Insights after deployment.
---

# Azure Telemetry Validation Skill

Use this skill after private Foundry deployment to prove workflow, HITL,
dependency, trace, and exception telemetry is flowing into Application
Insights. Application Insights is the required observability backend; LangSmith
is not a release or evaluation dependency.

## Required inputs

- Azure subscription/resource-group context for the selected private lane
- Application Insights component/workspace name
- `backend/.foundry/results/hosted-e2e-evidence.json`
- A private runner or approved network path that can reach the monitoring
  control plane without exposing private application endpoints

## Hosted workflow stimulus

Run the workflow cases before querying telemetry:

```bash
make foundry-private-hosted-e2e
```

The E2E covers low-risk, approval, rejection, and duplicate HITL responses.
Wait for Application Insights ingestion before querying. This stimulus is not
deployment evidence until the run is complete and release-window scoped.

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
short spans are useful when exported, but the persisted workflow event store
remains the source of truth for the SSE contract.

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

Frontend health and SSE request spans are intentionally excluded. Do not fail
this check because those paths are absent; use workflow dependencies, private
Foundry invocation, and readiness spans as the required signal.

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

- Pass when E2E evidence exists, dependencies include workflow/LangGraph/
  Foundry/HITL business spans, HITL wait/resume/response spans share
  `workflow.thread_id` and the same trace operation after persisted
  trace-context restore, no new `NoneType` attribute warnings are present, and
  no new workflow exceptions appear.
- If HITL spans are split across operations, inspect checkpoint state
  persistence for `telemetry_trace_context` and confirm the approval path uses
  it as parent trace context.
- Never treat an Application Insights row count as proof that private DNS,
  private endpoints, or the deployment itself succeeded; correlate it to the
  same release window and private workflow evidence.
