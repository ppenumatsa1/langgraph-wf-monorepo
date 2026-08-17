from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


def _read_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("backend/eval.yaml must be a mapping")
    return config


def _load_evidence(path: Path) -> tuple[datetime, list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Hosted smoke evidence must be a JSON object")

    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str):
        raise ValueError("Hosted smoke evidence is missing generated_at")
    try:
        timestamp = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Hosted smoke evidence generated_at must be ISO 8601") from exc
    if timestamp.tzinfo is None:
        raise ValueError("Hosted smoke evidence generated_at must include a timezone")

    conversation_ids = payload.get("conversation_ids")
    if not isinstance(conversation_ids, list):
        raise ValueError("Hosted smoke evidence is missing conversation_ids")
    valid_ids = [value for value in conversation_ids if isinstance(value, str) and value.strip()]
    if not valid_ids:
        raise ValueError("Hosted smoke evidence must contain at least one conversation ID")
    return timestamp.astimezone(UTC), list(dict.fromkeys(valid_ids))


def _criteria(evaluators: list[str], model: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "azure_ai_evaluator",
            "name": evaluator,
            "evaluator_name": f"builtin.{evaluator}",
            "initialization_parameters": {"model": model},
            "data_mapping": {"messages": "{{item.messages}}"},
        }
        for evaluator in evaluators
    ]


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _result_counts(value: object) -> dict[str, int]:
    return {
        name: int(getattr(value, name, 0) or 0)
        for name in ("errored", "failed", "passed", "total", "skipped")
    }


def _evidence_path(root: Path, configured: str) -> Path:
    return Path(os.getenv("FOUNDRY_SMOKE_EVIDENCE_FILE", root / configured))


def run() -> None:
    root = Path(__file__).resolve().parents[1]
    config = _read_config(root / "eval.yaml")
    foundry = config.get("foundry")
    if not isinstance(foundry, dict):
        raise ValueError("backend/eval.yaml is missing the foundry configuration")
    trace_config = foundry.get("trace_evaluation")
    if not isinstance(trace_config, dict):
        raise ValueError("backend/eval.yaml is missing foundry.trace_evaluation")
    evidence_uri = trace_config.get("evidence_file")
    if not isinstance(evidence_uri, str) or not evidence_uri:
        raise ValueError("foundry.trace_evaluation.evidence_file is required")
    evidence_path = _evidence_path(root, evidence_uri)
    generated_at, conversation_ids = _load_evidence(evidence_path)

    minimum_age = float(trace_config.get("minimum_trace_age_seconds", 90))
    if minimum_age < 0:
        raise ValueError("minimum_trace_age_seconds must be non-negative")
    remaining_delay = minimum_age - (datetime.now(UTC) - generated_at).total_seconds()
    if remaining_delay > 0:
        time.sleep(remaining_delay)

    evaluators = foundry.get("evaluators")
    if not isinstance(evaluators, list) or not all(
        isinstance(item, str) and item for item in evaluators
    ):
        raise ValueError("foundry.evaluators must be a non-empty list of evaluator names")
    project_endpoint = _required_env("FOUNDRY_PROJECTS_ENDPOINT")
    judge_model = _required_env("FOUNDRY_MODEL_DEPLOYMENT_NAME")
    timeout = float(foundry.get("timeout", 900))
    poll_interval = float(foundry.get("poll_interval", 5))
    evaluation_name = str(foundry.get("name", "underwriting-foundry-trace"))

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
        project_client.get_openai_client() as openai_client,
    ):
        evaluation = openai_client.evals.create(
            name=evaluation_name,
            data_source_config={"type": "azure_ai_source", "scenario": "traces"},
            testing_criteria=_criteria(evaluators, judge_model),
        )
        evaluation_run = openai_client.evals.runs.create(
            eval_id=evaluation.id,
            name=f"{evaluation_name}-run",
            data_source={
                "type": "azure_ai_trace_data_source_preview",
                "trace_source": {
                    "type": "conversation_id_source",
                    "conversation_ids": conversation_ids,
                },
            },
            extra_body={"evaluation_level": "conversation"},
        )
        deadline = time.monotonic() + timeout
        while evaluation_run.status not in {"completed", "failed", "cancelled"}:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Foundry trace evaluation timed out after {timeout} seconds")
            time.sleep(poll_interval)
            evaluation_run = openai_client.evals.runs.retrieve(
                eval_id=evaluation.id,
                run_id=evaluation_run.id,
            )

    result_counts = _result_counts(getattr(evaluation_run, "result_counts", None))
    result = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trace_evidence_generated_at": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": str(evaluation_run.status),
        "eval_id": evaluation.id,
        "run_id": evaluation_run.id,
        "conversation_ids": conversation_ids,
        "result_counts": result_counts,
    }
    configured_output = os.getenv("FOUNDRY_TRACE_EVAL_OUTPUT_FILE", "").strip()
    output = (
        Path(configured_output)
        if configured_output
        else root / ".foundry" / "results" / "foundry-trace-eval.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))
    if evaluation_run.status != "completed":
        raise RuntimeError(f"Foundry trace evaluation ended with status: {evaluation_run.status}")
    if (
        result_counts["total"] != len(conversation_ids)
        or result_counts["passed"] != len(conversation_ids)
        or result_counts["failed"]
        or result_counts["errored"]
        or result_counts["skipped"]
    ):
        raise RuntimeError(f"Foundry trace evaluation did not pass: {result_counts}")


if __name__ == "__main__":
    run()
