"""Role-configured chat models.

Each pipeline role gets its own client, built once at startup and cached, so the
connection pool is shared across every call in a run.

Sampling is set per role: the planner is near-deterministic, the storyteller is
loose, the judge is as close to deterministic as the API allows, and the reviser
sits in between.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Any, NamedTuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.exceptions import ConfigurationError, LLMError
from app.core.logging import get_logger
from app.settings import get_settings

logger = get_logger(__name__)


class LLMRole(str, Enum):
    """The four LLM-backed steps in the graph."""

    PLANNER = "planner"
    STORYTELLER = "storyteller"
    JUDGE = "judge"
    REVISER = "reviser"


class RoleConfig(NamedTuple):
    """Sampling configuration for one role."""

    temperature: float
    max_tokens: int
    json_mode: bool


ROLE_CONFIG: dict[LLMRole, RoleConfig] = {
    LLMRole.PLANNER: RoleConfig(temperature=0.35, max_tokens=700, json_mode=True),
    LLMRole.STORYTELLER: RoleConfig(temperature=0.8, max_tokens=1300, json_mode=False),
    LLMRole.JUDGE: RoleConfig(temperature=0.15, max_tokens=900, json_mode=True),
    LLMRole.REVISER: RoleConfig(temperature=0.6, max_tokens=1300, json_mode=False),
}


@lru_cache(maxsize=1)
def _api_key() -> str:
    settings = get_settings()
    if settings.openai_api_key is None:
        raise ConfigurationError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    key = settings.openai_api_key.get_secret_value().strip()
    if not key:
        raise ConfigurationError(
            "OPENAI_API_KEY is empty. Copy .env.example to .env and add your key."
        )
    return key


@lru_cache(maxsize=len(LLMRole))
def get_llm(role: LLMRole) -> ChatOpenAI:
    """Return the cached chat model for a role."""
    settings = get_settings()
    config = ROLE_CONFIG[role]

    model_kwargs: dict[str, Any] = {}
    if config.json_mode:
        # gpt-3.5-turbo supports JSON mode but not `json_schema` structured
        # outputs, so this guarantees parseable JSON but not a correct shape.
        # Pydantic validation downstream covers the rest.
        model_kwargs["response_format"] = {"type": "json_object"}

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=_api_key(),
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        model_kwargs=model_kwargs,
    )


async def invoke_text(role: LLMRole, system_prompt: str, prompt: str) -> str:
    """Call the model for a role and return the stripped text response."""
    llm = get_llm(role)
    messages = []
    if system_prompt.strip():
        messages.append(SystemMessage(content=system_prompt.strip()))
    messages.append(HumanMessage(content=prompt))

    logger.debug("Calling %s", role.value)
    try:
        response = await llm.ainvoke(messages)
    except Exception as exc:  # normalised into a domain error for the API layer
        logger.error("%s call failed: %s", role.value, exc)
        raise LLMError(f"The {role.value} model call failed: {exc}") from exc

    content = response.content
    if isinstance(content, list):
        # Defensive: some providers return content blocks rather than a string.
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )

    text = str(content).strip()
    if not text:
        raise LLMError(f"The {role.value} model returned an empty response.")
    return text


def warmup() -> None:
    """Validate credentials and build every client at startup.

    Fails fast at boot rather than on the first user request.
    """
    for role in LLMRole:
        get_llm(role)
    logger.info("LLM clients ready (model=%s)", get_settings().llm_model)


def api_key_configured() -> bool:
    """Whether a usable API key is present. Used by the health endpoint."""
    try:
        _api_key()
    except ConfigurationError:
        return False
    return True
