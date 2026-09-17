"""Node 4 (deterministic): decide whether to publish or refine.

No LLM call. This node is the entire acceptance policy made visible: it reads
the score card the evaluation service produced, compares it against the
configured budget, and writes its decision into state so the conditional edge is
a one-line lookup and the decision shows up in the trace.

It is also what guarantees termination -- once the revision budget is spent the
only remaining branch is ``publish``.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.graph.state import StoryState
from app.schemas.story import Decision, ScoreCard, TerminalReason
from app.services.evaluation import is_better

logger = get_logger(__name__)


async def threshold_detector_node(state: StoryState) -> dict:
    """Route the run, and keep track of the best draft seen so far."""
    scorecard = ScoreCard.model_validate(state["scorecard"])
    iteration = state["iteration"]
    revisions_used = state.get("revisions_used", 0)
    max_revisions = state["max_revisions"]

    update: dict = {}

    # Track the best draft so an exhausted budget still publishes the strongest
    # version rather than the most recent one.
    incumbent_raw = state.get("best_scorecard")
    incumbent = ScoreCard.model_validate(incumbent_raw) if incumbent_raw else None
    if is_better(scorecard, incumbent):
        update |= {
            "best_story": state["story"],
            "best_scorecard": scorecard.model_dump(),
            "best_iteration": iteration,
        }

    if scorecard.passed:
        decision, reason = Decision.PUBLISH, TerminalReason.PASSED_THRESHOLD
        logger.info("Threshold met on pass %d (%.2f) -> publish", iteration, scorecard.overall_score)
    elif revisions_used >= max_revisions:
        decision, reason = Decision.PUBLISH, TerminalReason.MAX_REVISIONS_EXHAUSTED
        logger.info(
            "Revision budget spent (%d/%d) -> publishing best draft from pass %d",
            revisions_used,
            max_revisions,
            update.get("best_iteration", state.get("best_iteration", iteration)),
        )
    else:
        decision, reason = Decision.REFINE, ""
        logger.info(
            "Below threshold on pass %d (%.2f, failed=%s) -> refine %d/%d",
            iteration,
            scorecard.overall_score,
            scorecard.failed_metrics or scorecard.safety_violations,
            revisions_used + 1,
            max_revisions,
        )

    update["decision"] = decision.value
    if reason:
        update["terminal_reason"] = reason.value

    return update
