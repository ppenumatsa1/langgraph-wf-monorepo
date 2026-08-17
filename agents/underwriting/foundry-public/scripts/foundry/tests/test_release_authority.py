from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts" / "foundry"
sys.path.insert(0, str(SCRIPTS))

from release_record import (  # noqa: E402
    finalize_record,
    finish_release_timing,
    initialize_record,
    register_artifact,
    resume_record,
    start_release_timing,
    utc_now,
    validate_succeeded_timing,
)


class ReleaseRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch_root = ROOT / "backend" / ".tmp"
        scratch_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch_root, prefix="release-authority-")
        self.scratch = Path(self.temporary.name)
        self.releases = self.scratch / "releases"
        self.profile = self.scratch / "profile.env"
        self.profile.write_text("CONTRACT_VERSION=1\n", encoding="utf-8")
        initialize_record(
            release_id="test-release-001",
            repository="https://example.invalid/repository",
            commit="abcdef1",
            profile=self.profile,
            environment="test",
            subscription_id="00000000-0000-0000-0000-000000000001",
            resource_group="test-rg",
            location="eastus2",
            executor="unit-test",
            required_gates=["verification"],
            releases_root=self.releases,
        )
        self.release_dir = self.releases / "test-release-001"
        record_path = self.release_dir / "release.json"
        record = json.loads(record_path.read_text())
        record["started_at"] = "2026-08-15T19:00:00.000Z"
        record["updated_at"] = record["started_at"]
        record_path.write_text(json.dumps(record), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_evidence(self, name: str, payload: dict[str, object]) -> Path:
        path = self.release_dir / "evidence" / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def record_successful_timing(self) -> None:
        self.record_timing_intervals(
            (
                ("package_build", "2026-08-15T20:00:00.000Z", "2026-08-15T20:00:10.000Z"),
                ("image_build", "2026-08-15T20:00:10.000Z", "2026-08-15T20:00:25.000Z"),
                ("hosted_activation", "2026-08-15T20:00:25.000Z", "2026-08-15T20:00:35.000Z"),
                ("aca_deployment", "2026-08-15T20:00:35.000Z", "2026-08-15T20:00:50.000Z"),
                ("smoke", "2026-08-15T20:00:50.000Z", "2026-08-15T20:01:00.000Z"),
                ("deployed_e2e", "2026-08-15T20:01:00.000Z", "2026-08-15T20:01:30.000Z"),
                ("evaluation", "2026-08-15T20:01:00.000Z", "2026-08-15T20:01:40.000Z"),
                ("telemetry", "2026-08-15T20:01:30.000Z", "2026-08-15T20:01:50.000Z"),
                (
                    "deployment_verification",
                    "2026-08-15T20:01:50.000Z",
                    "2026-08-15T20:02:00.000Z",
                ),
                ("final_evidence", "2026-08-15T20:02:00.000Z", "2026-08-15T20:02:10.000Z"),
            )
        )

    def record_timing_intervals(self, intervals: tuple[tuple[str, str, str], ...]) -> None:
        for index, (stage, started_at, ended_at) in enumerate(intervals):
            start_release_timing(
                "test-release-001",
                stage,
                start_app_only=index == 0,
                at=started_at,
                releases_root=self.releases,
            )
            finish_release_timing(
                "test-release-001",
                stage,
                "succeeded",
                at=ended_at,
                releases_root=self.releases,
            )

    def test_accepts_sub_15_minute_deployment_and_sub_30_minute_lifecycle(self) -> None:
        self.record_timing_intervals(
            (
                ("package_build", "2026-08-15T20:00:00.000Z", "2026-08-15T20:00:01.000Z"),
                ("image_build", "2026-08-15T20:00:01.000Z", "2026-08-15T20:05:00.000Z"),
                (
                    "hosted_activation",
                    "2026-08-15T20:05:00.000Z",
                    "2026-08-15T20:08:00.000Z",
                ),
                ("aca_deployment", "2026-08-15T20:08:00.000Z", "2026-08-15T20:12:40.000Z"),
                ("smoke", "2026-08-15T20:12:40.000Z", "2026-08-15T20:15:00.000Z"),
                ("deployed_e2e", "2026-08-15T20:15:00.000Z", "2026-08-15T20:24:00.000Z"),
                ("evaluation", "2026-08-15T20:15:00.000Z", "2026-08-15T20:17:00.000Z"),
                ("telemetry", "2026-08-15T20:24:00.000Z", "2026-08-15T20:27:00.000Z"),
                (
                    "deployment_verification",
                    "2026-08-15T20:27:00.000Z",
                    "2026-08-15T20:28:00.000Z",
                ),
                ("final_evidence", "2026-08-15T20:28:00.000Z", "2026-08-15T20:29:00.000Z"),
            )
        )

        record = json.loads((self.release_dir / "release.json").read_text())
        validate_succeeded_timing(record)

    def test_rejects_deployment_over_15_minutes(self) -> None:
        self.record_timing_intervals(
            (
                ("package_build", "2026-08-15T20:00:00.000Z", "2026-08-15T20:00:01.000Z"),
                ("image_build", "2026-08-15T20:00:01.000Z", "2026-08-15T20:07:00.000Z"),
                (
                    "hosted_activation",
                    "2026-08-15T20:07:00.000Z",
                    "2026-08-15T20:11:00.000Z",
                ),
                ("aca_deployment", "2026-08-15T20:11:00.000Z", "2026-08-15T20:15:01.000Z"),
                ("smoke", "2026-08-15T20:15:01.000Z", "2026-08-15T20:16:00.000Z"),
                ("deployed_e2e", "2026-08-15T20:16:00.000Z", "2026-08-15T20:20:00.000Z"),
                ("evaluation", "2026-08-15T20:16:00.000Z", "2026-08-15T20:18:00.000Z"),
                ("telemetry", "2026-08-15T20:20:00.000Z", "2026-08-15T20:22:00.000Z"),
                (
                    "deployment_verification",
                    "2026-08-15T20:22:00.000Z",
                    "2026-08-15T20:23:00.000Z",
                ),
                ("final_evidence", "2026-08-15T20:23:00.000Z", "2026-08-15T20:24:00.000Z"),
            )
        )

        record = json.loads((self.release_dir / "release.json").read_text())
        with self.assertRaisesRegex(ValueError, "15-minute deployment"):
            validate_succeeded_timing(record)

    def test_registers_evidence_and_finalizes_contract_record(self) -> None:
        self.write_evidence(
            "verification.json",
            {
                "release_id": "test-release-001",
                "generated_at": utc_now(),
                "database_url_placeholder": True,
            },
        )
        register_artifact(
            "test-release-001",
            "evidence/verification.json",
            "verification",
            self.releases,
        )
        self.record_successful_timing()
        finalize_record("test-release-001", "succeeded", releases_root=self.releases)
        record = json.loads((self.release_dir / "release.json").read_text())
        schema = json.loads(
            (ROOT / ".artifacts/releases/_contract/release-v1.schema.json").read_text()
        )
        jsonschema.Draft202012Validator(schema).validate(record)
        self.assertEqual(record["status"], "succeeded")
        self.assertEqual(record["gates"]["verification"]["status"], "succeeded")
        self.assertEqual(len(record["artifacts"][0]["sha256"]), 64)
        self.assertTrue((self.release_dir / "provenance-manifest.json").is_file())
        self.assertTrue((self.release_dir / "checksums.sha256").is_file())

    def test_records_duration_parallel_overlap_and_app_only_total(self) -> None:
        self.record_successful_timing()
        timing = json.loads((self.release_dir / "release.json").read_text())["extensions"][
            "release_timing"
        ]
        self.assertEqual(timing["stages"]["package_build"]["duration_ms"], 10_000)
        self.assertEqual(timing["stages"]["evaluation"]["duration_ms"], 40_000)
        self.assertEqual(timing["app_only_duration_ms"], 110_000)
        self.assertEqual(timing["app_only"]["duration_ms"], 110_000)
        self.assertEqual(timing["app_only"]["status"], "succeeded")
        self.assertEqual(
            timing["telemetry_succeeded_at"],
            timing["stages"]["telemetry"]["ended_at"],
        )
        self.assertLess(
            timing["stages"]["evaluation"]["started_at"],
            timing["stages"]["deployed_e2e"]["ended_at"],
        )
        self.assertGreater(
            timing["stages"]["evaluation"]["ended_at"],
            timing["stages"]["telemetry"]["started_at"],
        )

    def test_resumes_failed_release_from_selected_stage(self) -> None:
        self.record_successful_timing()
        finalize_record(
            "test-release-001",
            "failed",
            failed_stage="telemetry",
            error="transient failure",
            releases_root=self.releases,
        )

        resume_record(
            "test-release-001",
            "deployed_e2e",
            at="2026-08-15T20:02:00.000Z",
            releases_root=self.releases,
        )

        record = json.loads((self.release_dir / "release.json").read_text())
        timing = record["extensions"]["release_timing"]
        self.assertEqual(record["status"], "running")
        self.assertIsNone(record["completed_at"])
        self.assertEqual(timing["app_only"]["status"], "running")
        self.assertIn("smoke", timing["stages"])
        self.assertNotIn("deployed_e2e", timing["stages"])
        self.assertNotIn("telemetry", timing["stages"])

    def test_rejects_invalid_ordering(self) -> None:
        start_release_timing(
            "test-release-001",
            "package_build",
            start_app_only=True,
            at="2026-08-15T20:00:10.000Z",
            releases_root=self.releases,
        )
        with self.assertRaisesRegex(ValueError, "must not precede"):
            finish_release_timing(
                "test-release-001",
                "package_build",
                "succeeded",
                at="2026-08-15T20:00:09.999Z",
                releases_root=self.releases,
            )
        with self.assertRaisesRegex(ValueError, "prerequisite"):
            start_release_timing(
                "test-release-001",
                "image_build",
                at="2026-08-15T20:00:11.000Z",
                releases_root=self.releases,
            )

    def test_records_failed_stage_and_allows_failed_final_record(self) -> None:
        start_release_timing(
            "test-release-001",
            "package_build",
            start_app_only=True,
            at="2026-08-15T20:00:00.000Z",
            releases_root=self.releases,
        )
        finish_release_timing(
            "test-release-001",
            "package_build",
            "failed",
            at="2026-08-15T20:00:01.250Z",
            releases_root=self.releases,
        )
        finalize_record(
            "test-release-001",
            "failed",
            "package_build",
            "package failed",
            releases_root=self.releases,
        )
        record = json.loads((self.release_dir / "release.json").read_text())
        self.assertEqual(
            record["extensions"]["release_timing"]["stages"]["package_build"]["duration_ms"],
            1_250,
        )
        self.assertEqual(record["status"], "failed")

    def test_fails_closed_for_missing_required_gate(self) -> None:
        self.record_successful_timing()
        with self.assertRaisesRegex(ValueError, "Required gates"):
            finalize_record("test-release-001", "succeeded", releases_root=self.releases)

    def test_fails_closed_for_missing_timing_completion(self) -> None:
        self.write_evidence("verification.json", {"generated_at": utc_now()})
        register_artifact(
            "test-release-001",
            "evidence/verification.json",
            "verification",
            self.releases,
        )
        start_release_timing(
            "test-release-001",
            "package_build",
            start_app_only=True,
            at="2026-08-15T20:00:00.000Z",
            releases_root=self.releases,
        )
        with self.assertRaisesRegex(ValueError, "timing"):
            finalize_record("test-release-001", "succeeded", releases_root=self.releases)

    def test_rejects_unsafe_and_duplicate_paths(self) -> None:
        evidence = self.write_evidence("valid.json", {"generated_at": utc_now()})
        with self.assertRaisesRegex(ValueError, "Unsafe artifact path"):
            register_artifact("test-release-001", "../valid.json", releases_root=self.releases)
        with self.assertRaisesRegex(ValueError, "Unsafe artifact path"):
            register_artifact(
                "test-release-001", str(evidence.resolve()), releases_root=self.releases
            )
        register_artifact("test-release-001", "evidence/valid.json", releases_root=self.releases)
        with self.assertRaisesRegex(ValueError, "Duplicate artifact path"):
            register_artifact(
                "test-release-001", "evidence/valid.json", releases_root=self.releases
            )

    def test_rejects_escaping_symlink_cross_release_stale_and_secret_evidence(self) -> None:
        outside = self.scratch / "outside.json"
        outside.write_text(json.dumps({"generated_at": utc_now()}), encoding="utf-8")
        (self.release_dir / "evidence" / "escape.json").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "escapes"):
            register_artifact(
                "test-release-001", "evidence/escape.json", releases_root=self.releases
            )

        cases = {
            "cross.json": {
                "release_id": "other-release",
                "generated_at": utc_now(),
            },
            "stale.json": {"generated_at": "2000-01-01T00:00:00Z"},
            "secret.json": {"api_key": "not-allowed"},
        }
        expected = ("Cross-release", "Stale evidence", "Secret-like")
        for (name, payload), message in zip(cases.items(), expected, strict=True):
            self.write_evidence(name, payload)
            with self.assertRaisesRegex(ValueError, message):
                register_artifact(
                    "test-release-001",
                    f"evidence/{name}",
                    releases_root=self.releases,
                )


class HistoryMigrationTests(unittest.TestCase):
    def test_fixture_inventory_is_dry_run_with_hashes_and_destinations(self) -> None:
        fixture = ROOT / "scripts" / "foundry" / "tests" / "fixtures" / "release-history"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "migrate_release_history.py"),
                "--root",
                str(fixture),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "dry-run")
        self.assertEqual(len(payload["files"]), 2)
        for item in payload["files"]:
            self.assertEqual(len(item["sha256"]), 64)
            self.assertGreater(item["size_bytes"], 0)
            self.assertIn(".artifacts/releases/_history/legacy/", item["destination"])

    def test_execute_and_delete_are_interlocked_and_disabled(self) -> None:
        script = str(SCRIPTS / "migrate_release_history.py")
        delete = subprocess.run(
            [sys.executable, script, "--delete-source"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(delete.returncode, 0)
        self.assertIn("requires --execute", delete.stderr)
        execute = subprocess.run(
            [sys.executable, script, "--execute"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(execute.returncode, 0)
        self.assertIn("intentionally disabled", execute.stderr)


if __name__ == "__main__":
    unittest.main()
