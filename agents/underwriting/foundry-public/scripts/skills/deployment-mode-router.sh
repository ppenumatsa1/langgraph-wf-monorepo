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
  echo "reason=no_changed_files"
  exit 0
fi

if grep -Eq '^(Makefile|infra/|scripts/|docker-compose\.yml|backend/Dockerfile(\.hosted)?|frontend/Dockerfile|pyproject\.toml|requirements\.txt|\.env\.example)' <<<"$changed_files"; then
  echo "deploy_mode=app_only"
  echo "validation_mode=full"
  echo "reason=infra_or_runtime_surface_changed_app_only"
  exit 0
fi

if grep -Eq '^(backend/|frontend/)' <<<"$changed_files"; then
  echo "deploy_mode=app_only"
  echo "validation_mode=full"
  echo "reason=application_surface_changed"
  exit 0
fi

echo "deploy_mode=app_only"
echo "validation_mode=quick"
echo "reason=non_runtime_change"
