from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from evals.foundry_eval_runner import (
    _assert_eval_passed,
    _build_conversation_trace_testing_criteria,
    _evidence_path,
    _load_domain_e2e_evidence,
    _trace_materialization_delay,
)


def test_assert_eval_passed_accepts_completed_passed_results() -> None:
    _assert_eval_passed(
        {
            "status": "completed",
            "result_counts": {
                "passed": 1,
                "failed": 0,
                "errored": 0,
                "total": 1,
            },
        }
    )


@pytest.mark.parametrize(
    "result_counts",
    [
        {"passed": 0, "failed": 0, "errored": 1, "total": 1},
        {"passed": 0, "failed": 1, "errored": 0, "total": 1},
        {"passed": 0, "failed": 0, "errored": 0, "total": 0},
    ],
)
def test_assert_eval_passed_rejects_non_passing_results(
    result_counts: dict[str, int],
) -> None:
    with pytest.raises(RuntimeError, match="did not pass"):
        _assert_eval_passed({"status": "completed", "result_counts": result_counts})


def test_evidence_path_prefers_current_release_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = tmp_path / "release-domain-e2e.json"
    monkeypatch.setenv("DOMAIN_E2E_EVIDENCE_FILE", str(current))

    assert _evidence_path(tmp_path, "tracked-sample.json") == current


def test_load_domain_e2e_evidence_requires_all_release_conversations(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "domain-e2e.json"
    evidence.write_text(
        json.dumps(
            {
                "started_at": "2026-07-20T13:58:00Z",
                "generated_at": "2026-07-20T14:00:00Z",
                "conversation_ids": ["conv-low", "conv-approved", "conv-damaged"],
            }
        ),
        encoding="utf-8",
    )

    started_at, generated_at, conversation_ids, release_id = _load_domain_e2e_evidence(evidence)

    assert started_at == datetime(2026, 7, 20, 13, 58, tzinfo=timezone.utc)
    assert generated_at == datetime(2026, 7, 20, 14, 0, tzinfo=timezone.utc)
    assert conversation_ids == ["conv-low", "conv-approved", "conv-damaged"]
    assert release_id == "manual-report"


def test_load_domain_e2e_evidence_rejects_missing_conversation(tmp_path: Path) -> None:
    evidence = tmp_path / "domain-e2e.json"
    evidence.write_text(
        json.dumps(
            {
                "started_at": "2026-07-20T13:58:00Z",
                "generated_at": "2026-07-20T14:00:00Z",
                "low_risk_thread_id": "conv-low",
                "approved_thread_id": "conv-approved",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="three conversation IDs"):
        _load_domain_e2e_evidence(evidence)


def test_conversation_trace_criteria_use_messages_mapping() -> None:
    criteria = _build_conversation_trace_testing_criteria(["coherence"], "gpt-4o-mini")

    assert criteria == [
        {
            "type": "azure_ai_evaluator",
            "name": "coherence",
            "evaluator_name": "builtin.coherence",
            "initialization_parameters": {"model": "gpt-4o-mini"},
            "data_mapping": {
                "messages": "{{item.messages}}",
            },
        }
    ]


def test_trace_materialization_delay_waits_for_minimum_evidence_age() -> None:
    generated_at = datetime(2026, 7, 20, 14, 0, tzinfo=timezone.utc)

    delay = _trace_materialization_delay(
        generated_at,
        90,
        now=datetime(2026, 7, 20, 14, 0, 30, tzinfo=timezone.utc),
    )

    assert delay == 60


@pytest.mark.parametrize("minimum_age_seconds", [-1, float("nan"), float("inf")])
def test_trace_materialization_delay_rejects_invalid_minimum_age(
    minimum_age_seconds: float,
) -> None:
    with pytest.raises(ValueError, match="finite non-negative"):
        _trace_materialization_delay(
            datetime(2026, 7, 20, 14, 0, tzinfo=timezone.utc),
            minimum_age_seconds,
        )
