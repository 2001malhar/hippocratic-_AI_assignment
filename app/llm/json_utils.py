"""Resilient JSON extraction for a model that predates structured outputs.

``gpt-3.5-turbo`` offers JSON mode but not ``json_schema``, so a well-formed
object is guaranteed and a correctly shaped one is not. Four layers close that
gap:

1. ``response_format: json_object`` on the request (set in ``client.py``)
2. fence stripping and brace-slicing here
3. one retry with stricter instructions
4. Pydantic validation at the call site
"""

from __future__ import annotations

import json
from typing import Any

from app.core.exceptions import JSONParseError
from app.core.logging import get_logger
from app.llm.client import LLMRole, invoke_text

logger = get_logger(__name__)

STRICT_JSON_SUFFIX = """

IMPORTANT OUTPUT REQUIREMENT:
Return exactly one valid JSON object.
Do not use Markdown code fences.
Do not include explanations.
Do not include text before or after the JSON object.
"""


def parse_json_response(raw_text: str) -> dict[str, Any]:
    """Parse JSON out of a model response.

    Handles plain JSON, fenced JSON, and JSON surrounded by a little prose.
    """
    cleaned = raw_text.strip()

    if cleaned.startswith("```"):
        cleaned = (
            cleaned.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
        )

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = None

    if parsed is None:
        # Fallback: slice out the outermost object from surrounding text.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and start < end:
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                parsed = None

    if parsed is None:
        raise JSONParseError("The model returned invalid JSON.", raw_response=raw_text)

    if not isinstance(parsed, dict):
        raise JSONParseError(
            f"Expected a JSON object, got {type(parsed).__name__}.", raw_response=raw_text
        )

    return parsed


async def invoke_json(role: LLMRole, system_prompt: str, prompt: str) -> dict[str, Any]:
    """Call the model expecting a JSON object, retrying once on a parse failure."""
    attempts = (prompt, prompt + STRICT_JSON_SUFFIX)
    last_error: JSONParseError | None = None

    for attempt_number, attempt_prompt in enumerate(attempts, start=1):
        raw = await invoke_text(role, system_prompt, attempt_prompt)
        try:
            return parse_json_response(raw)
        except JSONParseError as exc:
            last_error = exc
            logger.warning(
                "%s returned unparseable JSON on attempt %d/%d",
                role.value,
                attempt_number,
                len(attempts),
            )

    raise JSONParseError(
        f"The {role.value} model failed to return valid JSON after a retry.",
        raw_response=last_error.raw_response if last_error else "",
    ) from last_error
