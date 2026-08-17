from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class KnowledgeDocument:
    source: str
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievedEvidence:
    evidence_id: str
    document_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalRequest:
    thread_id: str | None
    query: str
    issue_type: str | None
    top_k: int = 3


@dataclass(frozen=True)
class RetrievalResult:
    provider: str
    query_id: str
    evidence: list[RetrievedEvidence] = field(default_factory=list)


class RAGProvider(Protocol):
    async def ingest(self, document: KnowledgeDocument) -> str: ...

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult: ...
