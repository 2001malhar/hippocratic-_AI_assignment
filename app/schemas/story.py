"""Domain models for the story pipeline.

``StoryPlan`` and ``JudgeVerdict`` are what the two JSON-emitting LLM calls must
produce, and are validated at the node boundary so a malformed plan or verdict
cannot flow downstream unnoticed.

``ScoreCard`` is the deterministic output: the LLM supplies raw 1-5 judgements,
Python decides the average, the safety veto and the pass/fail.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

# The six rubric dimensions, in report order. All six are averaged into
# `overall_score`; only a subset is individually gated (see Settings).
SCORE_KEYS: tuple[str, ...] = (
    "request_adherence",
    "age_appropriateness",
    "story_quality",
    "story_structure",
    "emotional_safety",
    "bedtime_quality",
)

Score = Annotated[float, Field(ge=1.0, le=5.0)]


class TerminalReason(str, Enum):
    """Why the graph stopped iterating."""

    PASSED_THRESHOLD = "passed_threshold"
    MAX_REVISIONS_EXHAUSTED = "max_revisions_exhausted"


class Decision(str, Enum):
    """The deterministic routing decision made by the threshold detector."""

    PUBLISH = "publish"
    REFINE = "refine"


class StoryPlan(BaseModel):
    """The compact blueprint the planner produces before any prose is written."""

    model_config = ConfigDict(extra="ignore")

    category: str
    target_age: str
    characters: list[str] = Field(min_length=1)
    setting: str
    tone: str
    story_arc: list[str] = Field(min_length=1)
    lesson: str
    bedtime_ending: str

    @field_validator("characters", "story_arc", mode="before")
    @classmethod
    def _coerce_to_list(cls, value: object) -> object:
        """Accept a comma-joined string where a list was requested.

        gpt-3.5-turbo returns ``"fox, bunny"`` instead of ``["fox", "bunny"]``
        often enough that rejecting it would mean burning a retry on a plan that
        is otherwise perfectly usable.
        """
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


class ContentFlags(BaseModel):
    """Hard parental-guideline breaches reported by the judge.

    Any flag set to ``True`` triggers a deterministic veto in the evaluation
    service. The model cannot score its way past these.
    """

    model_config = ConfigDict(extra="ignore")

    violence: bool = False
    scary_imagery: bool = False
    death_or_loss: bool = False
    cruelty: bool = False
    unresolved_distress: bool = False
    adult_themes: bool = False
    unsafe_behavior_modeled: bool = False
    frightening_ending: bool = False

    def tripped(self) -> list[str]:
        """Return the names of every flag that is set."""
        return [name for name, value in self.model_dump().items() if value]


class JudgeVerdict(BaseModel):
    """Raw judge output.

    The judge is explicitly forbidden from computing the average or the pass
    decision -- it only supplies the six subjective scores, the safety flags and
    the feedback. Everything downstream of that is deterministic Python.
    """

    model_config = ConfigDict(extra="ignore")

    request_adherence: Score = 1.0
    age_appropriateness: Score = 1.0
    story_quality: Score = 1.0
    story_structure: Score = 1.0
    emotional_safety: Score = 1.0
    bedtime_quality: Score = 1.0

    content_flags: ContentFlags = Field(default_factory=ContentFlags)
    final_sentences: str = ""
    calming_ending_met: bool = True
    feedback: list[str] = Field(default_factory=list)

    @field_validator(*SCORE_KEYS, mode="before")
    @classmethod
    def _coerce_score(cls, value: object) -> float:
        """Coerce and clamp a score into the 1-5 rubric range.

        A missing or non-numeric score becomes 1.0 -- the safe interpretation is
        that an unscored dimension failed, not that it passed.
        """
        try:
            score = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 1.0
        return max(1.0, min(5.0, score))

    @field_validator("feedback", mode="before")
    @classmethod
    def _coerce_feedback(cls, value: object) -> list[str]:
        """Normalise feedback into a list of non-empty strings."""
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []


class ScoreCard(BaseModel):
    """The judged result after deterministic post-processing.

    This is the object the threshold detector routes on and the API returns.
    """

    model_config = ConfigDict(extra="forbid")

    request_adherence: Score
    age_appropriateness: Score
    story_quality: Score
    story_structure: Score
    emotional_safety: Score
    bedtime_quality: Score

    overall_score: float = Field(ge=1.0, le=5.0)
    rating: int = Field(ge=1, le=5, description="Star rating derived from overall_score.")
    passed: bool

    content_flags: ContentFlags
    safety_violations: list[str] = Field(default_factory=list)
    calming_ending_met: bool = True
    final_sentences: str = ""
    feedback: list[str] = Field(default_factory=list)
    failed_metrics: list[str] = Field(
        default_factory=list,
        description="Gated metrics that fell below their configured threshold.",
    )

    def scores(self) -> dict[str, float]:
        """Return just the six rubric dimensions."""
        return {key: getattr(self, key) for key in SCORE_KEYS}


class IterationRecord(BaseModel):
    """One judge pass, kept so the whole revision history is inspectable."""

    model_config = ConfigDict(extra="forbid")

    iteration: int = Field(ge=1)
    story: str
    scorecard: ScoreCard
