from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from release_record import (
    atomic_json_write,
    configured_sensitive_values,
    finalize_record,
    finish_release_timing,
    register_artifact,
    validate_secret_free,
)

ROOT = Path(__file__).resolve().parents[2]
release_id = os.getenv("RELEASE_ID", "").strip()
DEFAULT_RESULTS = (
    ROOT / ".artifacts" / "releases" / release_id / "evidence"
    if release_id
    else ROOT / "backend" / ".foundry" / "results"
)
RESULTS = Path(os.getenv("FOUNDRY_RELEASE_EVIDENCE_DIR", DEFAULT_RESULTS))
OUTPUT = Path(os.getenv("FOUNDRY_RELEASE_EVIDENCE_FILE", RESULTS / "release-evidence.json"))
SOURCES = {
    "verification": RESULTS / "foundry-verify.json",
    "postgres_readiness": RESULTS / "postgres-readiness-evidence.json",
    "model_preflight": RESULTS / "model-preflight-evidence.json",
    "hosted_e2e": RESULTS / "hosted-e2e-evidence.json",
    "hosted_smoke": RESULTS / "hosted-smoke-evidence.json",
    "trace_evaluation": RESULTS / "foundry-trace-eval.json",
    "application_insights": RESULTS / "appinsights-evidence.json",
}
TARGET = {
    "subscription_id": "7df95e88-701c-4693-af77-3159f83b558d",
    "resource_group": "rg-langgraph-uw-foundry-public",
    "location": "eastus2",
}


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def validate_evidence(documents: dict[str, Any]) -> None:
    verification = documents["verification"]
    require(verification.get("target") == TARGET, "Verification target is not canonical.")
    topology = verification.get("topology", {})
    require(
        topology.get("frontend_external") is True
        and topology.get("backend_internal") is True
        and topology.get("same_origin_health") is True
        and topology.get("same_origin_api") is True
        and topology.get("direct_backend_publicly_reachable") is False,
        "Verification topology checks did not pass.",
    )
    hosted_agent = verification.get("hosted_agent", {})
    require(
        hosted_agent.get("status") == "active"
        and hosted_agent.get("database_url_placeholder") is True
        and hosted_agent.get("runtime_database_url_placeholder") is True
        and hosted_agent.get("database_url_parity") is True
        and hosted_agent.get("application_insights_configured") is True,
        "Hosted-agent verification checks did not pass.",
    )
    runtime_database = verification.get("runtime_database", {})
    require(
        runtime_database.get("url_parity") is True
        and runtime_database.get("required_schema_ready") is True
        and runtime_database.get("schema_managed_externally") is True,
        "Runtime database verification checks did not pass.",
    )

    postgres = documents["postgres_readiness"]
    postgres_target = postgres.get("target", {})
    require(
        postgres.get("evidence_type") == "postgres_readiness"
        and postgres_target.get("subscription_id") == TARGET["subscription_id"]
        and postgres_target.get("resource_group") == TARGET["resource_group"]
        and all(value is True for value in postgres.get("checks", {}).values())
        and len(postgres.get("checks", {})) == 7,
        "PostgreSQL readiness evidence did not pass.",
    )

    model = documents["model_preflight"]
    require(
        model.get("evidence_type") == "model_preflight"
        and model.get("status") == "passed"
        and model.get("mutation_performed") is False
        and model.get("target", {}).get("subscription_id") == TARGET["subscription_id"]
        and model.get("target", {}).get("resource_group") == TARGET["resource_group"]
        and str(model.get("target", {}).get("location", "")).lower() == TARGET["location"],
        "Model preflight evidence did not pass.",
    )
    if release_id:
        require(model.get("release_id") == release_id, "Model preflight release ID is stale.")

    hosted_e2e = documents["hosted_e2e"]
    workflow_run_ids = hosted_e2e.get("workflow_run_ids", [])
    require(
        isinstance(workflow_run_ids, list)
        and len(workflow_run_ids) == 3
        and all(isinstance(value, str) and value for value in workflow_run_ids)
        and hosted_e2e.get("playwright_status") == "passed"
        and hosted_e2e.get("backend_ingress_external") is False
        and hosted_e2e.get("resource_group") == TARGET["resource_group"],
        "Hosted E2E evidence did not pass.",
    )

    smoke = documents["hosted_smoke"]
    conversation_ids = smoke.get("conversation_ids", [])
    require(
        smoke.get("mode") in {"happy", "retry", "crash-resume"}
        and isinstance(conversation_ids, list)
        and len(conversation_ids) == 1
        and isinstance(conversation_ids[0], str)
        and bool(conversation_ids[0])
        and isinstance(smoke.get("workflow_run_id"), str)
        and bool(smoke["workflow_run_id"])
        and isinstance(smoke.get("decision"), str)
        and bool(smoke["decision"]),
        "Hosted smoke evidence did not pass.",
    )

    evaluation = documents["trace_evaluation"]
    counts = evaluation.get("result_counts", {})
    total = counts.get("total")
    require(
        evaluation.get("status") == "completed"
        and evaluation.get("conversation_ids") == conversation_ids
        and isinstance(total, int)
        and total == len(conversation_ids)
        and counts.get("passed") == total
        and counts.get("failed") == 0
        and counts.get("errored") == 0
        and counts.get("skipped") == 0,
        "Trace evaluation evidence did not pass.",
    )

    telemetry = documents["application_insights"]
    require(
        telemetry.get("resource_group") == TARGET["resource_group"]
        and telemetry.get("workflow_run_ids") == workflow_run_ids
        and telemetry.get("matched_count") == len(workflow_run_ids)
        and telemetry.get("request_run_count") == len(workflow_run_ids)
        and telemetry.get("hosted_invocation_run_count") == len(workflow_run_ids)
        and telemetry.get("workflow_span_run_count") == len(workflow_run_ids)
        and isinstance(telemetry.get("telemetry_rows"), int)
        and telemetry["telemetry_rows"] > 0
        and telemetry.get("exception_rows") == 0,
        "Application Insights evidence did not pass.",
    )


def main() -> None:
    documents: dict[str, Any] = {}
    timestamps: list[datetime] = []
    sensitive_values = configured_sensitive_values()
    for name, path in SOURCES.items():
        if not path.is_file():
            raise RuntimeError(f"Missing release evidence: {path}")
        document = json.loads(path.read_text())
        validate_secret_free(document, sensitive_values=sensitive_values)
        timestamp = document.get("generated_at") or document.get("started_at")
        if isinstance(timestamp, str) and timestamp:
            timestamps.append(parse_timestamp(timestamp))
        else:
            timestamps.append(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))
        documents[name] = document
    validate_evidence(documents)

    configured_start = os.getenv("RELEASE_WINDOW_START", "").strip()
    window_start = parse_timestamp(configured_start) if configured_start else min(timestamps)
    if any(timestamp < window_start for timestamp in timestamps):
        raise RuntimeError("One or more evidence files predate RELEASE_WINDOW_START.")

    payload = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release_window": {
            "start": window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "target": {
            **TARGET,
        },
        "evidence": documents,
    }
    validate_secret_free(payload, sensitive_values=sensitive_values)
    atomic_json_write(OUTPUT, payload)
    if release_id:
        gates = {
            "verification": "foundry-verify.json",
            "postgres_readiness": "postgres-readiness-evidence.json",
            "model_preflight": "model-preflight-evidence.json",
            "hosted_e2e": "hosted-e2e-evidence.json",
            "hosted_smoke": "hosted-smoke-evidence.json",
            "trace_evaluation": "foundry-trace-eval.json",
            "application_insights": "appinsights-evidence.json",
        }
        for gate, filename in gates.items():
            register_artifact(release_id, f"evidence/{filename}", gate)
        register_artifact(release_id, f"evidence/{OUTPUT.name}")
        finish_release_timing(release_id, "final_evidence", "succeeded")
        finalize_record(release_id, "succeeded")
    print(f"Release-window evidence written to {OUTPUT}.")


if __name__ == "__main__":
    main()
