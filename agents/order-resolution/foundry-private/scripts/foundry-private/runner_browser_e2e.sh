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

(
  cd "$PRIVATE_ROOT_DIR/scripts/playwright"
  PLAYWRIGHT_BASE_URL="$web_url" npm run test:e2e
) >/dev/null
(
  cd "$PRIVATE_ROOT_DIR/frontend"
  PLAYWRIGHT_BASE_URL="$web_url" npm run test:e2e -- tests/e2e/selected-thread-integrations.spec.ts
) >/dev/null

jq -n --arg web_url "$web_url" \
  '{web_url:$web_url,private_runner:true,workflow_browser_e2e:"passed",selected_thread_e2e:"passed"}'
