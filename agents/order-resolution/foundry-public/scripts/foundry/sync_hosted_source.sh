#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE_DIR="${ROOT_DIR}/backend"
TARGET_DIR="${ROOT_DIR}/infra/foundry-hosted/agent"
HOSTED_LAUNCHER="${ROOT_DIR}/infra/foundry-hosted/runtime/launch_hosted_agent.py"

if [[ ! -f "${SOURCE_DIR}/Dockerfile.hosted" || ! -f "${HOSTED_LAUNCHER}" ]]; then
  echo "backend/Dockerfile.hosted and infra/foundry-hosted/runtime/launch_hosted_agent.py are required."
  exit 1
fi

has_hosted_entrypoint=0
for candidate in \
  "${SOURCE_DIR}/foundry/main.py" \
  "${SOURCE_DIR}/app/langgraph/foundry_public.py" \
  "${SOURCE_DIR}/app/langgraph/foundry.py" \
  "${SOURCE_DIR}/app/langgraph/hosted.py"; do
  if [[ -f "$candidate" ]]; then
    has_hosted_entrypoint=1
    break
  fi
done
if [[ "$has_hosted_entrypoint" -ne 1 ]]; then
  echo "Hosted source sync requires backend/foundry/main.py or a supported backend/app/langgraph hosted entrypoint." >&2
  exit 1
fi

rm -rf "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"
tar --exclude='.env' --exclude='.venv' --exclude='tests' --exclude='.pytest_cache' --exclude='__pycache__' --exclude='*/__pycache__' \
  --exclude='.foundry/results' --exclude='tmp-foundry-sample' \
  -C "${SOURCE_DIR}" -cf - . | tar -C "${TARGET_DIR}" -xf -
cp "${SOURCE_DIR}/Dockerfile.hosted" "${TARGET_DIR}/Dockerfile"
cp "${SOURCE_DIR}/.dockerignore" "${TARGET_DIR}/.dockerignore"
mkdir -p "${TARGET_DIR}/.deployment"
cp "${HOSTED_LAUNCHER}" "${TARGET_DIR}/.deployment/launch_hosted_agent.py"
python3 - "${TARGET_DIR}/Dockerfile" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
filtered = [line for line in lines if not line.lstrip().startswith("CMD ")]
filtered.append('CMD ["python", ".deployment/launch_hosted_agent.py"]')
path.write_text("\n".join(filtered) + "\n", encoding="utf-8")
PY

if find "${TARGET_DIR}" -type d -name '__pycache__' -print -quit | grep -q .; then
  echo "Hosted source sync retained a nested __pycache__ directory." >&2
  exit 1
fi
