from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY_SOURCES = (ROOT / "deployment-report", ROOT / ".artifacts" / "release")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(root: Path, destination_root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for source in (root / "deployment-report", root / ".artifacts" / "release"):
        if not source.exists():
            continue
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix()
            entries.append(
                {
                    "source": relative,
                    "destination": (destination_root / "_history" / "legacy" / relative).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run inventory for deferred Underwriting release-history migration."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--destination-root", type=Path, default=Path(".artifacts/releases"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--delete-source", action="store_true")
    parser.add_argument("--live-deployment-marker", type=Path)
    parser.add_argument("--durable-archive-marker", type=Path)
    args = parser.parse_args()

    if args.delete_source:
        if not args.execute:
            parser.error("--delete-source requires --execute")
        for name, marker in (
            ("--live-deployment-marker", args.live_deployment_marker),
            ("--durable-archive-marker", args.durable_archive_marker),
        ):
            if marker is None or not marker.is_file():
                parser.error(f"{name} must name an existing marker file")
    if args.execute:
        parser.error("Live migration is intentionally disabled until a later validated cutover.")

    root = args.root.resolve()
    payload = {
        "mode": "dry-run",
        "source_status": "legacy_pending_cutover",
        "destination_status": "prepared_not_live_validated",
        "files": inventory(root, args.destination_root),
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
