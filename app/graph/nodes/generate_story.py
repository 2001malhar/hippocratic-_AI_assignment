"""Node 2 (LLM): write the first full draft from the plan."""

from __future__ import annotations

from app.core.logging import get_logger
from app.graph.state import StoryState
from app.llm import LLMRole, invoke_text
from app.prompts import storyteller

logger = get_logger(__name__)


async def generate_story_node(state: StoryState) -> dict:
    """Write the initial story. Only ever runs once per run; revisions go through ``refine``."""
    story = await invoke_text(
        LLMRole.STORYTELLER,
        storyteller.SYSTEM,
        storyteller.build_prompt(state["user_request"], state["style"], state["plan"]),
    )

    logger.info("Draft written (%d words)", len(story.split()))
    return {"story": story}
