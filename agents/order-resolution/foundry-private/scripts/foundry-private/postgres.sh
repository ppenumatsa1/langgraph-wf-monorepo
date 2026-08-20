#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

[[ $# -eq 1 ]] || {
  printf 'Usage: %s <schema|credentials|readiness>\n' "$0" >&2
  exit 2
}

case "$1" in
  schema)
    stage=postgres_schema
    artifact=private-postgres-schema.json
    ;;
  credentials)
    stage=postgres_credentials
    artifact=private-postgres-credentials.json
    ;;
  readiness)
    stage=postgres_readiness
    artifact=private-postgres-readiness.json
    ;;
  *)
    private_die "unsupported private PostgreSQL operation: $1"
    ;;
esac

if [[ -n "${FOUNDRY_PRIVATE_RELEASE_ID:-}" ]]; then
  "$SCRIPT_DIR/runner_exec.sh" "$stage" "evidence/$artifact"
else
  "$SCRIPT_DIR/runner_manual.sh" "$stage"
fi
