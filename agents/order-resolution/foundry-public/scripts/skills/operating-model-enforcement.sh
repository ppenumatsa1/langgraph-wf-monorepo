#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

base_ref="${1:-HEAD}"
if git rev-parse --verify --quiet HEAD^{commit} >/dev/null; then
  changed_files="$(git diff --name-only --relative "$base_ref" -- .)"
else
  changed_files="$(git ls-files --cached --others --exclude-standard -- .)"
fi

if [[ -z "$changed_files" ]]; then
  echo "[PASS] operating-model: no changed files"
  exit 0
fi

require_changed() {
  local required_file="$1"
  local reason="$2"
  if ! grep -Fxq "$required_file" <<<"$changed_files"; then
    echo "[FAIL] operating-model: missing required update '$required_file' ($reason)"
    exit 1
  fi
}

if grep -Eq '^(backend/app/modules/order_resolution/hitl\.py|backend/app/modules/order_resolution/(durable_events|projections|service)\.py|backend/app/infrastructure/persistence/(checkpoint_store|idempotency_store|workflow_run_repository)\.py|backend/app/core/database\.py|backend/app/langgraph/.*(hitl|interrupt|resume|graph).*\.py)$' <<<"$changed_files"; then
  require_changed "docs/design/hitl-approval-conditions.md" "HITL decision logic changed"
  if ! grep -Eq '^(backend/tests/test_workflow\.py|backend/.foundry/datasets/order-resolution-hosted-cases\.jsonl)$' <<<"$changed_files"; then
    echo "[FAIL] operating-model: HITL changes require workflow tests or hosted eval dataset updates"
    exit 1
  fi
fi

if grep -Eq '^(\.github/workflows/foundry-.*\.yml|infra/foundry-hosted/|backend/foundry/main\.py|backend/agent\.yaml|scripts/foundry/|scripts/github/foundry_hosted_e2e\.sh)' <<<"$changed_files"; then
  require_changed "docs/design/issues-changes-fixes.md" "Hosted runtime/deploy surfaces changed"
fi

echo "[PASS] operating-model enforcement checks"
