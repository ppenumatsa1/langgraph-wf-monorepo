#!/usr/bin/env python3
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import uvicorn

SCRIPT_PATH = Path(__file__).resolve()
if (SCRIPT_PATH.parents[1] / "app").is_dir():
    BACKEND_ROOT = SCRIPT_PATH.parents[1]
elif len(SCRIPT_PATH.parents) > 3 and (SCRIPT_PATH.parents[3] / "backend").is_dir():
    BACKEND_ROOT = SCRIPT_PATH.parents[3] / "backend"
else:  # pragma: no cover - configuration error surfaced at runtime
    raise RuntimeError("Unable to locate the backend source root for the LangGraph launcher.")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DEFAULT_BACKEND_CANDIDATES = (
    ("app.langgraph.api", "app", BACKEND_ROOT / "app/langgraph/api.py"),
    ("app.langgraph.main", "app", BACKEND_ROOT / "app/langgraph/main.py"),
    ("app.langgraph.server", "app", BACKEND_ROOT / "app/langgraph/server.py"),
    ("app.main", "app", BACKEND_ROOT / "app/main.py"),
)


def resolve_backend_spec() -> tuple[str, str]:
    override = os.getenv("LANGGRAPH_BACKEND_APP_MODULE", "").strip()
    candidates = []
    if override:
        module_name, _, attr_name = override.partition(":")
        candidates.append((module_name, attr_name or "app", None))
    candidates.extend(DEFAULT_BACKEND_CANDIDATES)

    attempts: list[str] = []
    for module_name, attr_name, source_hint in candidates:
        if source_hint is not None and not source_hint.is_file():
            attempts.append(f"{module_name}:{attr_name} (missing {source_hint.relative_to(BACKEND_ROOT)})")
            continue
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            attempts.append(f"{module_name}:{attr_name} ({exc})")
            continue
        except Exception as exc:  # pragma: no cover - surfaced in runtime validation
            raise RuntimeError(f"Failed to import {module_name}:{attr_name}") from exc

        if getattr(module, attr_name, None) is None:
            attempts.append(f"{module_name}:{attr_name} (attribute not found)")
            continue
        print(f"Resolved backend startup to {module_name}:{attr_name}", file=sys.stderr, flush=True)
        return module_name, attr_name

    attempted = "; ".join(attempts) if attempts else "no backend candidates configured"
    raise RuntimeError(f"Unable to resolve a backend startup module. Tried: {attempted}")


def main() -> None:
    module_name, attr_name = resolve_backend_spec()
    uvicorn.run(
        f"{module_name}:{attr_name}",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("UVICORN_RELOAD", "").lower() == "true",
    )


if __name__ == "__main__":
    main()
