from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers.agui import router as agui_router
from app.api.v1.routers.copilotkit import router as copilotkit_router
from app.api.v1.routers.health import router as health_router
from app.api.v1.routers.underwriting import router as underwriting_router
from app.core.container import get_settings, get_underwriting_service
from app.core.observability import configure_observability, instrument_http_request

settings = get_settings()
configure_observability(settings.log_level)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    underwriting_service = get_underwriting_service()
    await underwriting_service.startup()
    try:
        yield
    finally:
        await underwriting_service.shutdown()


app = FastAPI(title="Underwriting LangGraph Prototype API", version="0.3.0", lifespan=lifespan)
app.middleware("http")(instrument_http_request)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(underwriting_router)
app.include_router(agui_router)
app.include_router(copilotkit_router)
app.include_router(health_router)
