from __future__ import annotations

import json
import multiprocessing
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from scripts.azure import release_evidence


def _record_stage(release_id: str, stage: str) -> None:
    release_evidence.timing(release_id, stage, "start", None)


def test_concurrent_stage_updates_are_not_lost(monkeypatch) -> None:
    lane_root = Path(__file__).resolve().parents[3]
    scratch_root = lane_root / "backend" / ".tmp" / f"release-evidence-{uuid4()}"
    release_id = "concurrency-regression"
    monkeypatch.setattr(release_evidence, "root", lambda: scratch_root)
    try:
        release_evidence.init(release_id, "azure-hosted.env")
        context = multiprocessing.get_context("fork")
        processes = [
            context.Process(target=_record_stage, args=(release_id, f"stage-{index}"))
            for index in range(16)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=10)
            assert process.exitcode == 0

        payload = json.loads(
            (release_evidence.release_dir(release_id) / "release.json").read_text(
                encoding="utf-8"
            )
        )
        assert set(payload["stages"]) == {f"stage-{index}" for index in range(16)}
        assert not list(
            release_evidence.release_dir(release_id).glob(".release.json.*.new")
        )
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)


def test_report_only_evaluation_must_complete_without_execution_errors(
    monkeypatch,
) -> None:
    lane_root = Path(__file__).resolve().parents[3]
    scratch_root = lane_root / "backend" / ".tmp" / f"release-evidence-{uuid4()}"
    release_id = "report-only-evaluation"
    monkeypatch.setattr(release_evidence, "root", lambda: scratch_root)
    try:
        release_evidence.init(release_id, "azure-hosted.env")
        evidence_dir = release_evidence.release_dir(release_id) / "evidence"
        for name in (
            "model-preflight.json",
            "images.json",
            "deployment.json",
            "verification.json",
            "smoke.json",
            "domain-e2e.json",
            "browser-e2e.json",
            "telemetry.json",
        ):
            (evidence_dir / name).write_text('{"status":"passed"}', encoding="utf-8")
        (evidence_dir / "evaluation.json").write_text(
            '{"status":"completed","report_only":true,'
            '"result_counts":{"errored":1,"failed":0,"passed":0,"total":1}}',
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="evaluation.json"):
            release_evidence.aggregate(release_id)
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)
