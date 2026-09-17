"""Node 1 (LLM): turn the user's request into a validated story plan."""

from __future__ import annotations

from pydantic import ValidationError

from app.core.exceptions import PlanValidationError
from app.core.logging import get_logger
from app.graph.state import StoryState
from app.llm import LLMRole, invoke_json
from app.prompts import planner
from app.schemas.story import StoryPlan

logger = get_logger(__name__)


async def plan_story_node(state: StoryState) -> dict:
    """Produce a ``StoryPlan`` for the request.

    The plan is schema-validated before it reaches the storyteller. On a
    validation failure the planner is re-asked once with the specific errors
    quoted back to it, which recovers most malformed plans.
    """
    user_request = state["user_request"]
    style = state["style"]

    raw = await invoke_json(
        LLMRole.PLANNER,
        planner.SYSTEM,
        planner.build_prompt(user_request, style),
    )

    try:
        plan = StoryPlan.model_validate(raw)
    except ValidationError as first_error:
        logger.warning("Story plan failed validation, re-asking the planner once.")
        repaired = await invoke_json(
            LLMRole.PLANNER,
            planner.SYSTEM,
            planner.build_repair_prompt(user_request, style, _summarise(first_error)),
        )
        try:
            plan = StoryPlan.model_validate(repaired)
        except ValidationError as second_error:
            raise PlanValidationError(
                f"The planner returned an unusable plan: {_summarise(second_error)}"
            ) from second_error

    logger.info("Plan ready: category=%s, characters=%d", plan.category, len(plan.characters))
    return {"plan": plan.model_dump()}


def _summarise(error: ValidationError) -> str:
    """Render validation errors compactly enough to paste into a prompt."""
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or 'root'}: {item['msg']}"
        for item in error.errors()
    )
