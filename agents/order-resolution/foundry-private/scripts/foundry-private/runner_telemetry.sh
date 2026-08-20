#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

[[ "$1" == "telemetry" ]] || private_die "private telemetry stage mismatch"
for command in az jq; do
  private_require_command "$command"
done
private_require_target

release_id="$(private_release_id)"
e2e_file="$PRIVATE_ROOT_DIR/.artifacts/private-runner-hosted-e2e-${release_id}.json"
[[ -f "$e2e_file" ]] ||
  private_die "fresh private hosted E2E evidence is required before telemetry validation"

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(private_azd_value AZURE_RESOURCE_GROUP)"
appinsights_name="$(private_required_env_value APPLICATION_INSIGHTS_NAME)"
started_at="$(jq -r '.started_at // empty' "$e2e_file")"
mapfile -t conversation_ids < <(jq -r '.conversation_ids[]? | select(type == "string" and length > 0)' "$e2e_file" | sort -u)
[[ -n "$started_at" && "${#conversation_ids[@]}" -eq 3 ]] ||
  private_die "private E2E evidence must contain a start time and exactly three conversations"
[[ "$started_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] ||
  private_die "private E2E evidence start time must be UTC ISO 8601"

conversation_ids_json="$(printf '%s\n' "${conversation_ids[@]}" | jq -R . | jq -sc .)"
query="$(cat <<EOF
let releaseStartedAt = todatetime('${started_at}');
let conversationIds = dynamic(${conversation_ids_json});
union withsource=source_table isfuzzy=true requests, dependencies, traces, customEvents, exceptions
| where timestamp between (releaseStartedAt .. now())
| extend dimensions = tostring(customDimensions)
| mv-expand conversationId = conversationIds
| extend conversation_id = tostring(conversationId)
| where dimensions has conversation_id
| summarize telemetry_rows=count(), exception_rows=countif(source_table == "exceptions") by conversation_id
| summarize matched_conversations=dcount(conversation_id), telemetry_rows=sum(telemetry_rows), exception_rows=sum(exception_rows)
EOF
)"

for attempt in $(seq 1 12); do
  result="$(az monitor app-insights query --subscription "$subscription_id" --resource-group "$resource_group" --app "$appinsights_name" --analytics-query "$query" --output json)"
  matched="$(jq -r '.tables[0].rows[0][0] // 0' <<<"$result")"
  rows="$(jq -r '.tables[0].rows[0][1] // 0' <<<"$result")"
  exceptions="$(jq -r '.tables[0].rows[0][2] // 0' <<<"$result")"
  if [[ "$matched" == "3" && "$rows" =~ ^[0-9]+$ && "$rows" -gt 0 && "$exceptions" == "0" ]]; then
    jq -n \
      --arg started_at "$started_at" \
      --argjson conversation_ids "$conversation_ids_json" \
      --argjson matched "$matched" \
      --argjson rows "$rows" \
      --argjson exceptions "$exceptions" \
      '{started_at:$started_at,conversation_ids:$conversation_ids,matched_count:$matched,telemetry_rows:$rows,exception_rows:$exceptions}'
    exit 0
  fi
  sleep 15
done

private_die "Application Insights did not correlate all three private conversations with zero exceptions"
