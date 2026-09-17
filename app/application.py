"""Application factory.

One process, one port: the JSON API lives under ``/api/v1`` and the Gradio UI is
mounted at ``/ui``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import gradio as gr
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.routes import health_router, stories_router
from app.core.exceptions import ConfigurationError
from app.core.logging import configure_logging, get_logger
from app.graph.builder import get_graph
from app.llm.client import warmup
from app.services.story_service import StoryService
from app.settings import get_settings
from app.ui import build_blocks

logger = get_logger(__name__)

DESCRIPTION = """
Generates bedtime stories for children aged 5-10 using a LangGraph pipeline:

`plan_story` -> `generate_story` -> `judge` -> `threshold_detector` -> `publish`,
with a `refine` -> `judge` loop for any draft that falls short.

Planning, writing, judging and refining are LLM steps. Scoring, the parental
safety veto, the threshold decision and publishing are deterministic Python.

The Gradio UI is at [/ui](/ui).
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the graph and the LLM clients once, at startup."""
    settings = get_settings()
    logger.info("Starting Bedtime Story Agent v%s", __version__)

    try:
        warmup()
    except ConfigurationError as exc:
        # Serve anyway so /healthz and /docs still work and can report the
        # problem; story requests will fail with a clear message.
        logger.error("%s Story generation will fail until this is fixed.", exc)

    logger.info(
        "Ready: model=%s max_revisions=%d thresholds=%s",
        settings.llm_model,
        settings.max_revisions,
        settings.evaluation_policy,
    )
    yield
    logger.info("Shutting down")


def create_app() -> FastAPI:
    """Build the fully wired ASGI application."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Bedtime Story Agent",
        description=DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
    )

    # One service instance shared by the API and the UI, so both run the same
    # compiled graph rather than each holding their own.
    app.state.story_service = StoryService(get_graph())

    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(stories_router)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/ui")

    # Mounted last: Gradio takes over its subtree, so every API route must
    # already be registered.
    return gr.mount_gradio_app(app, build_blocks(app.state.story_service), path="/ui")
