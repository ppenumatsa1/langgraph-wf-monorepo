from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXPECTED = {
    "CONTRACT_VERSION": "2",
    "DEPLOYMENT_LANE": "foundry-private",
    "AZURE_SUBSCRIPTION_ID": "7df95e88-701c-4693-af77-3159f83b558d",
    "AZURE_RESOURCE_GROUP": "rg-langgraph-ora-foundry-private",
    "AZURE_LOCATION": "eastus2",
}
RUNTIME_ENVIRONMENT = "order-resolution-foundry-private"
ALLOWED_ENVIRONMENTS = {
    RUNTIME_ENVIRONMENT,
    "order-resolution-private-bootstrap",
    "order-resolution-private-package-validation",
}
ALLOWED_KEYS = {
    *EXPECTED,
    "AZURE_ENV_NAME",
    "NAME_PREFIX",
}
SAFE_VALUE = re.compile(r"^[A-Za-z0-9._/:-]+$")


def fail(message: str) -> None:
    raise ValueError(f"private deployment profile error: {message}")


def parse_profile(path: Path, *, require_runtime: bool = False) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        fail("profile must be a readable regular file")

    values: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw or raw.startswith("#"):
            continue
        if raw.count("=") != 1:
            fail(f"line {line_number} must use KEY=VALUE syntax")
        key, value = raw.split("=", 1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or not value:
            fail(f"line {line_number} is not an approved declaration")
        if key not in ALLOWED_KEYS:
            fail(f"line {line_number} has an unsupported key: {key}")
        if key in values:
            fail(f"line {line_number} declares {key} more than once")
        if not SAFE_VALUE.fullmatch(value):
            fail(f"line {line_number} has an unsafe value")
        values[key] = value

    missing = sorted(set(ALLOWED_KEYS) - values.keys())
    if missing:
        fail(f"required key is missing: {', '.join(missing)}")
    for key, expected in EXPECTED.items():
        if values.get(key) != expected:
            fail(f"{key} must be {expected}")
    environment = values["AZURE_ENV_NAME"]
    if environment not in ALLOWED_ENVIRONMENTS:
        fail("AZURE_ENV_NAME is not an approved foundry-private environment")
    if require_runtime and environment != RUNTIME_ENVIRONMENT:
        fail(f"AZURE_ENV_NAME must be {RUNTIME_ENVIRONMENT} for private release operations")
    if not re.fullmatch(r"[a-z][a-z0-9]{2,14}", values["NAME_PREFIX"]):
        fail("NAME_PREFIX must be 3-15 lowercase alphanumeric characters")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a secret-free foundry-private deployment profile")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--runtime", action="store_true")
    args = parser.parse_args()
    try:
        values = parse_profile(args.profile, require_runtime=args.runtime)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
    if args.json:
        print(json.dumps(values, sort_keys=True))
    else:
        print(f"Validated private deployment profile: {args.profile}")


if __name__ == "__main__":
    main()
