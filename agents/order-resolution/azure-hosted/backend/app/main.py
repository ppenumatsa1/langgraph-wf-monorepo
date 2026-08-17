from __future__ import annotations

import os
from contextlib import asynccontextmanager

from app.api.v1.routers.chat import router as chat_router
from app.api.v1.routers.copilotkit import router as copilotkit_router
from app.api.v1.routers.health import router as health_router
from app.api.v1.routers.hitl import router as hitl_router
from app.api.v1.routers.sessions import router as sessions_router
from app.api.v1.routers.workflows import router as workflows_router
from app.core.container import order_resolution_service
from app.core.telemetry import (
    enable_langgraph_auto_tracing,
    instrument_fastapi_app,
    setup_observability,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

setup_observability()
enable_langgraph_auto_tracing()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await order_resolution_service.startup()
    try:
        yield
    finally:
        await order_resolution_service.shutdown()


app = FastAPI(
    title="LangGraph Order Resolution",
    version="0.2.0",
    lifespan=lifespan,
)
instrument_fastapi_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",")
        if origin.strip()
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(copilotkit_router)
app.include_router(hitl_router)
app.include_router(workflows_router)
app.include_router(sessions_router)
app.include_router(health_router)
