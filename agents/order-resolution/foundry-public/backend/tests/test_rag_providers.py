from __future__ import annotations

import pytest
from app.infrastructure.rag import RetrievalRequest
from app.infrastructure.rag.providers import NoopRAGProvider


@pytest.mark.asyncio
async def test_policy_lookup_does_not_persist_vector_state() -> None:
    provider = NoopRAGProvider()
    result = await provider.retrieve(
        RetrievalRequest(
            thread_id="thread-1",
            query="Policy guidance for late_delivery",
            issue_type="late_delivery",
            top_k=3,
        )
    )
    assert result.provider == "noop"
    assert result.evidence == []
