from __future__ import annotations

from datetime import UTC, datetime, timedelta

from psycopg import connect

from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository


def test_workflow_run_claim_is_atomic() -> None:
    repo = WorkflowRunRepository()

    assert repo.create_workflow_run("run-claim", "app-claim", "Ada Lovelace") is True
    assert repo.create_workflow_run("run-claim", "app-claim", "Ada Lovelace") is False


def test_history_searches_filters_and_sorts_newest_first() -> None:
    repo = WorkflowRunRepository()
    repo.create_workflow_run("run-older", "app-older", "Grace Hopper")
    repo.create_workflow_run("run-newer", "app-newer", "Ada Lovelace")
    with connect(repo._pool.conninfo, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE workflow_runs SET created_at = %s WHERE id = %s",
                (datetime.now(UTC) - timedelta(minutes=5), "run-older"),
            )
    repo.record_checkpoint("run-newer", "cp-newer", "", None, {})
    repo.update_workflow_run_status("run-newer", "CRASHED")
    repo.save_underwriting_result(
        "run-older",
        "app-older",
        "final_decision",
        {"decision": "APPROVED"},
        "run-older:final_decision:app-older",
    )

    total, items = repo.list_workflow_runs(search=None, status=None, limit=25, offset=0)

    assert total == 2
    assert [item["workflow_run_id"] for item in items] == ["run-newer", "run-older"]
    assert items[0]["resumable"] is True
    assert items[1]["final_decision"] == "APPROVED"

    total, items = repo.list_workflow_runs(search="ada", status=None, limit=25, offset=0)
    assert total == 1
    assert items[0]["workflow_run_id"] == "run-newer"

    total, items = repo.list_workflow_runs(search=None, status="crashed", limit=25, offset=0)
    assert total == 1
    assert items[0]["workflow_run_id"] == "run-newer"
