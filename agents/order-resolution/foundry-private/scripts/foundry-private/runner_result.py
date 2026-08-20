from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.foundry.release_evidence import assert_secret_free, atomic_write_json, release_directory, safe_artifact_path  # noqa: E402

MARKER = re.compile(r"^FOUNDRY_PRIVATE_RUNNER_EVIDENCE_B64=([A-Za-z0-9+/=]+)$", re.MULTILINE)


def main() -> None:
    parser = argparse.ArgumentParser(description="Accept one sanitized Azure Run Command result")
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--relative-path", required=True)
    parser.add_argument("--stage", required=True)
    args = parser.parse_args()

    response = json.load(sys.stdin)
    if not isinstance(response, dict):
        raise SystemExit("Azure Run Command returned an invalid response.")
    messages = [
        str(item.get("message", ""))
        for item in response.get("value", [])
        if isinstance(item, dict)
    ]
    matches = MARKER.findall("\n".join(messages))
    if len(matches) != 1:
        raise SystemExit("Azure Run Command did not return exactly one sanitized evidence payload.")
    try:
        decoded = base64.b64decode(matches[0], validate=True)
        payload = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as error:
        raise SystemExit("Azure Run Command returned malformed evidence.") from error
    if not isinstance(payload, dict):
        raise SystemExit("Runner evidence must be a JSON object.")
    if payload.get("release_id") != args.release_id:
        raise SystemExit("Runner evidence belongs to another release.")
    if payload.get("stage") != args.stage or payload.get("status") != "passed":
        raise SystemExit("Runner stage did not report a successful matching result.")
    assert_secret_free(payload)
    release_dir = release_directory(ROOT, args.release_id)
    target = safe_artifact_path(release_dir, args.relative_path, must_exist=False)
    atomic_write_json(target, payload)
    print(json.dumps({"stage": args.stage, "status": "passed"}))


if __name__ == "__main__":
    main()
