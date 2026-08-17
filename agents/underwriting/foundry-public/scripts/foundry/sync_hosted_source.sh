#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_DIR="$ROOT_DIR/infra/foundry-hosted/agent"

if [[ ! -f "$ROOT_DIR/backend/Dockerfile.hosted" || ! -f "$ROOT_DIR/backend/foundry/main.py" ]]; then
  echo "backend/Dockerfile.hosted and backend/foundry/main.py are required." >&2
  exit 1
fi

rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"

cp "$ROOT_DIR/backend/pyproject.toml" "$TARGET_DIR/"
cp "$ROOT_DIR/backend/Dockerfile.hosted" "$TARGET_DIR/Dockerfile"
cp "$ROOT_DIR/.dockerignore" "$TARGET_DIR/.dockerignore"

tar \
  --exclude='backend/.env' \
  --exclude='backend/.venv' \
  --exclude='backend/tests' \
  --exclude='backend/.pytest_cache' \
  --exclude='backend/__pycache__' \
  --exclude='*/__pycache__' \
  --exclude='backend/.foundry/results' \
  --exclude='backend/.tmp' \
  -C "$ROOT_DIR" \
  -cf - backend | tar -C "$TARGET_DIR" -xf -
