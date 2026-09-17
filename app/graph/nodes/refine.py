"""Node 5 (LLM): rewrite the draft using the judge's feedback.

Reached only when the threshold detector routed here, and it always loops back
to the judge -- a refined story is never published unscored.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.graph.state import StoryState
from app.llm import LLMRole, invoke_text
from app.prompts import reviser
from app.schemas.story import ScoreCard

logger = get_logger(__name__)


async def refine_node(state: StoryState) -> dict:
    """Produce a revised draft addressing the latest score card."""
    scorecard = ScoreCard.model_validate(state["scorecard"])
    revisions_used = state.get("revisions_used", 0) + 1

    logger.info(
        "Refining (revision %d): %s",
        revisions_used,
        "; ".join(scorecard.feedback[:2]),
    )

    story = await invoke_text(
        LLMRole.REVISER,
        reviser.SYSTEM,
        reviser.build_prompt(
            user_request=state["user_request"],
            style=state["style"],
            plan=state["plan"],
            story=state["story"],
            feedback=scorecard.feedback,
            safety_violations=scorecard.safety_violations,
            calming_ending_met=scorecard.calming_ending_met,
        ),
    )

    return {"story": story, "revisions_used": revisions_used}
