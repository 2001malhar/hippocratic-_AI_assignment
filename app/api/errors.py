"""Exception handlers.

Each domain error carries its own HTTP status and a message safe to show a
caller; the technical detail and the traceback go to the log, not the response
body.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import StoryAgentError
from app.core.logging import get_logger, get_run_id
from app.schemas.api import ErrorResponse

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the application's error handlers."""

    @app.exception_handler(StoryAgentError)
    async def _handle_story_agent_error(
        _request: Request, exc: StoryAgentError
    ) -> JSONResponse:
        logger.error("%s: %s", type(exc).__name__, exc, exc_info=True)
        return JSONResponse(
            status_code=exc.http_status,
            content=ErrorResponse(
                error=type(exc).__name__,
                detail=exc.user_message,
                run_id=get_run_id(),
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="InternalServerError",
                detail="An unexpected error occurred. Check the server logs.",
                run_id=get_run_id(),
            ).model_dump(),
        )
