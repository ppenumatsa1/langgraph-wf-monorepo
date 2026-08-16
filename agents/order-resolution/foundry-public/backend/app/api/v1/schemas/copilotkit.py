from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CopilotKitAgentDiscovery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    class_name: str = Field(alias="className")
    description: str


class CopilotKitThreadEndpoints(BaseModel):
    list: bool = False
    inspect: bool = False
    mutations: bool = False
    realtime_metadata: bool = Field(default=False, alias="realtimeMetadata")


class CopilotKitDiscoveryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: Literal["1.0"] = "1.0"
    agents: dict[str, CopilotKitAgentDiscovery]
    audio_file_transcription_enabled: bool = Field(
        default=False,
        alias="audioFileTranscriptionEnabled",
    )
    mode: Literal["sse"] = "sse"
    thread_endpoints: CopilotKitThreadEndpoints = Field(alias="threadEndpoints")
    a2ui_enabled: bool = Field(default=False, alias="a2uiEnabled")


class CopilotKitBridgeRequest(BaseModel):
    """AG-UI-compatible input used only to select an existing workflow thread."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    thread_id: str = Field(
        alias="threadId",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    run_id: str | None = Field(default=None, alias="runId", max_length=128, exclude=True)
    # CopilotKit includes these standard AG-UI fields. They are intentionally
    # discarded: the bridge never accepts prompts, state, or tool execution.
    messages: list[dict[str, Any]] = Field(default_factory=list, max_length=32, exclude=True)
    state: dict[str, Any] | None = Field(default=None, exclude=True)
    tools: list[dict[str, Any]] = Field(default_factory=list, max_length=32, exclude=True)
    context: list[dict[str, Any]] = Field(default_factory=list, max_length=32, exclude=True)
    forwarded_props: dict[str, Any] | None = Field(
        default=None,
        alias="forwardedProps",
        exclude=True,
    )


__all__ = [
    "CopilotKitAgentDiscovery",
    "CopilotKitBridgeRequest",
    "CopilotKitDiscoveryResponse",
    "CopilotKitThreadEndpoints",
]
