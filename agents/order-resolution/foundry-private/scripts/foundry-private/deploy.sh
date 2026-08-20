#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

[[ $# -eq 1 ]] || {
  printf 'Usage: %s <backend|frontend|hosted>\n' "$0" >&2
  exit 2
}
case "$1" in
  backend)
    "$SCRIPT_DIR/runner_exec.sh" deploy_backend evidence/private-backend-deployment.json
    ;;
  frontend)
    "$SCRIPT_DIR/runner_exec.sh" deploy_frontend evidence/private-frontend-deployment.json
    ;;
  hosted)
    "$SCRIPT_DIR/runner_exec.sh" deploy_hosted evidence/private-hosted-deployment.json
    ;;
  *)
    printf 'Unsupported private deployment component: %s\n' "$1" >&2
    exit 1
    ;;
esac
