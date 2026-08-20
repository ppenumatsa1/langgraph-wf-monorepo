from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from scripts.foundry import release_evidence

ROOT = Path(__file__).resolve().parents[3]
PROFILE_GATE_PATH = ROOT / "scripts" / "foundry-private" / "profile_gate.py"
spec = importlib.util.spec_from_file_location("private_profile_gate", PROFILE_GATE_PATH)
assert spec and spec.loader
private_profile_gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(private_profile_gate)


def profile_text(**overrides: str) -> str:
    values = {
        "CONTRACT_VERSION": "2",
        "DEPLOYMENT_LANE": "foundry-private",
        "AZURE_ENV_NAME": "order-resolution-foundry-private",
        "AZURE_SUBSCRIPTION_ID": "7df95e88-701c-4693-af77-3159f83b558d",
        "AZURE_RESOURCE_GROUP": "rg-langgraph-ora-foundry-private",
        "AZURE_LOCATION": "eastus2",
        "NAME_PREFIX": "orderprivate",
    }
    values.update(overrides)
    return "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"


def test_private_profile_gate_rejects_public_lane(tmp_path: Path) -> None:
    profile = tmp_path / "private.env"
    profile.write_text(profile_text(), encoding="utf-8")
    values = private_profile_gate.parse_profile(profile)
    assert values["DEPLOYMENT_LANE"] == "foundry-private"

    profile.write_text(profile_text(DEPLOYMENT_LANE="foundry-public"), encoding="utf-8")
    with pytest.raises(ValueError, match="DEPLOYMENT_LANE"):
        private_profile_gate.parse_profile(profile)


def test_private_profile_gate_rejects_public_network_bootstrap_values(tmp_path: Path) -> None:
    profile = tmp_path / "private.env"
    profile.write_text(
        profile_text() + "POSTGRES_OPERATOR_IP=203.0.113.10\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsupported key"):
        private_profile_gate.parse_profile(profile)


def test_private_release_evidence_requires_private_profile_lane(tmp_path: Path) -> None:
    profile = tmp_path / "private.env"
    profile.write_text(profile_text(), encoding="utf-8")
    release_evidence.initialize_release(
        tmp_path,
        "private-release-1",
        "2026-08-20T12:00:00Z",
        profile,
    )
    record = json.loads(
        (tmp_path / ".artifacts" / "releases" / "private-release-1" / "release.json").read_text(
            encoding="utf-8"
        )
    )
    assert record["lane"] == "order-resolution-foundry-private"
    assert "browser_e2e" in record["gates"]
    assert "release_gates" in record["gates"]
    assert "runner_bootstrap" in release_evidence.TIMING_STAGES

    profile.write_text(profile_text(DEPLOYMENT_LANE="foundry-public"), encoding="utf-8")
    with pytest.raises(ValueError, match="DEPLOYMENT_LANE"):
        release_evidence.initialize_release(
            tmp_path,
            "private-release-2",
            "2026-08-20T12:00:00Z",
            profile,
        )
