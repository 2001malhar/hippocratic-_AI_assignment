"""FastAPI dependencies.

The service is built once during startup and held on ``app.state`` so that no
request pays graph-compilation or client-construction cost.
"""

from __future__ import annotations

from fastapi import Request

from app.services.story_service import StoryService


def get_story_service(request: Request) -> StoryService:
    """Return the application-scoped story service."""
    return request.app.state.story_service
