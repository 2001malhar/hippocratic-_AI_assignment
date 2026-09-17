"""Run the graph and shape the result.

This is the single entry point used by the API, the Gradio UI and the CLI, so
all three behave identically and none of them duplicates orchestration logic.
"""

from __future__ import annotations

import time
import uuid

from langgraph.graph.state import CompiledStateGraph

from app.core.logging import get_logger, set_run_id
from app.graph.builder import get_graph
from app.graph.state import initial_state
from app.schemas.api import IterationSummary, StoryResponse
from app.schemas.story import IterationRecord, ScoreCard, StoryPlan, TerminalReason
from app.settings import get_settings
from app.styles import StyleKey, describe

logger = get_logger(__name__)


class StoryService:
    """Generates bedtime stories by invoking the compiled graph."""

    def __init__(self, graph: CompiledStateGraph | None = None) -> None:
        self._graph = graph or get_graph()

    async def generate(
        self,
        request: str,
        style: StyleKey = StyleKey.AUTO,
        max_revisions: int | None = None,
    ) -> StoryResponse:
        """Run one story generation end to end."""
        settings = get_settings()
        run_id = uuid.uuid4().hex[:8]
        set_run_id(run_id)

        budget = settings.max_revisions if max_revisions is None else max_revisions
        started = time.perf_counter()

        logger.info(
            "Starting run: style=%s max_revisions=%d request=%r",
            style.value,
            budget,
            request,
        )

        final = await self._graph.ainvoke(
            initial_state(
                run_id=run_id,
                user_request=request.strip(),
                style=describe(style),
                max_revisions=budget,
            ),
            config={
                # Derived from the revision budget rather than left at the
                # default 25, so an override of max_revisions cannot trip it.
                "recursion_limit": max(settings.recursion_limit, 2 * (budget + 1) + 6),
            },
        )

        elapsed = time.perf_counter() - started
        response = self._to_response(final, request, style, elapsed)

        logger.info(
            "Run complete in %.1fs: rating=%d/5 revisions=%d reason=%s",
            elapsed,
            response.rating,
            response.revisions_used,
            response.terminal_reason.value,
        )
        return response

    @staticmethod
    def _to_response(
        final: dict,
        request: str,
        style: StyleKey,
        elapsed: float,
    ) -> StoryResponse:
        """Convert terminal graph state into the API response model."""
        scorecard = ScoreCard.model_validate(final["scorecard"])
        history = [IterationRecord.model_validate(item) for item in final.get("history", [])]

        return StoryResponse(
            run_id=final["run_id"],
            title=final["published_title"],
            story=final["published_story"],
            plan=StoryPlan.model_validate(final["plan"]),
            scorecard=scorecard,
            rating=scorecard.rating,
            revisions_used=final.get("revisions_used", 0),
            judge_passes=final.get("iteration", len(history)),
            terminal_reason=TerminalReason(final["terminal_reason"]),
            published_iteration=final.get("best_iteration", final.get("iteration", 1)),
            history=[
                IterationSummary(
                    iteration=record.iteration,
                    overall_score=record.scorecard.overall_score,
                    passed=record.scorecard.passed,
                    scores=record.scorecard.scores(),
                    feedback=record.scorecard.feedback,
                    safety_violations=record.scorecard.safety_violations,
                )
                for record in history
            ],
            style=style,
            request=request.strip(),
            elapsed_seconds=round(elapsed, 2),
        )
