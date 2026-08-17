#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

base_ref="${1:-HEAD}"
if git rev-parse --verify --quiet HEAD^{commit} >/dev/null; then
  tracked_changes="$(git diff --name-only --relative "$base_ref" -- .)"
  untracked_changes="$(git ls-files --others --exclude-standard -- .)"
else
  tracked_changes="$(git ls-files --cached --others --exclude-standard -- .)"
  untracked_changes=""
fi
changed_files="$(printf '%s\n%s\n' "$tracked_changes" "$untracked_changes" | sed '/^$/d' | sort -u)"

if [[ -z "$changed_files" ]]; then
  echo "deploy_mode=app_only"
  echo "validation_mode=quick"
  echo "infrastructure_reconciliation=not_requested"
  echo "reason=no_changed_files"
  exit 0
fi

if grep -Eq '^infra/' <<<"$changed_files"; then
  echo "deploy_mode=app_only"
  echo "validation_mode=full"
  echo "infrastructure_reconciliation=required"
  echo "reason=infrastructure_change_requires_explicit_reconciliation"
  exit 0
fi

if grep -Eq '^(Makefile|scripts/|\.azure/|docker-compose\.yml|backend/Dockerfile(\.hosted)?|frontend/Dockerfile|frontend/nginx\.conf|pyproject\.toml|backend/requirements(\-dev)?\.txt|frontend/package(-lock)?\.json|\.env\.example|\.github/workflows/|backend/|frontend/)' <<<"$changed_files"; then
  echo "deploy_mode=app_only"
  echo "validation_mode=full"
  echo "infrastructure_reconciliation=not_requested"
  echo "reason=runtime_or_package_surface_changed"
  exit 0
fi

echo "deploy_mode=app_only"
echo "validation_mode=quick"
echo "infrastructure_reconciliation=not_requested"
echo "reason=non_runtime_change"
