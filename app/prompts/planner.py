"""Planner prompt: turn a free-text request into a compact structured plan."""

from __future__ import annotations

import json

SYSTEM = """
You are a careful planner for children's bedtime stories.

Your task is to convert a user's request into a short structured plan
for a bedtime story appropriate for children ages 5 to 10.

The plan should improve consistency and story structure without becoming elaborate.

Do not write the full story.

Return valid JSON only.
"""


def build_prompt(user_request: str, style: str) -> str:
    """Render the planner user prompt."""
    return f"""
User request:
"{user_request}"

Requested style:
"{style}"

Create a short JSON story plan using exactly these keys:

{{
    "category": "one short category such as animal_adventure, fantasy, friendship, everyday_life, or bedtime_magic",
    "target_age": "a reasonable age range within ages 5 to 10",
    "characters": ["2 to 4 important characters"],
    "setting": "short description of where the story happens",
    "tone": "short description matching the requested style",
    "story_arc": [
        "setup",
        "mild problem",
        "meaningful action taken by the characters",
        "resolution"
    ],
    "lesson": "a subtle lesson or kindness theme",
    "bedtime_ending": "short note describing how the story becomes calm and reassuring"
}}

Planning guidelines:
- Follow all important details in the user's request.
- Keep the plan concise.
- Give the main character something meaningful to do.
- Use a mild, age-appropriate challenge.
- Mild worry or suspense is allowed.
- Avoid graphic violence, cruelty, intense fear, death, or unresolved distress.
- The ending should feel warm, emotionally complete, and suitable for bedtime.
- The lesson should emerge naturally rather than feel preachy.

Return JSON only.
"""


def build_repair_prompt(user_request: str, style: str, errors: str) -> str:
    """Re-ask the planner after a schema validation failure.

    Naming the exact broken fields recovers far more often than simply retrying
    the original prompt.
    """
    return build_prompt(user_request, style) + f"""

Your previous response did not match the required schema.

Validation errors:
{errors}

Return one JSON object with all eight keys spelled exactly as shown above.
"characters" and "story_arc" must be JSON arrays of strings.
Return JSON only.
"""


def format_plan(plan: dict) -> str:
    """Render a plan for inclusion in downstream prompts."""
    return json.dumps(plan, indent=2)
