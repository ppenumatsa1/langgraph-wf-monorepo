from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


class MCPArguments(BaseModel):
    query: str = Field(min_length=1)


class MCPRequest(BaseModel):
    tool: str
    arguments: MCPArguments


app = FastAPI(title="Mock MCP Server", version="0.1.0")


def _validate_auth(authorization: str | None, x_api_key: str | None) -> None:
    expected_api_key = os.getenv("MOCK_MCP_API_KEY")
    expected_bearer = os.getenv("MOCK_MCP_BEARER_TOKEN")

    if expected_api_key and x_api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid X-API-Key")

    if expected_bearer:
        expected_header = f"Bearer {expected_bearer}"
        if authorization != expected_header:
            raise HTTPException(
                status_code=401, detail="Invalid Authorization bearer token"
            )


@app.post("/mcp")
async def mcp_tool(
    payload: MCPRequest,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    _validate_auth(authorization=authorization, x_api_key=x_api_key)

    if payload.tool != "search":
        raise HTTPException(status_code=400, detail=f"Unsupported tool: {payload.tool}")

    query = payload.arguments.query
    return {
        "tool": payload.tool,
        "query": query,
        "results": [
            {
                "title": "Refund policy",
                "summary": "Refunds are allowed for delays beyond 3 days.",
                "score": 0.93,
            },
            {
                "title": "Damaged item policy",
                "summary": "Offer replacement or full refund after verification.",
                "score": 0.89,
            },
        ],
        "metadata": {
            "server": "mock-mcp",
            "auth_validated": True,
        },
    }
