from __future__ import annotations

import argparse
import json
from pathlib import Path

LIVE_RELEASE_MARKER = ".live-release-validated"
DURABLE_ARCHIVE_MARKER = ".durable-archive-confirmed"


def migration_plan(project_root: Path) -> dict[str, object]:
    releases_root = project_root / ".artifacts" / "releases"
    sources = [
        project_root / "deployment-report",
        project_root / ".artifacts" / "release",
    ]
    candidates: list[dict[str, object]] = []
    for source in sources:
        if source.is_symlink():
            candidates.append(
                {"source": source.relative_to(project_root).as_posix(), "eligible": False, "reason": "symlink"}
            )
            continue
        if not source.exists():
            continue
        for path in sorted(source.rglob("*")):
            if path.is_file() and not path.is_symlink():
                candidates.append(
                    {
                        "source": path.relative_to(project_root).as_posix(),
                        "eligible": True,
                        "reason": "legacy_candidate",
                    }
                )
    markers = {
        "live_release": (releases_root / LIVE_RELEASE_MARKER).is_file(),
        "durable_archive": (releases_root / DURABLE_ARCHIVE_MARKER).is_file(),
    }
    return {
        "mode": "dry_run",
        "sources_unchanged": True,
        "candidates": candidates,
        "deletion_requirements": markers,
        "deletion_eligible": all(markers.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan legacy release evidence migration")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan = migration_plan(args.project_root.resolve())
    rendered = json.dumps(plan, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
