from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable

from app.modules.order_resolution.models import WorkflowEvent

WorkflowEventPageReader = Callable[
    [str, int, str | None],
    tuple[list[WorkflowEvent], str | None, bool],
]


async def iter_durable_workflow_events(
    thread_id: str,
    read_page: WorkflowEventPageReader,
    *,
    initial_cursor: str | None = None,
    page_size: int = 100,
    poll_interval_seconds: float = 1.0,
    emit_heartbeats: bool = False,
) -> AsyncGenerator[WorkflowEvent | None, None]:
    """Replay persisted events, then tail the durable workflow ledger.

    When requested by an SSE route, an idle poll yields ``None`` so the route
    can retain its own wire-format heartbeat without fabricating an event.
    """

    cursor = initial_cursor
    while True:
        events, next_cursor, has_more = await asyncio.to_thread(
            read_page,
            thread_id,
            page_size,
            cursor,
        )
        for event in events:
            cursor = f"{event.timestamp}|{event.id}"
            yield event

        if has_more:
            cursor = next_cursor or cursor
            continue

        await asyncio.sleep(poll_interval_seconds)
        if emit_heartbeats:
            yield None


__all__ = ["WorkflowEventPageReader", "iter_durable_workflow_events"]
