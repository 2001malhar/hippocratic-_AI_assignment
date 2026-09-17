"""Story generation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_story_service
from app.schemas.api import ErrorResponse, StoryRequest, StoryResponse, StyleOption
from app.services.story_service import StoryService
from app.styles import STYLES

router = APIRouter(prefix="/api/v1", tags=["stories"])


@router.get("/styles", response_model=list[StyleOption], summary="List story styles")
async def list_styles() -> list[StyleOption]:
    """Return the selectable storytelling styles."""
    return [
        StyleOption(key=style.key, label=style.label, description=style.description)
        for style in STYLES
    ]


@router.post(
    "/stories",
    response_model=StoryResponse,
    summary="Generate a bedtime story",
    responses={
        502: {"model": ErrorResponse, "description": "The model returned unusable output."},
        503: {"model": ErrorResponse, "description": "The model is unavailable."},
    },
)
async def create_story(
    payload: StoryRequest,
    service: StoryService = Depends(get_story_service),
) -> StoryResponse:
    """Run the full plan -> generate -> judge -> refine -> publish pipeline.

    Returns the published story together with its plan, score card and the
    per-iteration judge trace, so a caller can see exactly why it was accepted.
    """
    return await service.generate(
        request=payload.request,
        style=payload.style,
        max_revisions=payload.max_revisions,
    )
