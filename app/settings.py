"""Application configuration, loaded from the environment and `.env`.

Every tunable lives here so that thresholds and the revision budget can be
changed through the environment rather than in code. Raising
``THRESHOLD_OVERALL`` tightens the acceptance policy and makes the refine loop
fire more often.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the story agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Credentials -----------------------------------------------------
    openai_api_key: SecretStr | None = Field(default=None)

    # --- Model -----------------------------------------------------------
    # Fixed by project constraint. gpt-3.5-turbo supports `response_format:
    # json_object` but not `json_schema`, hence the fallback parser in app.llm.
    llm_model: str = Field(default="gpt-3.5-turbo")
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    # --- Revision loop ---------------------------------------------------
    max_revisions: int = Field(default=2, ge=0, le=5)

    # --- Acceptance thresholds (1-5 rubric scale) ------------------------
    threshold_overall: float = Field(default=4.0, ge=1.0, le=5.0)
    threshold_request_adherence: float = Field(default=4.0, ge=1.0, le=5.0)
    threshold_age_appropriateness: float = Field(default=4.0, ge=1.0, le=5.0)
    threshold_emotional_safety: float = Field(default=4.0, ge=1.0, le=5.0)
    threshold_bedtime_quality: float = Field(default=4.0, ge=1.0, le=5.0)

    # --- Server ----------------------------------------------------------
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = Field(default="INFO")

    @property
    def evaluation_policy(self) -> dict[str, float]:
        """Metric -> minimum acceptable score.

        Note that ``story_quality`` and ``story_structure`` are scored and folded
        into the average but are deliberately not gated individually: a story can
        be a little plain and still be publishable, but it can never be unsafe or
        off-request.
        """
        return {
            "overall_score": self.threshold_overall,
            "request_adherence": self.threshold_request_adherence,
            "age_appropriateness": self.threshold_age_appropriateness,
            "emotional_safety": self.threshold_emotional_safety,
            "bedtime_quality": self.threshold_bedtime_quality,
        }

    @property
    def recursion_limit(self) -> int:
        """LangGraph step budget, derived from the revision budget.

        Worst case per run: plan + generate + (judge + threshold) * (n + 1)
        + refine * n + publish. The margin absorbs future node additions.
        """
        return 2 * (self.max_revisions + 1) + 6


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
