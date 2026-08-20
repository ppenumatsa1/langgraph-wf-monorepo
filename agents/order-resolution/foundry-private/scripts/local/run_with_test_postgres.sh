#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ "$#" -eq 0 ]]; then
  echo "Usage: run_with_test_postgres.sh <command> [args...]" >&2
  exit 2
fi

python_bin="$ROOT_DIR/backend/.venv/bin/python"
[[ -x "$python_bin" ]] || python_bin=python3

can_connect() {
  "$python_bin" - "$DATABASE_URL" <<'PY'
import sys
import psycopg

try:
    with psycopg.connect(sys.argv[1], connect_timeout=2):
        pass
except Exception:
    raise SystemExit(1)
PY
}

if [[ -n "${DATABASE_URL:-}" ]]; then
  can_connect || {
    echo "Configured DATABASE_URL is unreachable." >&2
    exit 1
  }
  exec "$@"
fi

for command in docker python3; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "$command is required to start isolated test PostgreSQL." >&2
    exit 1
  }
done

port="$(python3 scripts/local/find_free_port.py)"
project="langgraph-test-postgres-${port}"
compose_env="backend/.env.example"
[[ -f backend/.env ]] && compose_env="backend/.env"
export DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:${port}/langgraph_workflow?sslmode=disable"

cleanup() {
  COMPOSE_PROJECT_NAME="$project" POSTGRES_HOST_PORT="$port" \
    docker compose --env-file "$compose_env" down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

COMPOSE_PROJECT_NAME="$project" POSTGRES_HOST_PORT="$port" \
  docker compose --env-file "$compose_env" up -d postgres >/dev/null

for _ in {1..60}; do
  if can_connect; then
    PYTHONPATH="$ROOT_DIR/backend" \
      DATABASE_URL="$DATABASE_URL" \
      LANGGRAPH_STRICT_MSGPACK=true \
      "$python_bin" -m app.sql.bootstrap >/dev/null
    "$@"
    exit $?
  fi
  sleep 1
done

echo "Isolated test PostgreSQL did not become ready in time." >&2
exit 1
