from __future__ import annotations

import re
import sys

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
UNSAFE_CHANGE = re.compile(
    r'(?im)^\s*(?:[-~!?]\s*)?(?:delete|replace)\b'
    r'|\b(?:delete|replace)\s+(?:resource|change)\b'
    r'|"(?:changeType|change_type)"\s*:\s*"(?:delete|replace)"'
)


def main() -> None:
    captured: list[str] = []
    for line in sys.stdin:
        sys.stdout.write(line)
        captured.append(ANSI_ESCAPE.sub("", line))

    text = "".join(captured)
    if UNSAFE_CHANGE.search(text):
        raise SystemExit(
            "AUTOMATIC SAFETY CHECK FAILED: the Bicep what-if contains Delete or Replace changes."
        )


if __name__ == "__main__":
    main()
