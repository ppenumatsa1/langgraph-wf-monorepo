from __future__ import annotations

from uuid import uuid4

from app.infrastructure.rag.core import (
    KnowledgeDocument,
    RAGProvider,
    RetrievalRequest,
    RetrievalResult,
)


class NoopRAGProvider(RAGProvider):
    async def ingest(self, document: KnowledgeDocument) -> str:
        return document.source

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        return RetrievalResult(provider="noop", query_id=str(uuid4()), evidence=[])
