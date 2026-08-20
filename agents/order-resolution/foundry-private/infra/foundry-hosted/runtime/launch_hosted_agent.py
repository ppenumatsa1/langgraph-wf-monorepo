#!/usr/bin/env python3
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

DEFAULT_HOSTED_CANDIDATES = (
    (
        "app.langgraph.foundry_public",
        ("main", "app", "create_app", "_initialize_app"),
        PACKAGE_ROOT / "app/langgraph/foundry_public.py",
    ),
    (
        "app.langgraph.foundry",
        ("main", "app", "create_app", "_initialize_app"),
        PACKAGE_ROOT / "app/langgraph/foundry.py",
    ),
    (
        "app.langgraph.hosted",
        ("main", "app", "create_app", "_initialize_app"),
        PACKAGE_ROOT / "app/langgraph/hosted.py",
    ),
    ("foundry.main", ("main", "app", "_initialize_app"), PACKAGE_ROOT / "foundry/main.py"),
)


def run_target(target: object, module_name: str, attr_name: str) -> None:
    if attr_name in {"create_app", "_initialize_app"} and callable(target):
        target = target()
    elif attr_name == "main" and callable(target):
        target()
        return

    runner = getattr(target, "run", None)
    if callable(runner):
        runner()
        return
    if callable(target):
        target()
        return
    raise RuntimeError(f"{module_name}:{attr_name} is not runnable")


def resolve_hosted_entrypoint() -> tuple[object, str, str]:
    override = os.getenv("LANGGRAPH_HOSTED_ENTRYPOINT", "").strip()
    candidates = []
    if override:
        module_name, _, attr_name = override.partition(":")
        candidates.append((module_name, (attr_name or "main",), None))
    candidates.extend(DEFAULT_HOSTED_CANDIDATES)

    attempts: list[str] = []
    for module_name, attr_names, source_hint in candidates:
        if source_hint is not None and not source_hint.is_file():
            attempts.append(f"{module_name} (missing {source_hint.relative_to(PACKAGE_ROOT)})")
            continue
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            attempts.append(f"{module_name} ({exc})")
            continue
        except Exception as exc:  # pragma: no cover - surfaced in runtime validation
            raise RuntimeError(f"Failed to import {module_name}") from exc

        for attr_name in attr_names:
            if not hasattr(module, attr_name):
                continue
            target = getattr(module, attr_name)
            if target is not None or attr_name in {"app", "_initialize_app"}:
                return target, module_name, attr_name
        attempts.append(f"{module_name} (no supported entrypoint attribute)")

    attempted = "; ".join(attempts) if attempts else "no hosted candidates configured"
    raise RuntimeError(f"Unable to resolve a hosted entrypoint. Tried: {attempted}")


def main() -> None:
    target, module_name, attr_name = resolve_hosted_entrypoint()
    print(
        f"Resolved hosted startup to {module_name}:{attr_name}",
        file=sys.stderr,
        flush=True,
    )
    run_target(target, module_name, attr_name)


if __name__ == "__main__":
    main()
