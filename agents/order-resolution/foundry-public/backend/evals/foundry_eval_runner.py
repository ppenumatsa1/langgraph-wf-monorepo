from __future__ import annotations

import asyncio
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml
from app.langgraph.clients import get_foundry_models_config
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential


def _read_eval_config(path: Path) -> dict[str, object]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("backend/eval.yaml must be a mapping")
    return config


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _to_jsonable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump())
    if hasattr(value, "dict"):
        return _to_jsonable(value.dict())
    return str(value)


def _parse_evidence_timestamp(payload: dict[str, object], field: str) -> datetime:
    value = payload.get(field)
    if not isinstance(value, str):
        raise ValueError(f"Hosted E2E evidence is missing {field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Hosted E2E evidence {field} must be ISO 8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"Hosted E2E evidence {field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _load_hosted_e2e_evidence(
    path: Path,
) -> tuple[datetime, datetime, list[str], str]:
    if not path.is_file():
        raise FileNotFoundError(f"Hosted E2E evidence is required: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Hosted E2E evidence must be a JSON object")
    started_at = _parse_evidence_timestamp(payload, "started_at")
    generated_at = _parse_evidence_timestamp(payload, "generated_at")
    if generated_at < started_at:
        raise ValueError("Hosted E2E evidence generated_at cannot precede started_at")
    release_id = payload.get("release_id")
    if not isinstance(release_id, str) or not release_id:
        raise ValueError("Hosted E2E evidence is missing release_id")

    evidence_ids = payload.get("conversation_ids")
    conversation_ids = _dedupe(
        [
            value
            for value in (
                evidence_ids
                if isinstance(evidence_ids, list)
                else [
                    payload.get("low_risk_thread_id"),
                    payload.get("approved_thread_id"),
                    payload.get("damaged_item_thread_id"),
                ]
            )
            if isinstance(value, str) and value.strip()
        ]
    )
    if len(conversation_ids) != 3:
        raise ValueError("Hosted E2E evidence must contain three conversation IDs")
    return started_at, generated_at, conversation_ids, release_id


def _trace_materialization_delay(
    generated_at: datetime,
    minimum_age_seconds: float,
    *,
    now: datetime | None = None,
) -> float:
    if not math.isfinite(minimum_age_seconds) or minimum_age_seconds < 0:
        raise ValueError("Foundry trace evaluation minimum age must be a finite non-negative value")
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        raise ValueError("Current time used for trace evaluation must include a timezone")
    age_seconds = (current_time.astimezone(timezone.utc) - generated_at).total_seconds()
    return max(0.0, minimum_age_seconds - age_seconds)


def _build_conversation_trace_testing_criteria(
    evaluators: list[str],
    judge_model: str,
) -> list[dict[str, object]]:
    criteria: list[dict[str, object]] = []
    for evaluator_name in evaluators:
        criteria.append(
            {
                "type": "azure_ai_evaluator",
                "name": evaluator_name,
                "evaluator_name": f"builtin.{evaluator_name}",
                "initialization_parameters": {"model": judge_model},
                "data_mapping": {"messages": "{{item.messages}}"},
            }
        )
    return criteria


def _evidence_path(root: Path, configured: str) -> Path:
    return Path(os.getenv("HOSTED_E2E_EVIDENCE_FILE", root / configured))


def _assert_eval_passed(payload: dict[str, object]) -> None:
    if str(payload.get("status")) != "completed":
        raise RuntimeError(f"Foundry trace eval run ended with status: {payload.get('status')}")
    result_counts = payload.get("result_counts")
    if not isinstance(result_counts, dict):
        raise RuntimeError("Foundry trace eval completed without result counts")
    errored = int(result_counts.get("errored", 0))
    failed = int(result_counts.get("failed", 0))
    passed = int(result_counts.get("passed", 0))
    total = int(result_counts.get("total", 0))
    if errored or failed or total < 1 or passed < 1:
        raise RuntimeError(
            "Foundry trace eval did not pass: "
            f"passed={passed}, failed={failed}, errored={errored}, total={total}"
        )


async def run_foundry_eval() -> None:
    root = Path(__file__).resolve().parents[1]
    foundry_root = root / ".foundry"
    config = _read_eval_config(root / "eval.yaml")
    foundry_cfg = config.get("foundry")
    if not isinstance(foundry_cfg, dict):
        raise ValueError("backend/eval.yaml is missing foundry config block")
    trace_cfg = foundry_cfg.get("trace_evaluation")
    if not isinstance(trace_cfg, dict):
        raise ValueError("backend/eval.yaml is missing foundry.trace_evaluation")
    evidence_uri = trace_cfg.get("evidence_file")
    if not isinstance(evidence_uri, str) or not evidence_uri:
        raise ValueError("backend/eval.yaml trace_evaluation.evidence_file is required")
    max_traces = int(trace_cfg.get("max_traces", 10))
    if max_traces < 1:
        raise ValueError("backend/eval.yaml trace_evaluation.max_traces must be positive")
    minimum_trace_age_seconds = float(
        os.getenv(
            "FOUNDRY_EVAL_MIN_TRACE_AGE_SECONDS",
            trace_cfg.get("minimum_trace_age_seconds", 90),
        )
    )

    evaluator_values = foundry_cfg.get("evaluators")
    if not isinstance(evaluator_values, list) or not all(
        isinstance(value, str) and value for value in evaluator_values
    ):
        raise ValueError("backend/eval.yaml foundry.evaluators must be a list of evaluator names")
    evaluators = _dedupe([str(value) for value in evaluator_values])
    eval_name = str(foundry_cfg.get("name", "order-resolution-foundry-report"))
    poll_interval = float(
        os.getenv("FOUNDRY_EVAL_POLL_INTERVAL", foundry_cfg.get("poll_interval", 5))
    )
    timeout = float(os.getenv("FOUNDRY_EVAL_TIMEOUT", foundry_cfg.get("timeout", 900)))

    evidence_path = _evidence_path(root, evidence_uri)
    started_at, generated_at, conversation_ids, release_id = _load_hosted_e2e_evidence(
        evidence_path
    )
    requested_release_id = os.getenv("FOUNDRY_RELEASE_ID")
    if requested_release_id and requested_release_id != release_id:
        raise ValueError("Hosted E2E evidence does not belong to the active release window")
    trace_materialization_delay = _trace_materialization_delay(
        generated_at,
        minimum_trace_age_seconds,
    )
    report_path = Path(
        os.getenv("FOUNDRY_EVAL_EVIDENCE_FILE", foundry_root / "results" / "foundry-report.json")
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "status": "failed",
        "provider": "foundry-trace",
        "release_id": release_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluators": evaluators,
        "conversation_ids": conversation_ids,
        "e2e_started_at": started_at.isoformat(),
        "e2e_generated_at": generated_at.isoformat(),
        "trace_materialization_delay_seconds": trace_materialization_delay,
    }

    try:
        if trace_materialization_delay:
            await asyncio.sleep(trace_materialization_delay)
        models_cfg = get_foundry_models_config()
        if models_cfg is None:
            raise RuntimeError(
                "Foundry model configuration is missing. Set FOUNDRY_PROJECTS_ENDPOINT and "
                "FOUNDRY_MODEL_DEPLOYMENT_NAME."
            )
        judge_model = os.getenv("FOUNDRY_EVAL_MODEL", models_cfg.model)
        credential = DefaultAzureCredential()
        project_client = AIProjectClient(
            endpoint=models_cfg.project_endpoint, credential=credential
        )
        openai_client = project_client.get_openai_client()
        eval_object = await openai_client.evals.create(
            name=f"{eval_name}-trace",
            data_source_config={"type": "azure_ai_source", "scenario": "traces"},
            testing_criteria=_build_conversation_trace_testing_criteria(evaluators, judge_model),
        )
        eval_run = await openai_client.evals.runs.create(
            eval_id=eval_object.id,
            name=f"{eval_name} trace run",
            metadata={
                "e2e_started_at": started_at.isoformat(),
                "conversation_count": str(len(conversation_ids)),
            },
            data_source={
                "type": "azure_ai_trace_data_source_preview",
                "trace_source": {
                    "type": "conversation_id_source",
                    "conversation_ids": conversation_ids[:max_traces],
                },
            },
            extra_body={"evaluation_level": "conversation"},
        )
        start = asyncio.get_running_loop().time()
        while str(eval_run.status) not in {"completed", "failed", "cancelled"}:
            if asyncio.get_running_loop().time() - start > timeout:
                raise TimeoutError(f"Foundry trace evaluation timed out after {timeout} seconds")
            await asyncio.sleep(poll_interval)
            eval_run = await openai_client.evals.runs.retrieve(
                run_id=eval_run.id,
                eval_id=eval_object.id,
            )
        payload = {
            "status": str(eval_run.status),
            "provider": "foundry-trace",
            "release_id": release_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "eval_id": eval_object.id,
            "run_id": eval_run.id,
            "conversation_count": len(conversation_ids),
            "evaluators": evaluators,
            "conversation_ids": conversation_ids,
            "e2e_started_at": started_at.isoformat(),
            "e2e_generated_at": generated_at.isoformat(),
            "trace_materialization_delay_seconds": trace_materialization_delay,
            "result_counts": _to_jsonable(getattr(eval_run, "result_counts", None)),
            "report_url": (
                f"{models_cfg.project_endpoint.rstrip('/')}/evaluation/evaluations/{eval_object.id}/runs/{eval_run.id}"
            ),
            "error": _to_jsonable(getattr(eval_run, "error", None)),
        }
    except Exception as exc:  # noqa: BLE001
        payload["status"] = "timeout" if isinstance(exc, TimeoutError) else "failed"
        payload["error"] = str(exc)
        if "eval_object" in locals():
            payload["eval_id"] = getattr(eval_object, "id", None)
        if "eval_run" in locals():
            payload["run_id"] = getattr(eval_run, "id", None)
            payload["run_status"] = str(getattr(eval_run, "status", "unknown"))
        if payload.get("eval_id") and payload.get("run_id") and "models_cfg" in locals():
            payload["report_url"] = (
                f"{models_cfg.project_endpoint.rstrip('/')}/evaluation/evaluations/"
                f"{payload['eval_id']}/runs/{payload['run_id']}"
            )
    finally:
        if "openai_client" in locals():
            await openai_client.close()
        if "project_client" in locals():
            await project_client.close()
        if "credential" in locals():
            await credential.close()

    report_path.write_text(json.dumps(_to_jsonable(payload), indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"Foundry report saved to: {report_path}")

    enforce_pass = os.getenv("FOUNDRY_EVAL_ENFORCE_PASS", "true").lower() in {"1", "true", "yes"}
    if enforce_pass:
        _assert_eval_passed(payload)


if __name__ == "__main__":
    asyncio.run(run_foundry_eval())
