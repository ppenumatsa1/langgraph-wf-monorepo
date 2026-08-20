from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.foundry.release_evidence import assert_secret_free

MARKER = re.compile(r"^FOUNDRY_PRIVATE_RUNNER_EVIDENCE_B64=([A-Za-z0-9+/=]+)$", re.MULTILINE)


def main() -> None:
    parser = argparse.ArgumentParser(description="Accept one sanitized manual runner result")
    parser.add_argument("--release-id", required=True)
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
        raise SystemExit("Azure Run Command did not return exactly one sanitized result.")
    try:
        payload = json.loads(base64.b64decode(matches[0], validate=True))
    except (ValueError, json.JSONDecodeError) as error:
        raise SystemExit("Azure Run Command returned malformed evidence.") from error
    if not isinstance(payload, dict) or payload.get("status") != "passed":
        raise SystemExit("Private runner stage did not report success.")
    if payload.get("release_id") != args.release_id or payload.get("stage") != args.stage:
        raise SystemExit("Private runner evidence does not match the requested manual stage.")
    assert_secret_free(payload)
    print(json.dumps({"stage": args.stage, "status": "passed"}))


if __name__ == "__main__":
    main()
