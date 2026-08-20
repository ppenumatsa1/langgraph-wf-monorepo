from __future__ import annotations

import os
from typing import Any

import httpx


class MCPKnowledgeTool:
    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = endpoint or os.getenv("MCP_SERVER_URL")
        self.api_key = os.getenv("MCP_API_KEY")
        self.api_key_header = os.getenv("MCP_API_KEY_HEADER", "X-API-Key")
        self.bearer_token = os.getenv("MCP_BEARER_TOKEN")
        self.timeout_seconds = float(os.getenv("MCP_TIMEOUT_SECONDS", "15"))

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers[self.api_key_header] = self.api_key
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    async def search(self, query: str) -> dict[str, Any]:
        if not self.endpoint:
            return {
                "source": "mcp-fallback",
                "result": "No MCP server configured. Using local knowledge fallback.",
            }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.endpoint,
                headers=self._build_headers(),
                json={"tool": "search", "arguments": {"query": query}},
            )
            response.raise_for_status()
            return {"source": "mcp-remote", "result": response.json()}
