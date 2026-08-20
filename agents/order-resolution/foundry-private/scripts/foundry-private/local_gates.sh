#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

private_require_command make
private_require_command python3
private_require_command git
private_require_file "$SCRIPT_DIR/profile_gate.py"

profile_path="${FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE:-}"
[[ -n "$profile_path" ]] ||
  private_die "FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE is required"
python3 "$SCRIPT_DIR/profile_gate.py" "$profile_path"

bash "$PRIVATE_ROOT_DIR/scripts/skills/operating-model-enforcement.sh"
python3 "$PRIVATE_ROOT_DIR/scripts/skills/validate-skills.py"
make -C "$PRIVATE_ROOT_DIR" test-scripts
make -C "$PRIVATE_ROOT_DIR" test-deployment-profile

if [[ "${FOUNDRY_PRIVATE_RUN_FULL_LOCAL_GATES:-0}" == "1" ]]; then
  make -C "$PRIVATE_ROOT_DIR" test
  make -C "$PRIVATE_ROOT_DIR" eval-backend
  make -C "$PRIVATE_ROOT_DIR" test-e2e
  make -C "$PRIVATE_ROOT_DIR" docker-test
  bash "$PRIVATE_ROOT_DIR/scripts/skills/design-review-skill.sh"
fi

if [[ -n "${FOUNDRY_PRIVATE_RELEASE_ID:-}" ]]; then
  private_release_id >/dev/null
  jq -n \
    --arg release_id "$FOUNDRY_PRIVATE_RELEASE_ID" \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{schema_version:1,evidence_type:"release_gates",status:"passed",release_id:$release_id,generated_at:$generated_at,stage:"local_gates"}' |
    python3 "$SCRIPT_DIR/write_artifact.py" \
      --release-id "$FOUNDRY_PRIVATE_RELEASE_ID" \
      --relative-path evidence/release-gates.json
fi

echo "Foundry-private skill, local, script, and profile gates passed."
