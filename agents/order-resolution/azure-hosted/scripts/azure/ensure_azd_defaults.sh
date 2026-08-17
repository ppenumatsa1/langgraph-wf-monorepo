#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
PROFILE="${AZURE_DEPLOYMENT_PROFILE:-$ROOT_DIR/deployment/profiles/azure-hosted.env}"
ENV_NAME="${AZURE_ENV_NAME:-order-resolution-azure-hosted}"

if ! AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd env get-value AZURE_SUBSCRIPTION_ID --cwd "$ROOT_DIR" --no-prompt >/dev/null 2>&1; then
  bash "$ROOT_DIR/deployment/apply-azd-profile.sh" "$PROFILE"
else
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env select "$ENV_NAME" --cwd "$ROOT_DIR" --no-prompt >/dev/null
fi
