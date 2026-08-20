from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from evals.foundry_eval_runner import (
    _assert_eval_passed,
    _build_workflow_testing_criteria,
    _evidence_path,
    _load_private_e2e_evidence,
    _load_workflow_messages,
    _workflow_base_url,
    _workflow_data_source_config,
    _workflow_run_data_source,
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
    current = tmp_path / "release-hosted-e2e.json"
    monkeypatch.setenv("HOSTED_E2E_EVIDENCE_FILE", str(current))

    assert _evidence_path(tmp_path, "tracked-sample.json") == current


def test_load_private_e2e_evidence_requires_all_release_conversations(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "hosted-e2e-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-20T14:00:00Z",
                "started_at": "2026-07-20T13:45:00Z",
                "release_id": "release-1",
                "conversation_ids": ["conv-low", "conv-approved", "conv-damaged"],
            }
        ),
        encoding="utf-8",
    )

    started_at, generated_at, conversation_ids, release_id = _load_private_e2e_evidence(evidence)

    assert started_at == datetime(2026, 7, 20, 13, 45, tzinfo=timezone.utc)
    assert generated_at == datetime(2026, 7, 20, 14, 0, tzinfo=timezone.utc)
    assert conversation_ids == ["conv-low", "conv-approved", "conv-damaged"]
    assert release_id == "release-1"


def test_load_private_e2e_evidence_requires_release_id(tmp_path: Path) -> None:
    evidence = tmp_path / "hosted-e2e-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-20T14:00:00Z",
                "started_at": "2026-07-20T13:45:00Z",
                "conversation_ids": ["conv-low", "conv-approved", "conv-damaged"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing release_id"):
        _load_private_e2e_evidence(evidence)


def test_load_private_e2e_evidence_rejects_missing_conversation(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "hosted-e2e-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-20T14:00:00Z",
                "started_at": "2026-07-20T13:45:00Z",
                "release_id": "release-1",
                "low_risk_thread_id": "conv-low",
                "approved_thread_id": "conv-approved",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="three conversation IDs"):
        _load_private_e2e_evidence(evidence)


def test_workflow_criteria_use_messages_mapping() -> None:
    criteria = _build_workflow_testing_criteria(["coherence"], "gpt-4o-mini")

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


def test_workflow_eval_uses_ephemeral_message_snapshots() -> None:
    messages = [
        [
            {"role": "user", "content": "Where is my order?"},
            {"role": "assistant", "content": "It is in transit."},
        ]
    ]

    assert _workflow_data_source_config()["type"] == "custom"
    assert _workflow_run_data_source(messages) == {
        "type": "jsonl",
        "source": {
            "type": "file_content",
            "content": [{"item": {"messages": messages[0]}}],
        },
    }


def test_workflow_base_url_uses_secure_deployment_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = tmp_path / "hosted-e2e-evidence.json"
    verification = tmp_path / "deployment-verification.json"
    evidence.write_text("{}", encoding="utf-8")
    verification.write_text(
        json.dumps(
            {
                "status": "passed",
                "endpoints": {
                    "frontend_url": "https://private-frontend.example.test/",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("FOUNDRY_WORKFLOW_BASE_URL", raising=False)
    monkeypatch.delenv("FOUNDRY_DEPLOYMENT_VERIFICATION_FILE", raising=False)

    assert _workflow_base_url(tmp_path, evidence) == "https://private-frontend.example.test"


def test_workflow_base_url_rejects_insecure_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOUNDRY_WORKFLOW_BASE_URL", "http://frontend.example.test")

    with pytest.raises(ValueError, match="must use HTTPS"):
        _workflow_base_url(tmp_path, tmp_path / "evidence.json")


def test_load_workflow_messages_uses_only_redacted_projection_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_urls: list[str] = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        @staticmethod
        def read() -> bytes:
            return json.dumps(
                {
                    "thread_id": "conv/private",
                    "input": "Order ORD-1001 is late.",
                    "latest_output": {"message": "A partial refund was submitted."},
                    "events": [{"payload": {"customer_email": "redacted@example.test"}}],
                    "pending_approvals": [{"internal": "not-for-evaluation"}],
                }
            ).encode()

    def _urlopen(request, timeout: int):
        requested_urls.append(request.full_url)
        assert timeout == 30
        return _Response()

    monkeypatch.setattr("evals.foundry_eval_runner.urlopen", _urlopen)

    assert _load_workflow_messages(
        "https://private-frontend.example.test",
        ["conv/private"],
    ) == [
        [
            {"role": "user", "content": "Order ORD-1001 is late."},
            {"role": "assistant", "content": "A partial refund was submitted."},
        ]
    ]
    assert requested_urls == ["https://private-frontend.example.test/api/workflows/conv%2Fprivate"]
