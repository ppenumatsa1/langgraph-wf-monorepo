from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.foundry.release_evidence import (  # noqa: E402
    assert_secret_free,
    atomic_write_json,
    release_directory,
    safe_artifact_path,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Atomically persist secret-free private release evidence")
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--relative-path", required=True)
    args = parser.parse_args()

    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise SystemExit("Evidence payload must be a JSON object.")
    assert_secret_free(payload)
    release_dir = release_directory(ROOT, args.release_id)
    target = safe_artifact_path(release_dir, args.relative_path, must_exist=False)
    atomic_write_json(target, payload)


if __name__ == "__main__":
    main()
