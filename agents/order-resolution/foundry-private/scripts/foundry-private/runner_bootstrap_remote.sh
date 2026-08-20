#!/usr/bin/env bash
set -euo pipefail
set +x

export HOME=/root

private_azd() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd "$@"
}

required=(EXPECTED_COMMIT REPOSITORY_URL WORKDIR AZD_ENV_NAME AZURE_SUBSCRIPTION_ID AZURE_LOCATION GITHUB_TOKEN AZD_ENV_B64)
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || {
    printf 'runner bootstrap is missing %s\n' "$name" >&2
    exit 1
  }
done

[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || {
  echo "runner bootstrap requires a full immutable commit" >&2
  exit 1
}
[[ "$REPOSITORY_URL" =~ ^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$ ]] || {
  echo "runner bootstrap requires an approved HTTPS GitHub repository URL" >&2
  exit 1
}
expected_workdir="/opt/order-resolution/source/agents/order-resolution/foundry-private"
[[ "$WORKDIR" == "$expected_workdir" ]] || {
  echo "runner bootstrap workdir is outside the approved source root" >&2
  exit 1
}
[[ "$AZD_ENV_NAME" == "order-resolution-foundry-private" ]] || {
  echo "runner bootstrap received an unexpected AZD environment" >&2
  exit 1
}

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
  ca-certificates curl docker.io git gnupg jq postgresql-client \
  python3 python3-pip python3-venv >/dev/null

node_major="$(node --version 2>/dev/null | sed -n 's/^v\([0-9][0-9]*\).*/\1/p' || true)"
if [[ -z "$node_major" || "$node_major" -lt 22 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null
  apt-get install -y --no-install-recommends nodejs >/dev/null
fi
if ! command -v az >/dev/null 2>&1; then
  curl -fsSL https://aka.ms/InstallAzureCLIDeb | bash >/dev/null
fi
if ! command -v azd >/dev/null 2>&1; then
  curl -fsSL https://aka.ms/install-azd.sh | bash >/dev/null
fi
systemctl enable --now docker >/dev/null

source_root="/opt/order-resolution/source"
staging_root="/opt/order-resolution/source.next"
askpass="/run/foundry-private-git-askpass"
incoming_env="/run/foundry-private-azd.env"
persistent_dir="/var/lib/order-resolution"
persistent_env="$persistent_dir/private-runner.env"
cleanup() {
  rm -f -- "$askpass" "$incoming_env"
  rm -rf -- "$staging_root"
  unset GITHUB_TOKEN AZD_ENV_B64
}
trap cleanup EXIT
cat >"$askpass" <<'EOF'
#!/usr/bin/env bash
case "${1:-}" in
  *Username*) printf '%s\n' x-access-token ;;
  *) printf '%s\n' "$GITHUB_TOKEN" ;;
esac
EOF
chmod 700 "$askpass"

rm -rf -- "$staging_root"
export GITHUB_TOKEN
export GIT_ASKPASS="$askpass"
export GIT_ASKPASS_REQUIRE=force
export GIT_TERMINAL_PROMPT=0
git clone --filter=blob:none --no-checkout "$REPOSITORY_URL" "$staging_root" >/dev/null
git -C "$staging_root" fetch --depth 1 origin "$EXPECTED_COMMIT" >/dev/null
git -C "$staging_root" checkout --detach "$EXPECTED_COMMIT" >/dev/null
[[ "$(git -C "$staging_root" rev-parse HEAD)" == "$EXPECTED_COMMIT" ]] || {
  echo "runner bootstrap did not resolve the requested commit" >&2
  exit 1
}
[[ -f "$staging_root/agents/order-resolution/foundry-private/infra/foundry-hosted/azure.yaml" ]] || {
  echo "runner bootstrap commit does not contain the private lane" >&2
  exit 1
}

mkdir -p "$persistent_dir"
chmod 700 "$persistent_dir"
existing_env="$source_root/agents/order-resolution/foundry-private/infra/foundry-hosted/.azure/$AZD_ENV_NAME/.env"
if [[ -f "$existing_env" ]]; then
  install -m 600 "$existing_env" "$persistent_env"
fi
rm -rf -- "$source_root"
mv "$staging_root" "$source_root"
rm -f -- "$askpass"
unset GITHUB_TOKEN GIT_ASKPASS GIT_ASKPASS_REQUIRE GIT_TERMINAL_PROMPT

python3 -m venv "$WORKDIR/backend/.venv"
"$WORKDIR/backend/.venv/bin/pip" install --disable-pip-version-check --no-cache-dir \
  -r "$WORKDIR/backend/requirements.txt" >/dev/null
npm --prefix "$WORKDIR/frontend" ci --no-audit --no-fund >/dev/null
npm --prefix "$WORKDIR/scripts/playwright" ci --no-audit --no-fund >/dev/null
(
  cd "$WORKDIR/frontend"
  npx playwright install --with-deps chromium >/dev/null
)
(
  cd "$WORKDIR/scripts/playwright"
  npx playwright install chromium >/dev/null
)

az login --identity --allow-no-subscriptions --output none
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
private_azd auth login --managed-identity --no-prompt >/dev/null

azd_dir="$WORKDIR/infra/foundry-hosted"
if [[ -d "$azd_dir/.azure/$AZD_ENV_NAME" ]]; then
  private_azd env select "$AZD_ENV_NAME" --cwd "$azd_dir" --no-prompt
else
  private_azd env new "$AZD_ENV_NAME" \
    --subscription "$AZURE_SUBSCRIPTION_ID" \
    --location "$AZURE_LOCATION" \
    --cwd "$azd_dir" \
    --no-prompt
fi
env_file="$azd_dir/.azure/$AZD_ENV_NAME/.env"
printf '%s' "$AZD_ENV_B64" | base64 --decode >"$incoming_env"
chmod 600 "$incoming_env"
if [[ -f "$persistent_env" ]]; then
  cat "$persistent_env" "$incoming_env" >"$env_file"
else
  cat "$incoming_env" >"$env_file"
fi
chmod 600 "$env_file"
install -m 600 "$env_file" "$persistent_env"
unset AZD_ENV_B64
private_azd env select "$AZD_ENV_NAME" --cwd "$azd_dir" --no-prompt

[[ "$(git -C "$WORKDIR" rev-parse HEAD)" == "$EXPECTED_COMMIT" ]]
git -C "$WORKDIR" diff --quiet
git -C "$WORKDIR" diff --cached --quiet
docker info >/dev/null
private_azd auth login --check-status --no-prompt >/dev/null

jq -cn \
  --arg commit "$EXPECTED_COMMIT" \
  --arg workdir "$WORKDIR" \
  --arg node "$(node --version)" \
  --arg python "$(python3 --version)" \
  '{status:"passed",source_commit:$commit,workdir:$workdir,node:$node,python:$python}'
