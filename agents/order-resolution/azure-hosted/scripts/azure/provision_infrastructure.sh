#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

for command in azd python3; do
  require_command "$command"
done
assert_target

preview_file="$(mktemp)"
trap 'rm -f "$preview_file"' EXIT

AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd provision --cwd "$ROOT_DIR" --preview --no-prompt | tee "$preview_file"

python3 - "$preview_file" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
if re.search(r"(?im)^\s*[-~!?]?\s*(delete|replace)\b", text):
    raise SystemExit(
        "AUTOMATIC SAFETY CHECK FAILED: infrastructure preview contains "
        "Delete or Replace changes. Record an issue and stop."
    )
PY

AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd provision --cwd "$ROOT_DIR" --no-prompt "$@"
