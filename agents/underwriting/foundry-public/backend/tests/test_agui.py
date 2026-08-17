from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.routers import agui as agui_router


def test_agui_streams_safe_workflow_projection() -> None:
    class FakeService:
        def __init__(self) -> None:
            self.events = [
                {
                    "id": 1,
                    "event_type": "workflow_start",
                    "executor_name": "main",
                    "created_at": "2026-08-05T00:00:00Z",
                },
                {
                    "id": 2,
                    "event_type": "workflow_completed",
                    "executor_name": "main",
                    "created_at": "2026-08-05T00:00:01Z",
                },
            ]

        async def start_run(self, **_kwargs: object) -> dict[str, object]:
            await asyncio.sleep(0)
            return {"status": "COMPLETED", "outputs": []}

        async def resume_run(self, _workflow_run_id: str) -> dict[str, object]:
            await asyncio.sleep(0)
            return {"status": "COMPLETED", "outputs": []}

        def get_events(self, _workflow_run_id: str) -> list[dict[str, object]]:
            return self.events

    agui_router.service = FakeService()
    app = FastAPI()
    app.include_router(agui_router.router)
    application = {
        "application_id": "app-agui-test",
        "applicant_name": "AGUI Test",
        "age": 38,
        "income": 145000,
        "requested_coverage": 500000,
        "health_disclosures": "none",
        "driving_history": "clean",
        "credit_score": 760,
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/underwriting/ag-ui",
            headers={"accept": "text/event-stream"},
            json={
                "threadId": "stream-test",
                "runId": "stream-test-run",
                "messages": [
                    {
                        "id": "message-test",
                        "role": "user",
                        "content": json.dumps(
                            {
                                "workflow_run_id": "run-agui-test",
                                "application": application,
                            }
                        ),
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert '"name":"underwriting.event"' in response.text
    assert "RUN_FINISHED" in response.text
    assert application["applicant_name"] not in response.text
