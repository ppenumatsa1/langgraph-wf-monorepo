---
name: azure-telemetry-validation
description: Validate underwriting public-lane Application Insights and Foundry trace correlation after deployment.
---

# Azure Telemetry Validation Skill

Use this skill after deployed E2E writes evidence to prove the public adapter,
hosted workflow, and Foundry evaluation traces are correlated and safe.

## Required inputs

- Azure subscription/resource group context for the public underwriting lane
- Application Insights or Log Analytics access
- A recent `workflow_run_id` from smoke or hosted UI validation
- `backend/.foundry/results/hosted-smoke-evidence.json`
- `backend/.foundry/results/hosted-e2e-evidence.json`

## Stimulus

Before querying telemetry, refresh live evidence when needed:

```bash
make foundry-hosted-e2e
make foundry-telemetry
```

## Core lookup

Start from the durable run id:

```kusto
let workflowRunId = "run-...";
union isfuzzy=true requests, dependencies, traces, exceptions, customEvents
| where timestamp > ago(24h)
| where tostring(customDimensions["workflow.run_id"]) == workflowRunId
| project timestamp, itemType, name, operation_Id, operation_ParentId, success,
    workflowAction=tostring(customDimensions["workflow.action"])
| order by timestamp asc
```

## Required hosted span names

Look for the public request plus hosted spans such as:

- `foundry.responses.invoke`
- `underwriting.hosted.workflow`
- `workflow.stage.fan_out`
- `workflow.stage.risk_check`
- `workflow.stage.fan_in`
- `workflow.stage.final_decision`
- `workflow.stage.retry_attempt`
- `workflow.stage.retry_backoff`
- `workflow.stage.failure_injected`
- `workflow.stage.idempotency_skip`
- `workflow.checkpoint.save`
- `workflow.checkpoint.load`

## Safety checks

- Correlate start and resume by `workflow.run_id`; they may appear in separate hosted traces.
- Confirm telemetry attributes do not expose applicant names, health details, income, credit scores, checkpoint payloads, passwords, or secrets.
- Check for new exceptions on the same run id before declaring success.

## Pass/fail behavior

- Azure Monitor exports the hosted OpenTelemetry spans as `dependencies`.
  Require a public request plus `foundry.responses.invoke` and `workflow.*`
  dependency spans for **every** E2E workflow run; `traces` rows are
  supplemental evidence, not a required table type.
- Start this gate as soon as E2E writes evidence. It can wait for ingestion in
  parallel with trace evaluation.
- Pass when the public request, hosted workflow, checkpoint, retry/idempotency, fan-in, and final decision signals are present and safe.
- Fail when required spans are missing, correlation is broken, or protected data appears in telemetry.
