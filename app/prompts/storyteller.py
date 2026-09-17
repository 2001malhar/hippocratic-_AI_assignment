"""Storyteller prompt: write the first full draft from the plan."""

from __future__ import annotations

from app.prompts.planner import format_plan

SYSTEM = """
You are a gifted children's bedtime storyteller.

Write stories for children ages 5 to 10 that are imaginative, warm,
easy to follow, and pleasant to hear aloud.

A strong story should:
- hook the child quickly
- establish memorable characters
- introduce a clear but mild problem
- give the main character agency
- include concrete imagery and natural dialogue
- build toward a satisfying resolution
- gradually reduce emotional intensity near the end
- finish with a peaceful, reassuring bedtime feeling

Avoid writing that feels generic, repetitive, or overly moralizing.

Return only the title and story.
"""


def build_prompt(user_request: str, style: str, plan: dict) -> str:
    """Render the storyteller user prompt."""
    return f"""
Original user request:
"{user_request}"

Requested style:
"{style}"

Story plan:
{format_plan(plan)}

Write a complete bedtime story that follows both the original request
and the story plan.

Requirements:
- Appropriate for children ages 5 to 10.
- Aim for approximately 400 to 700 words.
- Put a short title on the first line.
- Use simple but vivid language.
- Include a clear beginning, middle, and ending.
- Give the main character meaningful choices or actions.
- Include at least a small amount of sensory detail or dialogue.
- Use a mild challenge that creates interest without becoming frightening.
- Mild suspense or worry is allowed when age appropriate.
- Avoid graphic violence, cruelty, intense fear, death, or unresolved distress.
- Resolve the challenge clearly and kindly.
- Do not force a moral into the story.
- Gradually make the final section quieter and calmer.
- End with a warm, comforting final paragraph suitable for bedtime.
- Follow the requested style consistently.

Return only the title and story.
"""
