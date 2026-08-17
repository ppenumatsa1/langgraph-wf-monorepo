from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncGenerator, Awaitable, Callable

from app.modules.order_resolution.models import WorkflowEvent
from app.modules.order_resolution.rich_events import rich_envelope_for_workflow_event


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[WorkflowEvent]]] = defaultdict(set)
        self._history: dict[str, list[WorkflowEvent]] = defaultdict(list)
        self._listeners: list[Callable[[WorkflowEvent], Awaitable[None] | None]] = []
        self._lock = asyncio.Lock()

    def add_listener(self, listener: Callable[[WorkflowEvent], Awaitable[None] | None]) -> None:
        self._listeners.append(listener)

    async def publish(self, event: WorkflowEvent) -> None:
        async with self._lock:
            self._history[event.thread_id].append(event)
            subscribers = list(self._subscribers[event.thread_id])
        for queue in subscribers:
            await queue.put(event)
        for listener in self._listeners:
            maybe_awaitable = listener(event)
            if asyncio.iscoroutine(maybe_awaitable):
                await maybe_awaitable

    async def subscribe(self, thread_id: str) -> asyncio.Queue[WorkflowEvent]:
        queue: asyncio.Queue[WorkflowEvent] = asyncio.Queue()
        async with self._lock:
            self._subscribers[thread_id].add(queue)
            history = list(self._history[thread_id])
        for item in history:
            await queue.put(item)
        return queue

    async def unsubscribe(self, thread_id: str, queue: asyncio.Queue[WorkflowEvent]) -> None:
        async with self._lock:
            self._subscribers[thread_id].discard(queue)

    async def sse_stream(self, thread_id: str) -> AsyncGenerator[str, None]:
        queue = await self.subscribe(thread_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {event.model_dump_json()}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            await self.unsubscribe(thread_id, queue)

    async def rich_sse_stream(self, thread_id: str) -> AsyncGenerator[str, None]:
        queue = await self.subscribe(thread_id)
        sequence = 0
        run_started = False
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    sequence += 1
                    envelope = rich_envelope_for_workflow_event(event, sequence)
                    if not run_started:
                        envelope["events"].insert(
                            0,
                            {
                                "type": "RUN_STARTED",
                                "threadId": event.thread_id,
                                "runId": event.payload.get("workflow_run_id") or event.thread_id,
                                "timestamp": envelope.get("events", [{}])[0].get("timestamp"),
                                "rawEvent": event.model_dump(),
                            },
                        )
                        run_started = True
                    yield f"event: workflow.rich\ndata: {json.dumps(envelope, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            await self.unsubscribe(thread_id, queue)

    def history_as_json(self, thread_id: str) -> str:
        return json.dumps([event.model_dump() for event in self._history[thread_id]], indent=2)
