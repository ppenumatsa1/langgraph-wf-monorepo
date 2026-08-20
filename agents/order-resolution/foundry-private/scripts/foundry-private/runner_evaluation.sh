#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

[[ "$1" == "evaluation" ]] || private_die "private evaluation stage mismatch"
private_require_command jq
private_require_target

python="$PRIVATE_ROOT_DIR/backend/.venv/bin/python"
[[ -x "$python" ]] ||
  private_die "private runner requires backend/.venv for Foundry report-only evaluation"

release_id="$(private_release_id)"
e2e_evidence="$PRIVATE_ROOT_DIR/.artifacts/private-runner-hosted-e2e-${release_id}.json"
evaluation_evidence="$PRIVATE_ROOT_DIR/.artifacts/private-runner-evaluation-${release_id}.json"
[[ -f "$e2e_evidence" ]] ||
  private_die "fresh private HITL E2E evidence is required before evaluation"

e2e_started_at="$(jq -r '.started_at // empty' "$e2e_evidence")"
[[ -n "$e2e_started_at" ]] ||
  private_die "private HITL E2E evidence is missing its start time"

AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
FOUNDRY_AZD_DIR="$PRIVATE_AZD_DIR" \
FOUNDRY_AZD_ENV_NAME="$PRIVATE_EXPECTED_ENVIRONMENT" \
FOUNDRY_RELEASE_ID="$release_id" \
FOUNDRY_PROJECTS_ENDPOINT="$(private_required_env_value FOUNDRY_PROJECTS_ENDPOINT)" \
FOUNDRY_MODEL_DEPLOYMENT_NAME="$(private_required_env_value FOUNDRY_MODEL_DEPLOYMENT_NAME)" \
FOUNDRY_EVAL_MODEL="$(private_required_env_value FOUNDRY_EVAL_MODEL)" \
FOUNDRY_WORKFLOW_BASE_URL="$(private_required_env_value WEB_URL)" \
HOSTED_E2E_EVIDENCE_FILE="$e2e_evidence" \
FOUNDRY_E2E_EVIDENCE_NOT_BEFORE="$e2e_started_at" \
FOUNDRY_EVAL_EVIDENCE_FILE="$evaluation_evidence" \
FOUNDRY_EVAL_ENFORCE_PASS=true \
  "$python" -m evals.foundry_eval_runner >/dev/null

jq -e '
  .status == "completed"
  and .report_only == true
  and .trace_evaluation.fresh_workflow_snapshots == true
  and (.conversation_ids | type == "array" and length == 3)
  and ((.result_counts.passed // 0) | tonumber) > 0
  and ((.result_counts.failed // 0) | tonumber) == 0
  and ((.result_counts.errored // 0) | tonumber) == 0
' "$evaluation_evidence" >/dev/null ||
  private_die "private Foundry report-only evaluation did not pass"

jq '{evaluation_name,run_name,result_counts,trace_evaluation,report_only,conversation_ids}' \
  "$evaluation_evidence"
