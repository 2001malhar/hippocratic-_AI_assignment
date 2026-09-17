"""Request and response models for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.story import ScoreCard, StoryPlan, TerminalReason
from app.styles import DEFAULT_STYLE, StyleKey

DEFAULT_REQUEST = "A tiny fox helps a lost bunny in a moonlit garden."


class StoryRequest(BaseModel):
    """What the caller asks for."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "request": DEFAULT_REQUEST,
                "style": "cozy",
            }
        },
    )

    request: str = Field(
        min_length=3,
        max_length=1000,
        description="Plain-language description of the bedtime story to write.",
    )
    style: StyleKey = Field(
        default=DEFAULT_STYLE,
        description="Storytelling style. 'auto' lets the planner choose.",
    )
    max_revisions: int | None = Field(
        default=None,
        ge=0,
        le=5,
        description="Override the configured revision budget for this run only.",
    )


class IterationSummary(BaseModel):
    """One judge pass, as returned to the caller."""

    model_config = ConfigDict(extra="forbid")

    iteration: int
    overall_score: float
    passed: bool
    scores: dict[str, float]
    feedback: list[str]
    safety_violations: list[str]


class StoryResponse(BaseModel):
    """The published story plus the full trace of how it got there."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    title: str
    story: str

    plan: StoryPlan
    scorecard: ScoreCard
    rating: int = Field(ge=1, le=5)

    revisions_used: int
    judge_passes: int
    terminal_reason: TerminalReason
    published_iteration: int = Field(
        description="Which judge pass produced the published draft (the best-scoring one)."
    )
    history: list[IterationSummary]

    style: StyleKey
    request: str
    elapsed_seconds: float


class StyleOption(BaseModel):
    """A selectable style, for populating clients."""

    model_config = ConfigDict(extra="forbid")

    key: StyleKey
    label: str
    description: str


class HealthResponse(BaseModel):
    """Liveness payload. Deliberately makes no LLM call."""

    model_config = ConfigDict(extra="forbid")

    status: str
    version: str
    model: str
    graph_ready: bool
    api_key_configured: bool


class ErrorResponse(BaseModel):
    """Uniform error body."""

    model_config = ConfigDict(extra="forbid")

    error: str
    detail: str
    run_id: str | None = None
