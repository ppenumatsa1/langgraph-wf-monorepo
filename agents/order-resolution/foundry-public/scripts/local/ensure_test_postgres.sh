#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

database_url="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/langgraph_workflow?sslmode=disable}"
python_bin="${ROOT_DIR}/backend/.venv/bin/python"

if [[ ! -x "$python_bin" ]]; then
  python_bin="python3"
fi

can_connect() {
  "$python_bin" - "$database_url" <<'PY'
import sys
import psycopg

try:
    with psycopg.connect(sys.argv[1], connect_timeout=2):
        pass
except Exception:
    raise SystemExit(1)
PY
}

readarray -t parts < <(python3 - "$database_url" <<'PY'
import sys
from urllib.parse import urlparse

url = sys.argv[1]
parsed = urlparse(url)
host = parsed.hostname or "localhost"
port = parsed.port or 5432
user = parsed.username or "postgres"
dbname = parsed.path.lstrip("/") or "postgres"
print(host)
print(port)
print(user)
print(dbname)
PY
)

host="${parts[0]}"
port="${parts[1]}"
user="${parts[2]}"
dbname="${parts[3]}"

if can_connect; then
  exit 0
fi

if [[ "$host" != "localhost" && "$host" != "127.0.0.1" ]]; then
  echo "PostgreSQL is unreachable at ${host}:${port}. Fix DATABASE_URL or database availability before running local validation."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to auto-start local PostgreSQL for validation."
  echo "Set DATABASE_URL to a reachable PostgreSQL instance to bypass local Docker startup."
  exit 1
fi

echo "Starting local PostgreSQL via docker compose..."
if docker compose version >/dev/null 2>&1; then
  docker compose up -d postgres >/dev/null
else
  container_name="langgraph-local-postgres"
  echo "Docker Compose unavailable; using standalone container ${container_name}."
  if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon is unavailable."
    echo "Set DATABASE_URL to a reachable PostgreSQL instance to bypass local Docker startup."
    exit 1
  fi
  if docker ps -a --format '{{.Names}}' | grep -qx "$container_name"; then
    docker start "$container_name" >/dev/null
  else
    docker run -d \
      --name "$container_name" \
      -e POSTGRES_DB=langgraph_workflow \
      -e POSTGRES_USER=postgres \
      -e POSTGRES_PASSWORD=postgres \
      -p 5432:5432 \
      postgres:16 >/dev/null
  fi
fi

for _ in {1..30}; do
  if can_connect; then
    exit 0
  fi
  sleep 1
done

echo "Local PostgreSQL did not become ready in time."
exit 1
