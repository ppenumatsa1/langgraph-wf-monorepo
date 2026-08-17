from __future__ import annotations

import json
import multiprocessing
import shutil
from pathlib import Path
from uuid import uuid4

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
