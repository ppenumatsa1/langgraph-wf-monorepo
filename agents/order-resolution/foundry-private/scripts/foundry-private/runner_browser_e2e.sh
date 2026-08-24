#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

[[ "$1" == "browser_e2e" ]] || private_die "private browser E2E stage mismatch"
for command in jq node npm; do
  private_require_command "$command"
done
private_require_target

web_url="$(private_required_env_value WEB_URL)"
[[ "$web_url" =~ ^https:// ]] || private_die "private WEB_URL must use HTTPS"

release_id="$(private_release_id)"
log_dir="$PRIVATE_ROOT_DIR/.artifacts/private-browser-logs/$release_id"
mkdir -p "$log_dir"
chmod 700 "$log_dir"

run_browser_suite() {
  local name="$1"
  local directory="$2"
  shift 2
  local log_file="$log_dir/${name}.log"
  if ! (
    cd "$directory"
    PLAYWRIGHT_BASE_URL="$web_url" \
      PLAYWRIGHT_CASE_DELAY_MS=20000 \
      PLAYWRIGHT_EXPECT_TIMEOUT_MS=60000 \
      PLAYWRIGHT_TEST_TIMEOUT_MS=150000 \
      "$@"
  ) >"$log_file" 2>&1; then
    printf 'Private browser suite failed: %s\n' "$name" >&2
    tail -c 4000 "$log_file" | private_redact_stream >&2
    return 1
  fi
}

run_browser_suite workflow "$PRIVATE_ROOT_DIR/scripts/playwright" \
  npm run test:e2e -- --workers=1
run_browser_suite selected-thread "$PRIVATE_ROOT_DIR/frontend" \
  npm run test:e2e -- tests/e2e/selected-thread-integrations.spec.ts --workers=1

jq -n --arg web_url "$web_url" \
  '{web_url:$web_url,private_runner:true,workflow_browser_e2e:"passed",selected_thread_e2e:"passed"}'
