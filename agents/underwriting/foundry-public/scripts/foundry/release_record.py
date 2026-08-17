from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
RELEASES_ROOT = ROOT / ".artifacts" / "releases"
LANE = "underwriting-foundry-public"
TIMING_EXTENSION = "release_timing"
MAX_DEPLOYMENT_MS = 15 * 60 * 1000
MAX_APP_TO_TELEMETRY_MS = 30 * 60 * 1000
TIMING_STAGES = (
    "package_build",
    "image_build",
    "hosted_activation",
    "aca_deployment",
    "smoke",
    "deployed_e2e",
    "evaluation",
    "telemetry",
    "deployment_verification",
    "final_evidence",
)
TIMING_PREREQUISITES = {
    "image_build": ("package_build",),
    "hosted_activation": ("image_build",),
    "aca_deployment": ("hosted_activation",),
    "smoke": ("aca_deployment",),
    "deployed_e2e": ("smoke",),
    "evaluation": ("smoke",),
    "telemetry": ("deployed_e2e",),
    "deployment_verification": ("evaluation", "telemetry"),
    "final_evidence": ("deployment_verification",),
}
RELEASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
SECRET_KEY_PATTERN = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|connection[_-]?string|database[_-]?url)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"postgres(?:ql)?(?:\+[^:]+)?://", re.IGNORECASE),
    re.compile(r"(?:instrumentationkey|sharedaccesskey|accountkey)\s*=", re.IGNORECASE),
    re.compile(r"authorization\s*:\s*bearer\s+", re.IGNORECASE),
    re.compile(
        r"(?:password|passwd|secret|token|api[_-]?key|connection[_-]?string|"
        r"database[_-]?url)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def release_lock(release_dir: Path):
    lock_path = release_dir / ".release-record.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def duration_ms(started_at: str, ended_at: str) -> int:
    milliseconds = (parse_timestamp(ended_at) - parse_timestamp(started_at)) // timedelta(
        milliseconds=1
    )
    if milliseconds < 0:
        raise ValueError("Timing end must not precede timing start.")
    return milliseconds


def timing_extension(record: dict[str, Any]) -> dict[str, Any]:
    extensions = record.setdefault("extensions", {})
    timing = extensions.setdefault(
        TIMING_EXTENSION,
        {
            "version": 1,
            "app_only_started_at": None,
            "telemetry_succeeded_at": None,
            "app_only_duration_ms": None,
            "app_only": {
                "status": "pending",
                "started_at": None,
                "ended_at": None,
                "duration_ms": None,
            },
            "stages": {},
        },
    )
    return timing


def start_release_timing(
    release_id: str,
    stage: str,
    *,
    start_app_only: bool = False,
    at: str | None = None,
    releases_root: Path = RELEASES_ROOT,
) -> None:
    if stage not in TIMING_STAGES:
        raise ValueError(f"Unknown release timing stage: {stage}")
    release_dir = release_directory(release_id, releases_root)
    with release_lock(release_dir):
        record = load_record(release_dir)
        if record["status"] != "running":
            raise ValueError("Release timing cannot start after finalization.")
        now = at or utc_now()
        parse_timestamp(now)
        timing = timing_extension(record)
        if stage in timing["stages"]:
            raise ValueError(f"Release timing stage already started: {stage}")
        if start_app_only:
            if stage != "package_build":
                raise ValueError("app_only timing must start with package_build.")
            if timing["app_only_started_at"] is not None:
                raise ValueError("app_only timing is already started.")
            timing["app_only_started_at"] = now
            timing["app_only"] = {
                "status": "running",
                "started_at": now,
                "ended_at": None,
                "duration_ms": None,
            }
        if timing["app_only_started_at"] is None:
            raise ValueError("app_only timing must start before release stages.")
        if parse_timestamp(now) < parse_timestamp(timing["app_only_started_at"]):
            raise ValueError("Release timing stage predates app_only start.")
        for prerequisite in TIMING_PREREQUISITES.get(stage, ()):
            result = timing["stages"].get(prerequisite)
            if not result or result.get("status") != "succeeded":
                raise ValueError(f"Timing prerequisite is incomplete: {prerequisite}")
        timing["stages"][stage] = {
            "status": "running",
            "started_at": now,
            "ended_at": None,
            "duration_ms": None,
        }
        record["updated_at"] = now
        atomic_json_write(release_dir / "release.json", record)


def finish_release_timing(
    release_id: str,
    stage: str,
    status: str,
    *,
    at: str | None = None,
    releases_root: Path = RELEASES_ROOT,
) -> None:
    if status not in {"succeeded", "failed"}:
        raise ValueError("Timing status must be succeeded or failed.")
    release_dir = release_directory(release_id, releases_root)
    with release_lock(release_dir):
        record = load_record(release_dir)
        if record["status"] != "running":
            raise ValueError("Release timing cannot finish after finalization.")
        now = at or utc_now()
        parse_timestamp(now)
        timing = timing_extension(record)
        result = timing["stages"].get(stage)
        if not result or result.get("status") != "running":
            raise ValueError(f"Release timing stage is not running: {stage}")
        result.update(
            {
                "status": status,
                "ended_at": now,
                "duration_ms": duration_ms(result["started_at"], now),
            }
        )
        if status == "failed" and timing["app_only"]["status"] == "running":
            timing["app_only"].update(
                {
                    "status": "failed",
                    "ended_at": now,
                    "duration_ms": duration_ms(timing["app_only_started_at"], now),
                }
            )
        if stage == "telemetry" and status == "succeeded":
            timing["telemetry_succeeded_at"] = now
            timing["app_only_duration_ms"] = duration_ms(timing["app_only_started_at"], now)
            timing["app_only"].update(
                {
                    "status": "succeeded",
                    "ended_at": now,
                    "duration_ms": timing["app_only_duration_ms"],
                }
            )
        record["updated_at"] = now
        atomic_json_write(release_dir / "release.json", record)


def resume_record(
    release_id: str,
    from_stage: str,
    *,
    at: str | None = None,
    releases_root: Path = RELEASES_ROOT,
) -> None:
    release_dir = release_directory(release_id, releases_root)
    with release_lock(release_dir):
        record = load_record(release_dir)
        if record["status"] != "failed":
            raise ValueError("Only a failed release may be resumed.")
        now = at or utc_now()
        parse_timestamp(now)
        timing = timing_extension(record)
        from_index = TIMING_STAGES.index(from_stage)
        for stage in TIMING_STAGES[from_index:]:
            timing["stages"].pop(stage, None)
        timing["telemetry_succeeded_at"] = None
        timing["app_only_duration_ms"] = None
        timing["app_only"].update(status="running", ended_at=None, duration_ms=None)
        record.update(
            status="running",
            updated_at=now,
            completed_at=None,
            failed_stage=None,
            error=None,
            artifacts=[],
        )
        atomic_json_write(release_dir / "release.json", record)


def validate_succeeded_timing(record: dict[str, Any]) -> None:
    timing = record.get("extensions", {}).get(TIMING_EXTENSION)
    if not isinstance(timing, dict):
        raise ValueError("Succeeded release is missing release timing.")
    app_started = timing.get("app_only_started_at")
    telemetry_ended = timing.get("telemetry_succeeded_at")
    if not isinstance(app_started, str) or not isinstance(telemetry_ended, str):
        raise ValueError("Succeeded release is missing app-only timing boundaries.")
    if parse_timestamp(app_started) < parse_timestamp(record["started_at"]):
        raise ValueError("app_only_started_at predates the release record.")
    stages = timing.get("stages", {})
    missing = [
        stage for stage in TIMING_STAGES if stages.get(stage, {}).get("status") != "succeeded"
    ]
    if missing:
        raise ValueError(f"Release timing stages are incomplete: {', '.join(missing)}")
    for stage in TIMING_STAGES:
        result = stages[stage]
        expected = duration_ms(result["started_at"], result["ended_at"])
        if result.get("duration_ms") != expected:
            raise ValueError(f"Release timing duration is invalid: {stage}")
        if parse_timestamp(result["started_at"]) < parse_timestamp(app_started):
            raise ValueError(f"Release timing stage predates app-only start: {stage}")
    if stages["package_build"]["started_at"] != app_started:
        raise ValueError("app_only_started_at must equal package/build start.")
    for stage, prerequisites in TIMING_PREREQUISITES.items():
        for prerequisite in prerequisites:
            if parse_timestamp(stages[stage]["started_at"]) < parse_timestamp(
                stages[prerequisite]["ended_at"]
            ):
                raise ValueError(f"Release timing order is invalid: {prerequisite} -> {stage}")
    if stages["telemetry"]["ended_at"] != telemetry_ended:
        raise ValueError("telemetry_succeeded_at must equal telemetry stage end.")
    expected_total = duration_ms(app_started, telemetry_ended)
    deployment_total = duration_ms(app_started, stages["aca_deployment"]["ended_at"])
    if deployment_total > MAX_DEPLOYMENT_MS:
        raise ValueError("Package-to-deployment exceeded the 15-minute deployment budget.")
    if expected_total > MAX_APP_TO_TELEMETRY_MS:
        raise ValueError("App-only to telemetry exceeded the 30-minute lifecycle budget.")
    if timing.get("app_only_duration_ms") != expected_total:
        raise ValueError("App-only total duration is invalid.")
    app_only = timing.get("app_only", {})
    if app_only != {
        "status": "succeeded",
        "started_at": app_started,
        "ended_at": telemetry_ended,
        "duration_ms": expected_total,
    }:
        raise ValueError("App-only total interval is invalid.")


def validate_release_id(release_id: str) -> None:
    if not RELEASE_ID_PATTERN.fullmatch(release_id):
        raise ValueError(f"Invalid release ID: {release_id!r}")


def release_directory(release_id: str, releases_root: Path = RELEASES_ROOT) -> Path:
    validate_release_id(release_id)
    return releases_root.resolve() / release_id


def safe_artifact_path(release_dir: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Unsafe artifact path: {relative_path}")
    if not candidate.parts or candidate.parts[0] not in {"evidence", "logs"}:
        raise ValueError("Artifact path must be below evidence/ or logs/.")
    resolved_root = release_dir.resolve()
    resolved = (release_dir / candidate).resolve(strict=True)
    if not resolved.is_relative_to(resolved_root):
        raise ValueError(f"Artifact path escapes the release directory: {relative_path}")
    if not resolved.is_file():
        raise ValueError(f"Artifact is not a regular file: {relative_path}")
    return resolved


def configured_sensitive_values() -> tuple[str, ...]:
    values: set[str] = set()
    for name in ("DATABASE_URL", "RUNTIME_DATABASE_URL"):
        configured = os.getenv(name, "").strip()
        if not configured:
            continue
        values.add(configured)
        password = urlsplit(configured).password
        if password:
            values.update((password, unquote(password)))
    return tuple(sorted((value for value in values if value), key=len, reverse=True))


def validate_secret_free(
    value: Any,
    path: str = "$",
    sensitive_values: tuple[str, ...] | None = None,
) -> None:
    sensitive_values = (
        configured_sensitive_values() if sensitive_values is None else sensitive_values
    )
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = str(key).lower()
            metric_key = normalized_key.endswith(("_tokens", "_token_count")) or normalized_key in {
                "tokens",
                "token_count",
                "token_usage",
            }
            if (
                SECRET_KEY_PATTERN.search(str(key))
                and not metric_key
                and not isinstance(item, (dict, list))
            ):
                safe_marker = isinstance(item, bool) or item in (None, "")
                if isinstance(item, str):
                    safe_marker = item.lower() in {
                        "placeholder",
                        "redacted",
                        "configured",
                        "true",
                        "false",
                    }
                if not safe_marker:
                    raise ValueError(f"Secret-like evidence key is forbidden: {path}.{key}")
            validate_secret_free(item, f"{path}.{key}", sensitive_values)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_secret_free(item, f"{path}[{index}]", sensitive_values)
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
            raise ValueError(f"Secret-like evidence value is forbidden: {path}")
        if any(secret in value for secret in sensitive_values):
            raise ValueError(f"Configured runtime secret is forbidden in evidence: {path}")


def validate_evidence(document: Any, release_id: str, started_at: str, path: Path) -> None:
    validate_secret_free(document)
    timestamps: list[datetime] = []

    def walk(value: Any, json_path: str = "$") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "release_id" and item != release_id:
                    raise ValueError(f"Cross-release evidence at {json_path}.release_id: {item!r}")
                if key.endswith("_at") and isinstance(item, str):
                    try:
                        timestamps.append(parse_timestamp(item))
                    except ValueError as error:
                        raise ValueError(
                            f"Invalid evidence timestamp at {json_path}.{key}"
                        ) from error
                walk(item, f"{json_path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{json_path}[{index}]")

    walk(document)
    oldest = min(timestamps or [datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)])
    if oldest < parse_timestamp(started_at):
        raise ValueError(f"Stale evidence predates release start: {path.name}")


def load_record(release_dir: Path) -> dict[str, Any]:
    path = release_dir / "release.json"
    if not path.is_file():
        raise ValueError(f"Release record is not initialized: {path}")
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("lane") != LANE:
        raise ValueError("Release record belongs to a different lane.")
    return record


def initialize_record(
    *,
    release_id: str,
    repository: str,
    commit: str,
    profile: Path,
    environment: str,
    subscription_id: str,
    resource_group: str,
    location: str,
    executor: str,
    required_gates: list[str],
    releases_root: Path = RELEASES_ROOT,
) -> Path:
    release_dir = release_directory(release_id, releases_root)
    record_path = release_dir / "release.json"
    if record_path.exists():
        raise ValueError(f"Release record already exists: {record_path}")
    profile = profile.resolve(strict=True)
    if not profile.is_file():
        raise ValueError("Profile must be a regular file.")
    try:
        profile_name = profile.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        profile_name = profile.name
    now = utc_now()
    record = {
        "schema_version": 1,
        "contract": "underwriting-release/v1",
        "project": "underwriting",
        "lane": LANE,
        "release_id": release_id,
        "source": {"repository": repository, "commit": commit},
        "target": {
            "profile": profile_name,
            "profile_sha256": sha256_file(profile),
            "environment": environment,
            "subscription_id": subscription_id,
            "resource_group": resource_group,
            "location": location,
        },
        "execution": {"executor": executor, "workflow_run_id": None},
        "status": "running",
        "started_at": now,
        "updated_at": now,
        "completed_at": None,
        "failed_stage": None,
        "error": None,
        "gates": {gate: {"status": "pending", "artifact": None} for gate in required_gates},
        "artifacts": [],
        "durable_artifact": None,
        "extensions": {
            "required_gates": required_gates,
            TIMING_EXTENSION: {
                "version": 1,
                "app_only_started_at": None,
                "telemetry_succeeded_at": None,
                "app_only_duration_ms": None,
                "app_only": {
                    "status": "pending",
                    "started_at": None,
                    "ended_at": None,
                    "duration_ms": None,
                },
                "stages": {},
            },
        },
    }
    validate_secret_free(record)
    atomic_json_write(record_path, record)
    (release_dir / "evidence").mkdir(exist_ok=True)
    (release_dir / "logs").mkdir(exist_ok=True)
    return record_path


def register_artifact(
    release_id: str,
    relative_path: str,
    gate: str | None = None,
    releases_root: Path = RELEASES_ROOT,
) -> None:
    release_dir = release_directory(release_id, releases_root)
    record = load_record(release_dir)
    if record["status"] != "running":
        raise ValueError("Artifacts cannot be registered after finalization.")
    normalized = Path(relative_path).as_posix()
    if normalized in {item["path"] for item in record["artifacts"]}:
        raise ValueError(f"Duplicate artifact path: {normalized}")
    path = safe_artifact_path(release_dir, normalized)
    if path.suffix.lower() == ".json":
        document = json.loads(path.read_text(encoding="utf-8"))
        validate_evidence(document, release_id, record["started_at"], path)
    else:
        validate_secret_free(path.read_text(encoding="utf-8", errors="replace"))
        if datetime.fromtimestamp(path.stat().st_mtime, tz=UTC) < parse_timestamp(
            record["started_at"]
        ):
            raise ValueError(f"Stale artifact predates release start: {normalized}")
    artifact = {
        "path": normalized,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }
    record["artifacts"].append(artifact)
    if gate:
        if gate not in record["gates"]:
            raise ValueError(f"Undeclared release gate: {gate}")
        record["gates"][gate] = {"status": "succeeded", "artifact": normalized}
    record["updated_at"] = utc_now()
    atomic_json_write(release_dir / "release.json", record)


def finalize_record(
    release_id: str,
    status: str,
    failed_stage: str | None = None,
    error: str | None = None,
    releases_root: Path = RELEASES_ROOT,
) -> None:
    if status not in {"succeeded", "failed"}:
        raise ValueError("Final status must be succeeded or failed.")
    release_dir = release_directory(release_id, releases_root)
    record = load_record(release_dir)
    if record["status"] != "running":
        raise ValueError("Release record is already finalized.")
    if status == "succeeded":
        validate_succeeded_timing(record)
        required = record.get("extensions", {}).get("required_gates", [])
        incomplete = [
            gate for gate in required if record["gates"].get(gate, {}).get("status") != "succeeded"
        ]
        if incomplete:
            raise ValueError(f"Required gates are not successful: {', '.join(incomplete)}")
        for artifact in record["artifacts"]:
            path = safe_artifact_path(release_dir, artifact["path"])
            if (
                sha256_file(path) != artifact["sha256"]
                or path.stat().st_size != artifact["size_bytes"]
            ):
                raise ValueError(f"Artifact changed after registration: {artifact['path']}")
    else:
        if not failed_stage:
            raise ValueError("failed_stage is required for failed releases.")
        validate_secret_free(error or "")
        for gate, result in record["gates"].items():
            if gate == failed_stage and result["status"] == "pending":
                record["gates"][gate] = {"status": "failed", "artifact": None}
    record.update(
        {
            "status": status,
            "updated_at": utc_now(),
            "completed_at": utc_now(),
            "failed_stage": failed_stage if status == "failed" else None,
            "error": error if status == "failed" else None,
        }
    )
    validate_secret_free(record)
    atomic_json_write(release_dir / "release.json", record)
    manifest = {
        "schema_version": 1,
        "release_id": release_id,
        "generated_at": record["updated_at"],
        "artifacts": record["artifacts"],
    }
    atomic_json_write(release_dir / "provenance-manifest.json", manifest)
    checksum_path = release_dir / "checksums.sha256"
    checksum_temporary = checksum_path.with_name(f".{checksum_path.name}.{os.getpid()}.tmp")
    try:
        checksum_temporary.write_text(
            "".join(
                f"{artifact['sha256']}  {artifact['path']}\n"
                for artifact in sorted(record["artifacts"], key=lambda item: item["path"])
            ),
            encoding="utf-8",
        )
        checksum_temporary.replace(checksum_path)
    finally:
        checksum_temporary.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Underwriting release records.")
    parser.add_argument("--releases-root", type=Path, default=RELEASES_ROOT, help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init")
    initialize.add_argument("--release-id", required=True)
    initialize.add_argument("--repository", required=True)
    initialize.add_argument("--commit", required=True)
    initialize.add_argument("--profile", type=Path, required=True)
    initialize.add_argument("--environment", required=True)
    initialize.add_argument("--subscription-id", required=True)
    initialize.add_argument("--resource-group", required=True)
    initialize.add_argument("--location", required=True)
    initialize.add_argument("--executor", required=True)
    initialize.add_argument("--required-gate", action="append", default=[])
    register = commands.add_parser("register")
    register.add_argument("--release-id", required=True)
    register.add_argument("--path", required=True)
    register.add_argument("--gate")
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--release-id", required=True)
    finalize.add_argument("--status", choices=("succeeded", "failed"), required=True)
    finalize.add_argument("--failed-stage")
    finalize.add_argument("--error")
    resume = commands.add_parser("resume")
    resume.add_argument("--release-id", required=True)
    resume.add_argument("--from-stage", choices=TIMING_STAGES, required=True)
    resume.add_argument("--at", help=argparse.SUPPRESS)
    timing = commands.add_parser("timing")
    timing.add_argument("--release-id", required=True)
    timing.add_argument("--stage", choices=TIMING_STAGES, required=True)
    timing.add_argument("--action", choices=("start", "succeed", "fail"), required=True)
    timing.add_argument("--start-app-only", action="store_true")
    timing.add_argument("--at", help=argparse.SUPPRESS)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "init":
        path = initialize_record(
            release_id=args.release_id,
            repository=args.repository,
            commit=args.commit,
            profile=args.profile,
            environment=args.environment,
            subscription_id=args.subscription_id,
            resource_group=args.resource_group,
            location=args.location,
            executor=args.executor,
            required_gates=args.required_gate,
            releases_root=args.releases_root,
        )
        print(path)
    elif args.command == "register":
        register_artifact(args.release_id, args.path, args.gate, releases_root=args.releases_root)
    elif args.command == "finalize":
        finalize_record(
            args.release_id,
            args.status,
            args.failed_stage,
            args.error,
            releases_root=args.releases_root,
        )
    elif args.command == "resume":
        resume_record(
            args.release_id,
            args.from_stage,
            at=args.at,
            releases_root=args.releases_root,
        )
    elif args.action == "start":
        start_release_timing(
            args.release_id,
            args.stage,
            start_app_only=args.start_app_only,
            at=args.at,
            releases_root=args.releases_root,
        )
    else:
        finish_release_timing(
            args.release_id,
            args.stage,
            "succeeded" if args.action == "succeed" else "failed",
            at=args.at,
            releases_root=args.releases_root,
        )


if __name__ == "__main__":
    main()
