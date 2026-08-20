from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RELEASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_GATES = {
    "release_gates": ("evidence/release-gates.json", "passed"),
    "model_preflight": ("evidence/model-preflight.json", "passed"),
    "deployment_verification": ("evidence/deployment-verification.json", "passed"),
    "hosted_smoke": ("evidence/hosted-smoke.json", "passed"),
    "hosted_e2e": ("evidence/hosted-e2e.json", "passed"),
    "browser_e2e": ("evidence/browser-e2e.json", "passed"),
    "appinsights_connection": ("evidence/appinsights-connection.json", "passed"),
    "telemetry": ("evidence/telemetry.json", "passed"),
    "evaluation": ("evidence/evaluation.json", "completed"),
}
TIMING_STAGES = (
    "app_only",
    "local_gates",
    "runner_bootstrap",
    "runner_preflight",
    "private_readiness",
    "package_build",
    "backend_deployment",
    "frontend_deployment",
    "hosted_deployment_activation",
    "verification",
    "smoke",
    "hosted_e2e",
    "browser_e2e",
    "evaluation",
    "telemetry",
    "final_evidence",
)
# Browser validation and report-only Foundry evaluations are bounded independently,
# but their combined private-network release window can exceed a short deployment SLA.
MAX_APP_TO_TELEMETRY_MS = 60 * 60 * 1000
SECRET_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "credential",
    "api_key",
    "apikey",
    "connection_string",
    "connectionstring",
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)\b(?:postgres(?:ql)?(?:\+psycopg)?|mysql|mongodb(?:\+srv)?)://"),
    re.compile(r"(?i)\b(?:instrumentationkey|accountkey|sharedaccesskey|clientsecret)="),
    re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)\bhttps?://[^/\s:@]+:[^@/\s]+@"),
)


def utc_timestamp(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty ISO 8601 timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def assert_secret_free(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            forbidden_key = any(part in normalized for part in SECRET_KEY_PARTS) or (
                "database_url" in normalized
                and not normalized.endswith(("_sha256", "_matches"))
            )
            if forbidden_key:
                raise ValueError(f"Secret-bearing key is not allowed in evidence: {path}.{key}")
            assert_secret_free(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            assert_secret_free(item, f"{path}[{index}]")
        return
    if isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
        raise ValueError(f"Secret-bearing value is not allowed in evidence: {path}")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Evidence file must contain a JSON object: {path}")
    return payload


def atomic_write_json(path: Path, payload: dict[str, Any], *, create: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_secret_free(payload)
    if create and path.exists():
        raise ValueError(f"Release record already exists: {path}")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if create and path.exists():
            raise ValueError(f"Release record already exists: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def release_lock(release_dir: Path) -> Any:
    lock_path = release_dir / ".release.lock"
    with lock_path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def duration_ms(started_at: datetime, ended_at: datetime) -> int:
    return round((ended_at - started_at).total_seconds() * 1000)


def timing_extension(record: dict[str, Any]) -> dict[str, Any]:
    extensions = record.get("extensions")
    timing = extensions.get("release_timing") if isinstance(extensions, dict) else None
    if not isinstance(timing, dict) or not isinstance(timing.get("stages"), dict):
        raise ValueError("Release timing extension is missing or invalid")
    return timing


def record_stage_timing(
    project_root: Path,
    release_id: str,
    stage: str,
    action: str,
    *,
    status: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    if stage not in TIMING_STAGES:
        raise ValueError(f"Unsupported release timing stage: {stage}")
    if action not in {"start", "end"}:
        raise ValueError("Timing action must be start or end")
    if action == "end" and status not in {"succeeded", "failed"}:
        raise ValueError("Timing end requires succeeded or failed status")
    moment = parse_timestamp(timestamp, "timing timestamp") if timestamp else datetime.now(timezone.utc)
    release_dir = release_directory(project_root, release_id)
    record_path = release_dir / "release.json"
    with release_lock(release_dir):
        record = read_json(record_path)
        if record.get("status") != "running":
            raise ValueError("Timing may only be recorded for a running release")
        timing = timing_extension(record)
        stages = timing["stages"]
        existing = stages.get(stage)
        if action == "start":
            if existing is not None:
                raise ValueError(f"Timing stage already started: {stage}")
            stages[stage] = {
                "status": "running",
                "started_at": utc_timestamp(moment),
                "ended_at": None,
                "duration_ms": None,
            }
            if stage == "app_only":
                timing["total"] = {
                    "status": "running",
                    "started_at": utc_timestamp(moment),
                    "ended_at": None,
                    "duration_ms": None,
                }
        else:
            if not isinstance(existing, dict) or existing.get("status") != "running":
                raise ValueError(f"Timing stage is not running: {stage}")
            started_at = parse_timestamp(existing.get("started_at"), f"{stage} started_at")
            elapsed = duration_ms(started_at, moment)
            if elapsed < 0:
                raise ValueError(f"Timing stage ends before it starts: {stage}")
            existing.update(
                status=status,
                ended_at=utc_timestamp(moment),
                duration_ms=elapsed,
            )
            if stage == "app_only":
                timing["total"] = {
                    "status": status,
                    "started_at": utc_timestamp(started_at),
                    "ended_at": utc_timestamp(moment),
                    "duration_ms": elapsed,
                }
        record["updated_at"] = utc_timestamp(moment)
        atomic_write_json(record_path, record)
        return existing if isinstance(existing, dict) else stages[stage]


def resume_release(
    project_root: Path,
    release_id: str,
    from_stage: str,
    *,
    timestamp: str | None = None,
) -> dict[str, Any]:
    moment = parse_timestamp(timestamp, "resume timestamp") if timestamp else datetime.now(
        timezone.utc
    )
    release_dir = release_directory(project_root, release_id)
    record_path = release_dir / "release.json"
    with release_lock(release_dir):
        record = read_json(record_path)
        if record.get("status") != "failed":
            raise ValueError("Only a failed release may be resumed")
        timing = timing_extension(record)
        stages = timing["stages"]
        from_index = TIMING_STAGES.index(from_stage)
        for stage in TIMING_STAGES[from_index:]:
            stages.pop(stage, None)
        app_only = stages.get("app_only")
        if not isinstance(app_only, dict) or not isinstance(app_only.get("started_at"), str):
            raise ValueError("Cannot resume without app_only timing")
        app_only.update(status="running", ended_at=None, duration_ms=None)
        timing["total"] = {
            "status": "running",
            "started_at": app_only["started_at"],
            "ended_at": None,
            "duration_ms": None,
        }
        record.update(
            status="running",
            updated_at=utc_timestamp(moment),
            completed_at=None,
            failed_stage=None,
            error=None,
            artifacts=[],
        )
        atomic_write_json(record_path, record)
        return record


def validate_release_timing(record: dict[str, Any]) -> None:
    timing = timing_extension(record)
    stages = timing["stages"]
    missing = [stage for stage in TIMING_STAGES if stage not in stages]
    if missing:
        raise ValueError(f"Release timing stages are missing: {', '.join(missing)}")

    parsed: dict[str, tuple[datetime, datetime]] = {}
    for stage in TIMING_STAGES:
        entry = stages[stage]
        if not isinstance(entry, dict) or entry.get("status") != "succeeded":
            raise ValueError(f"Release timing stage did not succeed: {stage}")
        started_at = parse_timestamp(entry.get("started_at"), f"{stage} started_at")
        ended_at = parse_timestamp(entry.get("ended_at"), f"{stage} ended_at")
        expected_duration = duration_ms(started_at, ended_at)
        if expected_duration < 0 or entry.get("duration_ms") != expected_duration:
            raise ValueError(f"Release timing duration is invalid: {stage}")
        parsed[stage] = (started_at, ended_at)

    app_start, app_end = parsed["app_only"]
    if app_end != parsed["telemetry"][1]:
        raise ValueError("app_only timing must end at telemetry success")
    for stage in TIMING_STAGES[1:-1]:
        if parsed[stage][0] < app_start or (
            stage != "evaluation" and parsed[stage][1] > app_end
        ):
            raise ValueError(f"Release timing stage is outside app_only: {stage}")
    ordered_after = (
        ("local_gates", "runner_bootstrap"),
        ("runner_bootstrap", "runner_preflight"),
        ("runner_preflight", "private_readiness"),
        ("private_readiness", "package_build"),
        ("package_build", "backend_deployment"),
        ("package_build", "frontend_deployment"),
        ("package_build", "hosted_deployment_activation"),
        ("backend_deployment", "verification"),
        ("frontend_deployment", "verification"),
        ("hosted_deployment_activation", "verification"),
        ("verification", "smoke"),
        ("smoke", "hosted_e2e"),
        ("hosted_e2e", "browser_e2e"),
        ("hosted_e2e", "evaluation"),
        ("hosted_e2e", "telemetry"),
        ("telemetry", "final_evidence"),
        ("evaluation", "final_evidence"),
        ("browser_e2e", "final_evidence"),
    )
    for earlier, later in ordered_after:
        if parsed[later][0] < parsed[earlier][1]:
            raise ValueError(f"Release timing order is invalid: {earlier} -> {later}")

    total = timing.get("total")
    expected_total = duration_ms(app_start, app_end)
    if expected_total > MAX_APP_TO_TELEMETRY_MS:
        raise ValueError("App-only to telemetry exceeded the 60-minute release budget")
    if not isinstance(total, dict) or (
        total.get("status") != "succeeded"
        or parse_timestamp(total.get("started_at"), "total started_at") != app_start
        or parse_timestamp(total.get("ended_at"), "total ended_at") != app_end
        or total.get("duration_ms") != expected_total
    ):
        raise ValueError("Release timing total is invalid")


def close_running_timings(record: dict[str, Any], failed_stage: str, ended_at: datetime) -> None:
    timing = timing_extension(record)
    for stage, entry in timing["stages"].items():
        if isinstance(entry, dict) and entry.get("status") == "running":
            started_at = parse_timestamp(entry.get("started_at"), f"{stage} started_at")
            entry.update(
                status="failed",
                ended_at=utc_timestamp(ended_at),
                duration_ms=max(0, duration_ms(started_at, ended_at)),
            )
    app_only = timing["stages"].get("app_only")
    if isinstance(app_only, dict) and app_only.get("ended_at"):
        timing["total"] = {
            "started_at": app_only["started_at"],
            "ended_at": app_only["ended_at"],
            "duration_ms": app_only["duration_ms"],
            "status": "failed",
            "failed_stage": failed_stage,
        }


def validate_release_id(release_id: str) -> None:
    if not RELEASE_ID_PATTERN.fullmatch(release_id):
        raise ValueError("release_id does not satisfy the langgraph-release/v1 contract")


def release_directory(project_root: Path, release_id: str, *, create: bool = False) -> Path:
    validate_release_id(release_id)
    resolved_project_root = project_root.resolve()
    artifacts_root = resolved_project_root / ".artifacts"
    releases_root = artifacts_root / "releases"
    if artifacts_root.is_symlink() or releases_root.is_symlink():
        raise ValueError("Release path parents may not be symlinks")
    if create:
        releases_root.mkdir(parents=True, exist_ok=True)
    candidate = releases_root / release_id
    if candidate.is_symlink():
        raise ValueError("Release directory may not be a symlink")
    if create:
        candidate.mkdir(mode=0o750, exist_ok=False)
        (candidate / "evidence").mkdir(mode=0o750)
        (candidate / "logs").mkdir(mode=0o750)
    if candidate.resolve(strict=False).parent != releases_root:
        raise ValueError("Release path escapes the release root")
    return candidate


def safe_artifact_path(release_dir: Path, relative_path: str, *, must_exist: bool) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Artifact path is absolute or traverses directories: {relative_path}")
    if not relative.parts or relative.parts[0] not in {"evidence", "logs"}:
        raise ValueError(f"Artifact path must be below evidence/ or logs/: {relative_path}")
    candidate = release_dir / relative
    current = release_dir
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"Artifact path contains a symlink: {relative_path}")
    if must_exist and (not candidate.is_file() or candidate.is_symlink()):
        raise ValueError(f"Required artifact is missing or unsafe: {relative_path}")
    try:
        candidate.resolve(strict=must_exist).relative_to(release_dir.resolve())
    except ValueError as error:
        raise ValueError(f"Artifact path escapes the release directory: {relative_path}") from error
    return candidate


def parse_profile(profile_path: Path) -> dict[str, str]:
    if not profile_path.is_file() or profile_path.is_symlink():
        raise ValueError("Deployment profile must be a regular non-symlink file")
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(profile_path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line or raw_line.startswith("#"):
            continue
        if "=" not in raw_line:
            raise ValueError(f"Invalid profile declaration on line {line_number}")
        key, value = raw_line.split("=", 1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or not value or key in values:
            raise ValueError(f"Invalid profile declaration on line {line_number}")
        values[key] = value
    required = {
        "AZURE_ENV_NAME",
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_RESOURCE_GROUP",
        "AZURE_LOCATION",
    }
    missing = sorted(required - values.keys())
    if missing:
        raise ValueError(f"Deployment profile is missing: {', '.join(missing)}")
    if values.get("DEPLOYMENT_LANE") != "foundry-private":
        raise ValueError("Deployment profile must declare DEPLOYMENT_LANE=foundry-private")
    assert_secret_free(values, "$.profile")
    return values


def git_value(project_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def initialize_release(
    project_root: Path,
    release_id: str,
    started_at: str,
    profile_path: Path,
    *,
    executor: str = "local",
) -> dict[str, Any]:
    parse_timestamp(started_at, "started_at")
    profile = parse_profile(profile_path)
    release_dir = release_directory(project_root, release_id, create=True)
    profile_relative = os.path.relpath(profile_path.resolve(), project_root.resolve())
    record: dict[str, Any] = {
        "schema_version": 1,
        "contract": "langgraph-release/v1",
        "project": "order-resolution",
        "lane": "order-resolution-foundry-private",
        "release_id": release_id,
        "source": {
            "repository": git_value(project_root, "config", "--get", "remote.origin.url")
            or str(project_root.resolve()),
            "commit": git_value(project_root, "rev-parse", "HEAD") or "0000000",
        },
        "target": {
            "profile": profile_relative,
            "profile_sha256": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
            "environment": profile["AZURE_ENV_NAME"],
            "subscription_id": profile["AZURE_SUBSCRIPTION_ID"],
            "resource_group": profile["AZURE_RESOURCE_GROUP"],
            "location": profile["AZURE_LOCATION"],
        },
        "execution": {
            "executor": executor,
            "workflow_run_id": os.getenv("GITHUB_RUN_ID"),
        },
        "status": "running",
        "started_at": utc_timestamp(parse_timestamp(started_at, "started_at")),
        "updated_at": utc_timestamp(),
        "completed_at": None,
        "failed_stage": None,
        "error": None,
        "gates": {
            name: {"status": "pending", "artifact": relative_path}
            for name, (relative_path, _) in REQUIRED_GATES.items()
        },
        "artifacts": [],
        "durable_artifact": None,
        "extensions": {
            "release_authority": "code_only",
            "validation_state": "prepared_not_live_validated",
            "release_timing": {
                "version": 1,
                "clock": "utc",
                "stages": {},
                "total": None,
            },
        },
    }
    atomic_write_json(release_dir / "release.json", record, create=True)
    return record


def validate_gate(
    release_dir: Path,
    release_id: str,
    started_at: datetime,
    name: str,
    relative_path: str,
    expected_status: str,
) -> dict[str, Any]:
    path = safe_artifact_path(release_dir, relative_path, must_exist=True)
    payload = read_json(path)
    assert_secret_free(payload, f"$.gates.{name}")
    if payload.get("status") != expected_status:
        raise ValueError(
            f"{name} evidence status must be {expected_status}, got {payload.get('status')}"
        )
    if name == "evaluation":
        validate_evaluation_counts(payload)
    artifact_release_id = payload.get("release_id")
    if artifact_release_id is not None and artifact_release_id != release_id:
        raise ValueError(f"{name} evidence belongs to another release")
    timestamp_value = payload.get("generated_at") or payload.get("started_at")
    if parse_timestamp(timestamp_value, f"{name} generated_at") < started_at:
        raise ValueError(f"{name} evidence predates the release window")
    return payload


def validate_evaluation_counts(payload: dict[str, Any]) -> None:
    result_counts = payload.get("result_counts")
    if not isinstance(result_counts, dict):
        raise ValueError("evaluation evidence must include result_counts")
    errored = int(result_counts.get("errored", 0))
    failed = int(result_counts.get("failed", 0))
    passed = int(result_counts.get("passed", 0))
    total = int(result_counts.get("total", 0))
    if errored or failed or total < 1 or passed < 1:
        raise ValueError(
            "evaluation evidence did not pass: "
            f"passed={passed}, failed={failed}, errored={errored}, total={total}"
        )


def artifact_inventory(release_dir: Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    seen: set[str] = set()
    for directory_name in ("evidence", "logs"):
        directory = release_dir / directory_name
        if directory.is_symlink():
            raise ValueError(f"{directory_name}/ may not be a symlink")
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if path.is_dir():
                continue
            relative_path = path.relative_to(release_dir).as_posix()
            safe_path = safe_artifact_path(release_dir, relative_path, must_exist=True)
            if relative_path in seen:
                raise ValueError(f"Duplicate artifact path: {relative_path}")
            seen.add(relative_path)
            content = safe_path.read_bytes()
            if safe_path.suffix.lower() == ".json":
                assert_secret_free(read_json(safe_path), f"$.artifacts.{relative_path}")
            inventory.append(
                {
                    "path": relative_path,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
            )
    return inventory


def safe_failure_text(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > 240:
        raise ValueError(f"{field} must be a non-empty summary of at most 240 characters")
    assert_secret_free(normalized, f"$.{field}")
    return normalized


def finalize_release(
    project_root: Path,
    release_id: str,
    status: str,
    *,
    failed_stage: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    if status not in {"succeeded", "failed"}:
        raise ValueError("Final status must be succeeded or failed")
    release_dir = release_directory(project_root, release_id)
    record_path = release_dir / "release.json"
    with release_lock(release_dir):
        record = read_json(record_path)
        if record.get("release_id") != release_id or record.get("status") != "running":
            raise ValueError("Only the active running release may be finalized")
        existing_artifact_paths = [
            item.get("path")
            for item in record.get("artifacts", [])
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        ]
        if len(existing_artifact_paths) != len(set(existing_artifact_paths)):
            raise ValueError("Release record contains duplicate artifact paths")
        started_at = parse_timestamp(record.get("started_at"), "release started_at")
        completed_at = datetime.now(timezone.utc)
        if status == "succeeded":
            validate_release_timing(record)
            for name, (relative_path, expected_status) in REQUIRED_GATES.items():
                validate_gate(
                    release_dir,
                    release_id,
                    started_at,
                    name,
                    relative_path,
                    expected_status,
                )
                record["gates"][name] = {"status": "succeeded", "artifact": relative_path}
            record["failed_stage"] = None
            record["error"] = None
        else:
            safe_stage = safe_failure_text(failed_stage, "failed_stage")
            safe_error = safe_failure_text(error, "error")
            if not safe_stage or not safe_error:
                raise ValueError("Failed releases require safe failed_stage and error summaries")
            close_running_timings(record, safe_stage, completed_at)
            if safe_stage in record["gates"]:
                record["gates"][safe_stage]["status"] = "failed"
            record["failed_stage"] = safe_stage
            record["error"] = safe_error
        record["artifacts"] = artifact_inventory(release_dir) if status == "succeeded" else []
        record["status"] = status
        record["completed_at"] = utc_timestamp(completed_at)
        record["updated_at"] = record["completed_at"]
        assert_secret_free(record)
        atomic_write_json(record_path, record)
        return record


def build_release_report(
    context: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    release_id = context.get("release_id")
    if not isinstance(release_id, str) or not release_id:
        raise ValueError("Release context must contain release_id")
    release_started_at = parse_timestamp(context.get("started_at"), "release context started_at")
    for name, (_, expected_status) in REQUIRED_GATES.items():
        payload = artifacts.get(name)
        if not isinstance(payload, dict):
            raise ValueError(f"Missing required release evidence: {name}")
        if payload.get("status") != expected_status:
            raise ValueError(
                f"{name} evidence status must be {expected_status}, got {payload.get('status')}"
            )
        if payload.get("release_id") != release_id:
            raise ValueError(f"{name} evidence release_id does not match the release context")
        if parse_timestamp(payload.get("generated_at"), f"{name} generated_at") < release_started_at:
            raise ValueError(f"{name} evidence predates the release window")
        assert_secret_free(payload, f"$.artifacts.{name}")
    conversation_ids = artifacts["hosted_e2e"].get("conversation_ids")
    if not isinstance(conversation_ids, list) or len(conversation_ids) != 3:
        raise ValueError("Hosted E2E evidence must contain three conversation IDs")
    if len({value for value in conversation_ids if isinstance(value, str) and value}) != 3:
        raise ValueError("Hosted E2E conversation IDs must be non-empty and unique")
    report = {
        "schema_version": 1,
        "evidence_type": "release_window",
        "status": "passed",
        "release_id": release_id,
        "started_at": utc_timestamp(release_started_at),
        "generated_at": utc_timestamp(generated_at),
        "target": artifacts["deployment_verification"].get("target"),
        "conversation_ids": conversation_ids,
        "summary": {name: payload["status"] for name, payload in artifacts.items()},
        "artifacts": artifacts,
    }
    assert_secret_free(report)
    return report


def aggregate_release(project_root: Path, release_id: str) -> dict[str, Any]:
    release_dir = release_directory(project_root, release_id)
    context = read_json(release_dir / "release.json")
    artifacts = {
        name: read_json(safe_artifact_path(release_dir, relative_path, must_exist=True))
        for name, (relative_path, _) in REQUIRED_GATES.items()
    }
    report = build_release_report(context, artifacts)
    atomic_write_json(release_dir / "evidence" / "release-window.json", report)
    return report


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Manage langgraph-release/v1 evidence")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--release-id", required=True)
    init_parser.add_argument("--started-at", required=True)
    init_parser.add_argument("--profile", required=True, type=Path)
    init_parser.add_argument("--executor", default="local")
    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("--release-id", required=True)
    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--release-id", required=True)
    finalize_parser.add_argument("--status", required=True, choices=("succeeded", "failed"))
    finalize_parser.add_argument("--failed-stage")
    finalize_parser.add_argument("--error")
    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--release-id", required=True)
    resume_parser.add_argument("--from-stage", required=True, choices=TIMING_STAGES)
    resume_parser.add_argument("--timestamp")
    timing_parser = subparsers.add_parser("timing")
    timing_parser.add_argument("--release-id", required=True)
    timing_parser.add_argument("--stage", required=True, choices=TIMING_STAGES)
    timing_parser.add_argument("--action", required=True, choices=("start", "end"))
    timing_parser.add_argument("--status", choices=("succeeded", "failed"))
    timing_parser.add_argument("--timestamp")
    args = parser.parse_args()
    if args.command == "init":
        result = initialize_release(
            project_root, args.release_id, args.started_at, args.profile, executor=args.executor
        )
    elif args.command == "aggregate":
        result = aggregate_release(project_root, args.release_id)
    elif args.command == "finalize":
        result = finalize_release(
            project_root,
            args.release_id,
            args.status,
            failed_stage=args.failed_stage,
            error=args.error,
        )
    elif args.command == "resume":
        result = resume_release(
            project_root,
            args.release_id,
            args.from_stage,
            timestamp=args.timestamp,
        )
    else:
        result = record_stage_timing(
            project_root,
            args.release_id,
            args.stage,
            args.action,
            status=args.status,
            timestamp=args.timestamp,
        )
    print(json.dumps({"release_id": args.release_id, "status": result["status"]}))


if __name__ == "__main__":
    main()
