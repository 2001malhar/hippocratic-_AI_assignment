"""Liveness endpoint. Makes no LLM call, so it is safe to poll."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app import __version__
from app.llm.client import api_key_configured
from app.schemas.api import HealthResponse
from app.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse, summary="Liveness check")
async def healthz(request: Request) -> HealthResponse:
    """Report whether the app booted and is configured to serve requests."""
    return HealthResponse(
        status="ok",
        version=__version__,
        model=get_settings().llm_model,
        graph_ready=getattr(request.app.state, "story_service", None) is not None,
        api_key_configured=api_key_configured(),
    )
