"""Deterministic evaluation policy.

The judge supplies the scores; this module supplies the verdict. Nothing here
calls an LLM, and every function is pure -- given the same ``JudgeVerdict`` and
the same settings it always returns the same ``ScoreCard``.

Two rules worth noting:

* ``story_quality`` and ``story_structure`` count toward the average but are not
  gated individually -- a slightly plain story is publishable, an unsafe or
  off-request one never is.
* A missing or non-numeric score is read as 1.0, not as a pass.
"""

from __future__ import annotations

from app.schemas.story import SCORE_KEYS, JudgeVerdict, ScoreCard
from app.settings import Settings, get_settings

# Emotional safety is forced no higher than this when a content flag is tripped.
SAFETY_VETO_CEILING = 2.0

# Bedtime quality is forced no higher than this when the ending is not calming.
CALMING_ENDING_CEILING = 3.0


def score_story(verdict: JudgeVerdict, settings: Settings | None = None) -> ScoreCard:
    """Turn raw judge output into a final, policy-applied score card.

    Pure: the input verdict is never mutated.
    """
    settings = settings or get_settings()

    scores = {key: float(getattr(verdict, key)) for key in SCORE_KEYS}

    # --- Deterministic vetoes -------------------------------------------
    # A model that flags "violence: true" and then awards emotional_safety 5 is
    # not a hypothetical; clamping here means the flag, not the score, decides.
    safety_violations = verdict.content_flags.tripped()
    if safety_violations:
        scores["emotional_safety"] = min(scores["emotional_safety"], SAFETY_VETO_CEILING)

    if not verdict.calming_ending_met:
        scores["bedtime_quality"] = min(scores["bedtime_quality"], CALMING_ENDING_CEILING)

    overall = round(sum(scores.values()) / len(scores), 2)

    # --- Threshold gate --------------------------------------------------
    metrics = {**scores, "overall_score": overall}
    failed_metrics = [
        metric
        for metric, minimum in settings.evaluation_policy.items()
        if metrics.get(metric, 0.0) < minimum
    ]

    # A content flag fails the story outright, whatever the arithmetic says.
    passed = not failed_metrics and not safety_violations

    return ScoreCard(
        **scores,
        overall_score=overall,
        rating=derive_rating(overall),
        passed=passed,
        content_flags=verdict.content_flags,
        safety_violations=safety_violations,
        calming_ending_met=verdict.calming_ending_met,
        final_sentences=verdict.final_sentences,
        feedback=normalise_feedback(verdict.feedback),
        failed_metrics=failed_metrics,
    )


def derive_rating(overall_score: float) -> int:
    """Map the 1-5 average onto a 1-5 star rating.

    Computed here rather than asked of the judge, so the rating can never
    contradict the scores it is supposed to summarise.
    """
    return max(1, min(5, round(overall_score)))


def normalise_feedback(feedback: list[str]) -> list[str]:
    """Guarantee the reviser always has something actionable to work from."""
    cleaned = [item.strip() for item in feedback if item and item.strip()]
    if cleaned:
        return cleaned
    return [
        "Improve the weakest scoring dimensions while preserving strong parts of the story."
    ]


def is_better(candidate: ScoreCard, incumbent: ScoreCard | None) -> bool:
    """Whether ``candidate`` should replace ``incumbent`` as the best draft.

    Used so the graph can publish the best draft it saw rather than the last
    one: a revision pass sometimes fixes the flagged issue and regresses
    something else, and there is no reason to ship the worse text.

    Ordering, most significant first: a safe story beats an unsafe one, a
    passing story beats a failing one, then the higher average wins.
    """
    if incumbent is None:
        return True

    candidate_safe = not candidate.safety_violations
    incumbent_safe = not incumbent.safety_violations
    if candidate_safe != incumbent_safe:
        return candidate_safe

    if candidate.passed != incumbent.passed:
        return candidate.passed

    return candidate.overall_score > incumbent.overall_score
