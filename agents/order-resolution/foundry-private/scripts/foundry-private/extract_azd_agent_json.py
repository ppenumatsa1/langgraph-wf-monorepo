from __future__ import annotations

import json
import re
import sys

AGENT_PREFIX = re.compile(r"^\[[A-Za-z0-9_-]+\]\s+")


def main() -> None:
    for line in sys.stdin:
        candidate = AGENT_PREFIX.sub("", line.strip(), count=1)
        if not candidate.startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            print(json.dumps(payload, separators=(",", ":")))
            return
    raise SystemExit("AZD agent invocation did not contain a JSON object.")


if __name__ == "__main__":
    main()
