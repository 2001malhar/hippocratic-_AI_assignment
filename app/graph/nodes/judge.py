"""Node 3 (LLM): score the current draft against the rubric and the guidelines.

The LLM part ends at ``JudgeVerdict``. The pass/fail, the average and the safety
veto are computed by ``app.services.evaluation``, which is pure Python.
"""

from __future__ import annotations

from pydantic import ValidationError

from app.core.exceptions import JudgeValidationError
from app.core.logging import get_logger
from app.graph.state import StoryState
from app.llm import LLMRole, invoke_json
from app.prompts import judge as judge_prompt
from app.schemas.story import IterationRecord, JudgeVerdict
from app.services.evaluation import score_story

logger = get_logger(__name__)


async def judge_node(state: StoryState) -> dict:
    """Evaluate the current draft and append the result to the history."""
    raw = await invoke_json(
        LLMRole.JUDGE,
        judge_prompt.SYSTEM,
        judge_prompt.build_prompt(
            state["user_request"],
            state["style"],
            state["plan"],
            state["story"],
        ),
    )

    try:
        verdict = JudgeVerdict.model_validate(raw)
    except ValidationError as exc:
        # The schema coerces scores and feedback, so reaching here means the
        # response was structurally wrong rather than merely sloppy.
        raise JudgeValidationError(f"The judge returned an unusable evaluation: {exc}") from exc

    scorecard = score_story(verdict)
    iteration = state.get("iteration", 0) + 1

    logger.info(
        "Judge pass %d: overall=%.2f passed=%s failed=%s violations=%s",
        iteration,
        scorecard.overall_score,
        scorecard.passed,
        scorecard.failed_metrics or "none",
        scorecard.safety_violations or "none",
    )

    record = IterationRecord(
        iteration=iteration,
        story=state["story"],
        scorecard=scorecard,
    )

    return {
        "scorecard": scorecard.model_dump(),
        "feedback": scorecard.feedback,
        "iteration": iteration,
        "history": [record.model_dump()],
    }
