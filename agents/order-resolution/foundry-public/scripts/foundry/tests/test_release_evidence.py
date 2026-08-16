from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.foundry.release_evidence import (
    REQUIRED_GATES,
    artifact_inventory,
    assert_secret_free,
    build_release_report,
    finalize_release,
    initialize_release,
    record_stage_timing,
    resume_release,
    safe_artifact_path,
    validate_release_timing,
)
from scripts.foundry.release_migration import migration_plan


def artifact(
    evidence_type: str,
    status: str = "passed",
    *,
    release_id: str = "release-1",
    generated_at: str = "2026-08-15T20:05:00Z",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "evidence_type": evidence_type,
        "status": status,
        "release_id": release_id,
        "generated_at": generated_at,
    }


def all_artifacts() -> dict[str, dict[str, object]]:
    return {
        "model_preflight": artifact("model_preflight"),
        "deployment_verification": {
            **artifact("deployment_verification"),
            "target": {
                "subscription_id": "7df95e88-701c-4693-af77-3159f83b558d",
                "resource_group": "rg-langgraph-ora-foundry-public",
                "location": "eastus2",
            },
        },
        "hosted_smoke": artifact("hosted_smoke"),
        "hosted_e2e": {
            **artifact("hosted_e2e"),
            "conversation_ids": ["conv-low", "conv-high", "conv-damaged"],
        },
        "appinsights_connection": artifact("appinsights_connection"),
        "telemetry": artifact("telemetry"),
        "evaluation": {
            **artifact("evaluation", status="completed"),
            "result_counts": {
                "passed": 1,
                "failed": 0,
                "errored": 0,
                "total": 1,
            },
        },
    }


def write_profile(path: Path) -> None:
    path.write_text(
        "\n".join(
            (
                "AZURE_ENV_NAME=order-resolution-foundry-public",
                "AZURE_SUBSCRIPTION_ID=7df95e88-701c-4693-af77-3159f83b558d",
                "AZURE_RESOURCE_GROUP=rg-langgraph-ora-foundry-public",
                "AZURE_LOCATION=eastus2",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def initialized_release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    profile = tmp_path / "foundry-public.env"
    write_profile(profile)
    monkeypatch.setattr(
        "scripts.foundry.release_evidence.git_value",
        lambda _root, *args: (
            "https://example.invalid/langgraph.git"
            if args[0] == "config"
            else "0123456789abcdef0123456789abcdef01234567"
        ),
    )
    initialize_release(
        tmp_path,
        "release-1",
        "2026-08-15T20:00:00Z",
        profile,
    )
    return tmp_path / ".artifacts" / "releases" / "release-1"


def write_gate_files(release_dir: Path, artifacts: dict[str, dict[str, object]]) -> None:
    for name, (relative_path, _) in REQUIRED_GATES.items():
        path = release_dir / relative_path
        path.write_text(json.dumps(artifacts[name]) + "\n", encoding="utf-8")


SUCCESS_TIMINGS = {
    "app_only": ("2026-08-15T20:01:00.000Z", "2026-08-15T20:10:00.000Z"),
    "package_build": ("2026-08-15T20:01:00.100Z", "2026-08-15T20:02:00.100Z"),
    "backend_deployment": ("2026-08-15T20:02:00.200Z", "2026-08-15T20:05:00.200Z"),
    "frontend_deployment": ("2026-08-15T20:02:00.300Z", "2026-08-15T20:04:00.300Z"),
    "hosted_deployment_activation": (
        "2026-08-15T20:02:00.400Z",
        "2026-08-15T20:06:00.400Z",
    ),
    "verification": ("2026-08-15T20:06:00.500Z", "2026-08-15T20:07:00.500Z"),
    "smoke": ("2026-08-15T20:07:00.600Z", "2026-08-15T20:07:10.600Z"),
    "hosted_e2e": ("2026-08-15T20:07:10.700Z", "2026-08-15T20:09:00.700Z"),
    "evaluation": ("2026-08-15T20:07:10.800Z", "2026-08-15T20:09:30.800Z"),
    "telemetry": ("2026-08-15T20:09:00.800Z", "2026-08-15T20:10:00.000Z"),
    "final_evidence": ("2026-08-15T20:10:00.100Z", "2026-08-15T20:10:01.100Z"),
}


def write_success_timings(project_root: Path) -> None:
    for stage, (started_at, ended_at) in SUCCESS_TIMINGS.items():
        record_stage_timing(
            project_root, "release-1", stage, "start", timestamp=started_at
        )
        record_stage_timing(
            project_root,
            "release-1",
            stage,
            "end",
            status="succeeded",
            timestamp=ended_at,
        )


def test_build_release_report_requires_one_fresh_three_conversation_window() -> None:
    report = build_release_report(
        {"release_id": "release-1", "started_at": "2026-08-15T20:00:00Z"},
        all_artifacts(),
        generated_at=datetime(2026, 8, 15, 20, 10, tzinfo=timezone.utc),
    )
    assert report["status"] == "passed"
    assert report["conversation_ids"] == ["conv-low", "conv-high", "conv-damaged"]


def test_initialize_and_finalize_hashes_required_gate_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_dir = initialized_release(tmp_path, monkeypatch)
    write_gate_files(release_dir, all_artifacts())
    write_success_timings(tmp_path)

    record = finalize_release(tmp_path, "release-1", "succeeded")

    assert record["status"] == "succeeded"
    assert all(gate["status"] == "succeeded" for gate in record["gates"].values())
    assert {item["path"] for item in record["artifacts"]} == {
        relative_path for relative_path, _ in REQUIRED_GATES.values()
    }
    assert all(len(item["sha256"]) == 64 for item in record["artifacts"])


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda values: values["hosted_smoke"].update(release_id="other"), "another release"),
        (
            lambda values: values["hosted_smoke"].update(generated_at="2026-08-15T19:59:59Z"),
            "predates",
        ),
        (
            lambda values: values["hosted_smoke"].update(token="not-safe"),
            "Secret-bearing",
        ),
    ],
)
def test_finalize_rejects_cross_release_stale_and_secret_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: object,
    message: str,
) -> None:
    release_dir = initialized_release(tmp_path, monkeypatch)
    artifacts = all_artifacts()
    mutation(artifacts)  # type: ignore[operator]
    write_gate_files(release_dir, artifacts)
    write_success_timings(tmp_path)

    with pytest.raises(ValueError, match=message):
        finalize_release(tmp_path, "release-1", "succeeded")


def test_inventory_rejects_artifact_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_dir = initialized_release(tmp_path, monkeypatch)
    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    (release_dir / "evidence" / "unsafe.json").symlink_to(outside)

    with pytest.raises(ValueError, match="symlink"):
        artifact_inventory(release_dir)


def test_safe_artifact_path_rejects_absolute_and_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_dir = initialized_release(tmp_path, monkeypatch)
    for unsafe in ("/absolute.json", "evidence/../release.json", "../other/evidence.json"):
        with pytest.raises(ValueError, match="absolute or traverses"):
            safe_artifact_path(release_dir, unsafe, must_exist=False)


def test_initialize_rejects_symlinked_artifact_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = tmp_path / "foundry-public.env"
    write_profile(profile)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".artifacts").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="parents may not be symlinks"):
        initialize_release(
            tmp_path,
            "release-1",
            "2026-08-15T20:00:00Z",
            profile,
        )


def test_finalize_rejects_duplicate_declared_artifact_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_dir = initialized_release(tmp_path, monkeypatch)
    record_path = release_dir / "release.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    duplicate = {
        "path": "evidence/duplicate.json",
        "sha256": "0" * 64,
        "size_bytes": 0,
    }
    record["artifacts"] = [duplicate, duplicate]
    record_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate artifact"):
        finalize_release(tmp_path, "release-1", "failed", failed_stage="test", error="failed")


def test_timing_preserves_parallel_overlap_and_exact_durations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_dir = initialized_release(tmp_path, monkeypatch)
    write_success_timings(tmp_path)
    record = json.loads((release_dir / "release.json").read_text(encoding="utf-8"))

    validate_release_timing(record)

    stages = record["extensions"]["release_timing"]["stages"]
    assert stages["hosted_e2e"]["started_at"] < stages["evaluation"]["started_at"]
    assert stages["evaluation"]["started_at"] < stages["hosted_e2e"]["ended_at"]
    assert stages["package_build"]["duration_ms"] == 60_000
    assert record["extensions"]["release_timing"]["total"]["duration_ms"] == 540_000


def test_failed_finalize_closes_running_stage_and_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialized_release(tmp_path, monkeypatch)
    record_stage_timing(
        tmp_path,
        "release-1",
        "app_only",
        "start",
        timestamp="2026-08-15T20:01:00Z",
    )
    record_stage_timing(
        tmp_path,
        "release-1",
        "package_build",
        "start",
        timestamp="2026-08-15T20:01:01Z",
    )

    record = finalize_release(
        tmp_path,
        "release-1",
        "failed",
        failed_stage="package_build",
        error="Package command failed.",
    )

    timing = record["extensions"]["release_timing"]
    assert timing["stages"]["package_build"]["status"] == "failed"
    assert timing["stages"]["app_only"]["status"] == "failed"
    assert timing["total"]["status"] == "failed"
    assert timing["total"]["failed_stage"] == "package_build"


def test_resume_failed_release_resets_selected_and_downstream_timing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized_release(tmp_path, monkeypatch)
    write_success_timings(tmp_path)
    finalize_release(
        tmp_path,
        "release-1",
        "failed",
        failed_stage="verification",
        error="transient failure",
    )

    record = resume_release(
        tmp_path,
        "release-1",
        "verification",
        timestamp="2026-08-15T20:10:00Z",
    )

    stages = record["extensions"]["release_timing"]["stages"]
    assert record["status"] == "running"
    assert record["completed_at"] is None
    assert stages["app_only"]["status"] == "running"
    assert "hosted_deployment_activation" in stages
    assert "verification" not in stages
    assert "telemetry" not in stages


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda timing: timing["stages"].pop("telemetry"),
            "stages are missing",
        ),
        (
            lambda timing: timing["stages"]["verification"].update(
                started_at="2026-08-15T20:05:00Z",
                duration_ms=120_500,
            ),
            "order is invalid",
        ),
        (
            lambda timing: timing["stages"]["smoke"].update(duration_ms=1),
            "duration is invalid",
        ),
        (
            lambda timing: timing["total"].update(duration_ms=1),
            "total is invalid",
        ),
    ],
)
def test_succeeded_finalize_rejects_invalid_timing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: object,
    message: str,
) -> None:
    release_dir = initialized_release(tmp_path, monkeypatch)
    write_gate_files(release_dir, all_artifacts())
    write_success_timings(tmp_path)
    record_path = release_dir / "release.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    mutation(record["extensions"]["release_timing"])  # type: ignore[operator]
    record_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        finalize_release(tmp_path, "release-1", "succeeded")


@pytest.mark.parametrize(
    "payload",
    [
        {"database_url": "redacted"},
        {"connection_string": "InstrumentationKey=not-safe"},
        {"nested": [{"token": "not-safe"}]},
        {"value": "postgresql://user:password@example.invalid/db"},
    ],
)
def test_secret_free_guard_rejects_secret_bearing_evidence(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="Secret-bearing"):
        assert_secret_free(payload)


def test_migration_is_dry_run_and_requires_both_deletion_markers(tmp_path: Path) -> None:
    legacy = tmp_path / "deployment-report"
    legacy.mkdir()
    candidate = legacy / "report.json"
    candidate.write_text("{}\n", encoding="utf-8")
    singular = tmp_path / ".artifacts" / "release"
    singular.mkdir(parents=True)
    singular_candidate = singular / "release.json"
    singular_candidate.write_text("{}\n", encoding="utf-8")

    plan = migration_plan(tmp_path)

    assert plan["mode"] == "dry_run"
    assert plan["sources_unchanged"] is True
    assert plan["deletion_eligible"] is False
    assert candidate.exists()
    assert singular_candidate.exists()

    markers = tmp_path / ".artifacts" / "releases"
    markers.mkdir(parents=True)
    (markers / ".live-release-validated").write_text("validated\n", encoding="utf-8")
    (markers / ".durable-archive-confirmed").write_text("archived\n", encoding="utf-8")
    assert migration_plan(tmp_path)["deletion_eligible"] is True
