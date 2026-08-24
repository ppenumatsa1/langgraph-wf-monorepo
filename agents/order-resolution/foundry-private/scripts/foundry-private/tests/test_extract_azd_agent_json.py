from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "extract_azd_agent_json.py"


def extract(value: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=value,
        capture_output=True,
        check=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_extracts_prefixed_azd_131_response() -> None:
    payload = extract(
        "Agent: order-resolution-hosted\n"
        '[order-resolution-hosted] {"status":"completed","thread_id":"conv-1"}\n'
        "Server responded in 1.0s\n"
    )

    assert payload == {"status": "completed", "thread_id": "conv-1"}


def test_extracts_legacy_unprefixed_response() -> None:
    payload = extract('notice\n{"status":"waiting_approval","thread_id":"conv-2"}\n')

    assert payload == {"status": "waiting_approval", "thread_id": "conv-2"}
