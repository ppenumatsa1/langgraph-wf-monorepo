#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

require_bin az
require_bin azd
require_bin jq
require_bin awk

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR"
get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
}
SUBSCRIPTION_ID="$(get_env AZURE_SUBSCRIPTION_ID)"
RESOURCE_GROUP="$(get_env AZURE_RESOURCE_GROUP)"
APPLICATION_INSIGHTS_NAME="${APPLICATION_INSIGHTS_NAME:-$(get_env APPLICATION_INSIGHTS_NAME)}"
[[ -n "$SUBSCRIPTION_ID" && -n "$RESOURCE_GROUP" && -n "$APPLICATION_INSIGHTS_NAME" ]] || {
  echo "Selected AZD environment must provide AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, and APPLICATION_INSIGHTS_NAME." >&2
  exit 1
}
[[ "$SUBSCRIPTION_ID" == "7df95e88-701c-4693-af77-3159f83b558d" ]] &&
  [[ "$RESOURCE_GROUP" == "rg-langgraph-ora-azure-hosted" ]] || {
  echo "Telemetry verification requires the canonical public target." >&2
  exit 1
}
LOOKBACK_MINUTES="${TELEMETRY_LOOKBACK_MINUTES:-30}"
MAX_ATTEMPTS="${TELEMETRY_MAX_ATTEMPTS:-12}"
EVIDENCE_FILE="${DOMAIN_E2E_EVIDENCE_FILE:-$ROOT_DIR/.artifacts/releases/${AZURE_RELEASE_ID:?AZURE_RELEASE_ID is required}/evidence/domain-e2e.json}"
REPORT_FILE="${APPINSIGHTS_EVIDENCE_FILE:-$ROOT_DIR/.artifacts/releases/$AZURE_RELEASE_ID/evidence/telemetry.json}"

[[ -f "$EVIDENCE_FILE" ]] || {
  echo "Domain E2E evidence is required: $EVIDENCE_FILE"
  exit 1
}

started_at="$(jq -r '.started_at // empty' "$EVIDENCE_FILE")"
mapfile -t conversation_ids < <(
  jq -r '
    [
      .conversation_ids[]?,
      .low_risk_thread_id?,
      .approved_thread_id?,
      .damaged_item_thread_id?
    ]
    | .[]
    | select(type == "string" and length > 0)
  ' "$EVIDENCE_FILE" | awk '!seen[$0]++'
)

[[ -n "$started_at" && "${#conversation_ids[@]}" -eq 3 ]] || {
  echo "Domain E2E evidence must contain started_at and three conversation IDs."
  exit 1
}

conversation_ids_json="$(printf '%s\n' "${conversation_ids[@]}" | jq -R . | jq -sc .)"

az account set --subscription "$SUBSCRIPTION_ID"
query=$(cat <<EOF
let e2eStartedAt = todatetime('${started_at}');
let conversationIds = dynamic(${conversation_ids_json});
union isfuzzy=true traces, dependencies, requests, customEvents, exceptions
| where timestamp between (e2eStartedAt .. now())
| extend dimensions = tostring(customDimensions)
| mv-expand conversationId = conversationIds
| where dimensions has tostring(conversationId)
| summarize
    matched_count = dcount(tostring(conversationId)),
    telemetry_rows = count(),
    exception_rows = countif(itemType == "exception")
EOF
)

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  result="$(
    az monitor app-insights query \
      --subscription "$SUBSCRIPTION_ID" \
      --resource-group "$RESOURCE_GROUP" \
      --app "$APPLICATION_INSIGHTS_NAME" \
      --analytics-query "$query" \
      -o json
  )"
  matched_count="$(echo "$result" | jq -r '.tables[0].rows[0][0] // 0')"
  telemetry_rows="$(echo "$result" | jq -r '.tables[0].rows[0][1] // 0')"
  exception_rows="$(echo "$result" | jq -r '.tables[0].rows[0][2] // 0')"
  if [[ "$telemetry_rows" -gt 0 && "$matched_count" -eq "${#conversation_ids[@]}" && "$exception_rows" -eq 0 ]]; then
    release_id="$AZURE_RELEASE_ID"
    release_started_at="$started_at"
    mkdir -p "$(dirname "$REPORT_FILE")"
    jq -n \
      --arg release_id "$release_id" \
      --arg release_started_at "$release_started_at" \
      --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --arg subscription_id "$SUBSCRIPTION_ID" \
      --arg resource_group "$RESOURCE_GROUP" \
      --arg application_insights_name "$APPLICATION_INSIGHTS_NAME" \
      --arg started_at "$started_at" \
      --argjson conversation_ids "$conversation_ids_json" \
      --argjson matched_count "$matched_count" \
      --argjson telemetry_rows "$telemetry_rows" \
      --argjson exception_rows "$exception_rows" \
      '{
        schema_version: 1,
        evidence_type: "telemetry",
        status: "passed",
        release_id: $release_id,
        release_started_at: $release_started_at,
        generated_at: $generated_at,
        subscription_id: $subscription_id,
        resource_group: $resource_group,
        application_insights_name: $application_insights_name,
        started_at: $started_at,
        conversation_ids: $conversation_ids,
        matched_count: $matched_count,
        telemetry_rows: $telemetry_rows,
        exception_rows: $exception_rows
      }' >"$REPORT_FILE"
    echo "Application Insights telemetry check passed: ${telemetry_rows} correlated rows for ${matched_count} domain E2E conversations."
    echo "Evidence written to ${REPORT_FILE}."
    exit 0
  fi
  echo "Awaiting correlated telemetry (attempt ${attempt}/${MAX_ATTEMPTS}; rows=${telemetry_rows}, conversations=${matched_count}/${#conversation_ids[@]}, exceptions=${exception_rows})."
  sleep 15
done

echo "Application Insights telemetry was not correlated to all current domain E2E conversations within the bounded wait."
exit 1
