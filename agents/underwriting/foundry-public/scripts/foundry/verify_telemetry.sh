#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -n "${RELEASE_ID:-}" ]]; then
  . "$ROOT_DIR/scripts/foundry/release_paths.sh"
  release_paths_configure "$ROOT_DIR"
fi
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
EVIDENCE_FILE="${HOSTED_E2E_EVIDENCE_FILE:-$ROOT_DIR/backend/.foundry/results/hosted-e2e-evidence.json}"
REPORT_FILE="${APPINSIGHTS_EVIDENCE_FILE:-$ROOT_DIR/backend/.foundry/results/appinsights-evidence.json}"
MAX_ATTEMPTS="${TELEMETRY_MAX_ATTEMPTS:-12}"

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
}

required_env() {
  local name="$1"
  local value
  value="$(get_env "$name")"
  if [[ -z "$value" ]]; then
    echo "Missing AZD environment value: $name" >&2
    exit 1
  fi
  printf '%s' "$value"
}

require_bin az
require_bin azd
require_bin jq
require_bin awk

[[ -f "$EVIDENCE_FILE" ]] || {
  echo "Hosted E2E evidence is required: $EVIDENCE_FILE" >&2
  exit 1
}

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"

resource_group="$(required_env AZURE_RESOURCE_GROUP)"
subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
application_insights_name="$(required_env APPLICATION_INSIGHTS_NAME)"
az account set --subscription "$subscription_id" >/dev/null
started_at="$(jq -r '.started_at // .generated_at // empty' "$EVIDENCE_FILE")"
mapfile -t workflow_run_ids < <(
  jq -r '
    [
      .workflow_run_ids[]?,
      .happy_run_id?,
      .recovered_run_id?,
      .resume_run_id?
    ]
    | .[]
    | select(type == "string" and length > 0)
  ' "$EVIDENCE_FILE" | awk '!seen[$0]++'
)

[[ -n "$started_at" && "${#workflow_run_ids[@]}" -gt 0 ]] || {
  echo "Hosted E2E evidence does not contain a timestamp and workflow run IDs." >&2
  exit 1
}

workflow_run_ids_json="$(printf '%s\n' "${workflow_run_ids[@]}" | jq -R . | jq -sc .)"

query=$(cat <<'__KQL__'
let e2eStartedAt = todatetime('__STARTED_AT__');
let workflowRunIds = dynamic(__WORKFLOW_RUN_IDS__);
union isfuzzy=true requests, dependencies, traces, customEvents, exceptions
| where timestamp between (e2eStartedAt .. now())
| extend workflowRunId = tostring(customDimensions["workflow.run_id"])
| mv-expand workflowRunIdFilter = workflowRunIds
| where workflowRunId == tostring(workflowRunIdFilter)
| summarize
    matched_count = dcount(workflowRunId),
    telemetry_rows = count(),
    request_rows = countif(itemType == "request"),
    dependency_rows = countif(itemType == "dependency"),
    trace_rows = countif(itemType == "trace"),
    request_run_count = dcountif(workflowRunId, itemType == "request"),
    hosted_invocation_run_count = dcountif(
      workflowRunId,
      itemType == "dependency"
        and name == "foundry.responses.invoke"
        and isnotempty(tostring(customDimensions["gen_ai.agent.name"]))
    ),
    workflow_span_run_count = dcountif(
      workflowRunId,
      itemType == "dependency" and name startswith "workflow."
    ),
    exception_rows = countif(itemType == "exception")
__KQL__
)
query="${query/__STARTED_AT__/$started_at}"
query="${query/__WORKFLOW_RUN_IDS__/$workflow_run_ids_json}"

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  result="$(
    az monitor app-insights query \
      --subscription "$subscription_id" \
      --resource-group "$resource_group" \
      --app "$application_insights_name" \
      --analytics-query "$query" \
      -o json
  )"
  matched_count="$(printf '%s\n' "$result" | jq -r '.tables[0].rows[0][0] // 0')"
  telemetry_rows="$(printf '%s\n' "$result" | jq -r '.tables[0].rows[0][1] // 0')"
  request_rows="$(printf '%s\n' "$result" | jq -r '.tables[0].rows[0][2] // 0')"
  dependency_rows="$(printf '%s\n' "$result" | jq -r '.tables[0].rows[0][3] // 0')"
  trace_rows="$(printf '%s\n' "$result" | jq -r '.tables[0].rows[0][4] // 0')"
  request_run_count="$(printf '%s\n' "$result" | jq -r '.tables[0].rows[0][5] // 0')"
  hosted_invocation_run_count="$(printf '%s\n' "$result" | jq -r '.tables[0].rows[0][6] // 0')"
  workflow_span_run_count="$(printf '%s\n' "$result" | jq -r '.tables[0].rows[0][7] // 0')"
  exception_rows="$(printf '%s\n' "$result" | jq -r '.tables[0].rows[0][8] // 0')"
  if [[ "$telemetry_rows" -gt 0 &&
        "$matched_count" -eq "${#workflow_run_ids[@]}" &&
        "$request_run_count" -eq "${#workflow_run_ids[@]}" &&
        "$hosted_invocation_run_count" -eq "${#workflow_run_ids[@]}" &&
        "$workflow_span_run_count" -eq "${#workflow_run_ids[@]}" &&
        "$exception_rows" -eq 0 ]]; then
    mkdir -p "$(dirname "$REPORT_FILE")"
    jq -n \
      --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --arg resource_group "$resource_group" \
      --arg application_insights_name "$application_insights_name" \
      --arg started_at "$started_at" \
      --argjson workflow_run_ids "$workflow_run_ids_json" \
      --argjson matched_count "$matched_count" \
      --argjson telemetry_rows "$telemetry_rows" \
      --argjson request_rows "$request_rows" \
      --argjson dependency_rows "$dependency_rows" \
      --argjson trace_rows "$trace_rows" \
      --argjson request_run_count "$request_run_count" \
      --argjson hosted_invocation_run_count "$hosted_invocation_run_count" \
      --argjson workflow_span_run_count "$workflow_span_run_count" \
      --argjson exception_rows "$exception_rows" \
      '{
        generated_at: $generated_at,
        resource_group: $resource_group,
        application_insights_name: $application_insights_name,
        started_at: $started_at,
        workflow_run_ids: $workflow_run_ids,
        matched_count: $matched_count,
        telemetry_rows: $telemetry_rows,
        request_rows: $request_rows,
        dependency_rows: $dependency_rows,
        trace_rows: $trace_rows,
        request_run_count: $request_run_count,
        hosted_invocation_run_count: $hosted_invocation_run_count,
        workflow_span_run_count: $workflow_span_run_count,
        exception_rows: $exception_rows
      }' >"$REPORT_FILE"
    echo "Application Insights telemetry check passed: ${telemetry_rows} correlated rows for ${matched_count} hosted workflow runs."
    echo "Evidence written to ${REPORT_FILE}."
    exit 0
  fi
  echo "Awaiting correlated telemetry (attempt ${attempt}/${MAX_ATTEMPTS}; rows=${telemetry_rows}, runs=${matched_count}/${#workflow_run_ids[@]}, request-runs=${request_run_count}/${#workflow_run_ids[@]}, hosted-invocation-runs=${hosted_invocation_run_count}/${#workflow_run_ids[@]}, workflow-span-runs=${workflow_span_run_count}/${#workflow_run_ids[@]}, exceptions=${exception_rows})."
  sleep 15
done

echo "Application Insights telemetry was not correlated to all hosted E2E workflow_run_id values within the bounded wait." >&2
exit 1
