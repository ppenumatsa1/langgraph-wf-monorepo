#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SECRET_PATTERNS = (
    re.compile(r"(?i)postgres(?:ql)?(?:\+psycopg)?://"),
    re.compile(r'(?i)"?(password|secret|token|credential|connection[_-]?string)"?\s*[:=]'),
    re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def release_dir(release_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,127}", release_id):
        raise ValueError("Invalid release ID")
    return root() / ".artifacts" / "releases" / release_id


@contextmanager
def release_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / ".release.lock"
    with lock_path.open("a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _write_json_unlocked(path: Path, payload: dict[str, object]) -> None:
    rendered = json.dumps(payload, indent=2)
    if any(pattern.search(rendered) for pattern in SECRET_PATTERNS):
        raise ValueError("Release evidence contains a secret-bearing value")
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".new",
            dir=path.parent,
            delete=False,
        ) as candidate:
            candidate_path = Path(candidate.name)
            candidate.write(rendered + "\n")
            candidate.flush()
            os.fsync(candidate.fileno())
        os.replace(candidate_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if candidate_path is not None and candidate_path.exists():
            candidate_path.unlink()


def write_json(path: Path, payload: dict[str, object]) -> None:
    with release_lock(path):
        _write_json_unlocked(path, payload)


def init(release_id: str, profile: str) -> None:
    directory = release_dir(release_id)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "evidence").mkdir()
    write_json(
        directory / "release.json",
        {
            "schema_version": 1,
            "release_id": release_id,
            "status": "running",
            "started_at": now(),
            "profile": Path(profile).name,
            "stages": {},
        },
    )


def timing(release_id: str, stage: str, action: str, status: str | None) -> None:
    path = release_dir(release_id) / "release.json"
    with release_lock(path):
        payload = json.loads(path.read_text(encoding="utf-8"))
        stages = payload.setdefault("stages", {})
        if action == "start":
            stages[stage] = {"status": "running", "started_at": now()}
        else:
            entry = stages.setdefault(stage, {})
            ended_at = now()
            started_at = datetime.fromisoformat(
                str(entry["started_at"]).replace("Z", "+00:00")
            )
            ended = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
            entry.update(
                status=status or "succeeded",
                ended_at=ended_at,
                duration_ms=round((ended - started_at).total_seconds() * 1000),
            )
        _write_json_unlocked(path, payload)


def aggregate(release_id: str) -> None:
    directory = release_dir(release_id)
    required = (
        "model-preflight.json",
        "images.json",
        "deployment.json",
        "verification.json",
        "smoke.json",
        "domain-e2e.json",
        "browser-e2e.json",
        "evaluation.json",
        "telemetry.json",
    )
    artifacts: list[dict[str, object]] = []
    for name in required:
        path = directory / "evidence" / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        acceptable = payload.get("status") in {"passed", "completed"}
        if name == "evaluation.json" and payload.get("report_only") is True:
            acceptable = True
        if not acceptable:
            raise ValueError(f"Release gate did not pass: {name}")
        artifacts.append(
            {
                "path": f"evidence/{name}",
                "status": payload["status"],
                "report_only": payload.get("report_only", False),
            }
        )
    release_path = directory / "release.json"
    with release_lock(release_path):
        release = json.loads(release_path.read_text(encoding="utf-8"))
        completed_at = now()
        started = datetime.fromisoformat(str(release["started_at"]).replace("Z", "+00:00"))
        completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        release.update(
            status="succeeded",
            completed_at=completed_at,
            duration_ms=round((completed - started).total_seconds() * 1000),
            artifacts=artifacts,
        )
        _write_json_unlocked(release_path, release)


def finalize_failed(release_id: str, failed_stage: str) -> None:
    path = release_dir(release_id) / "release.json"
    with release_lock(path):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.update(
            status="failed",
            completed_at=now(),
            failed_stage=failed_stage,
        )
        _write_json_unlocked(path, payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    init_parser = sub.add_parser("init")
    init_parser.add_argument("--release-id", required=True)
    init_parser.add_argument("--profile", required=True)
    timing_parser = sub.add_parser("timing")
    timing_parser.add_argument("--release-id", required=True)
    timing_parser.add_argument("--stage", required=True)
    timing_parser.add_argument("--action", choices=("start", "end"), required=True)
    timing_parser.add_argument("--status")
    aggregate_parser = sub.add_parser("aggregate")
    aggregate_parser.add_argument("--release-id", required=True)
    finalize_parser = sub.add_parser("finalize-failed")
    finalize_parser.add_argument("--release-id", required=True)
    finalize_parser.add_argument("--failed-stage", required=True)
    args = parser.parse_args()
    if args.command == "init":
        init(args.release_id, args.profile)
    elif args.command == "timing":
        timing(args.release_id, args.stage, args.action, args.status)
    elif args.command == "aggregate":
        aggregate(args.release_id)
    else:
        finalize_failed(args.release_id, args.failed_stage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
