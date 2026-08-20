#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

source_dir="$PRIVATE_ROOT_DIR/backend"
launcher="$PRIVATE_AZD_DIR/runtime/launch_hosted_agent.py"
target_dir="${PRIVATE_HOSTED_PACKAGE_DIR:-$PRIVATE_ROOT_DIR/.artifacts/private-packages/$(private_release_id)/agent}"
package_root="$PRIVATE_ROOT_DIR/.artifacts/private-packages/"

private_require_file "$source_dir/Dockerfile.hosted"
private_require_file "$launcher"
[[ -f "$source_dir/foundry/main.py" ]] ||
  private_die "private hosted source requires backend/foundry/main.py"
private_validate_absolute_path PRIVATE_HOSTED_PACKAGE_DIR "$target_dir"
[[ "$target_dir" == "$package_root"* ]] ||
  private_die "private hosted package directory must stay beneath .artifacts/private-packages"

rm -rf -- "$target_dir"
mkdir -p "$target_dir/.deployment"
tar \
  --exclude='.env*' \
  --exclude='.venv' \
  --exclude='.foundry' \
  --exclude='.tmp' \
  --exclude='.git' \
  --exclude='tests' \
  --exclude='.pytest_cache' \
  --exclude='__pycache__' \
  --exclude='*/__pycache__' \
  --exclude='.foundry/results' \
  -C "$source_dir" -cf - . |
  tar -C "$target_dir" -xf -
cp "$source_dir/Dockerfile.hosted" "$target_dir/Dockerfile"
cp "$source_dir/.dockerignore" "$target_dir/.dockerignore"
cp "$launcher" "$target_dir/.deployment/launch_hosted_agent.py"
python3 - "$target_dir/Dockerfile" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
lines = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("CMD ")]
lines.append('CMD ["python", ".deployment/launch_hosted_agent.py"]')
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

if find "$target_dir" -type d -name '__pycache__' -print -quit | grep -q .; then
  private_die "hosted source sync retained Python cache files"
fi
if find "$target_dir" \( -name '.env' -o -name '.env.*' -o -path '*/.foundry/*' \) -print -quit | grep -q .; then
  private_die "hosted source sync retained a secret-bearing runtime artifact"
fi
