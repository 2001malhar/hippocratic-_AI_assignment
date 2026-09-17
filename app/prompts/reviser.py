"""Reviser prompt: apply judge feedback without rewriting the story."""

from __future__ import annotations

from collections.abc import Sequence

from app.prompts.planner import format_plan

SYSTEM = """
You are an expert editor for children's bedtime stories.

Revise the story based on evaluator feedback.

Preserve everything that already works well.
Do not rewrite sections unnecessarily.

Keep the original characters, story identity, and user intent unless
the feedback specifically requires a change.

The revised story should feel like a better version of the same story,
not a completely different story.

Return only the revised title and story.
"""


def _bullets(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def build_prompt(
    user_request: str,
    style: str,
    plan: dict,
    story: str,
    feedback: Sequence[str],
    safety_violations: Sequence[str] = (),
    calming_ending_met: bool = True,
) -> str:
    """Render the reviser user prompt.

    Safety violations and a failed calming-ending check are surfaced as their own
    mandatory sections rather than being folded into the feedback list, because
    they are the two things a revision is not allowed to leave unfixed.
    """
    sections = [
        f"""
Original user request:
"{user_request}"

Requested style:
"{style}"

Story plan:
{format_plan(plan)}

Current story:
--- STORY START ---
{story}
--- STORY END ---

Evaluator feedback:
{_bullets(feedback) if feedback else "- No specific notes were provided; improve the weakest areas."}
"""
    ]

    if safety_violations:
        sections.append(
            f"""
MANDATORY SAFETY CORRECTIONS

A parental-controls review flagged this story for:
{_bullets(safety_violations)}

You must remove this content entirely. Do not soften it, imply it, or move it
offstage. Rework the plot as needed so the flagged element never occurs.
"""
        )

    if not calming_ending_met:
        sections.append(
            """
MANDATORY ENDING CORRECTION

The ending is not calm enough for bedtime. Rewrite the final two paragraphs so
the pace slows, the characters come to rest somewhere safe and warm, and the
last sentence leaves the listener settled and sleepy.
"""
        )

    sections.append(
        """
Revise the story.

Requirements:
- Preserve strong parts of the current version.
- Address each useful feedback item.
- Continue following the original request.
- Preserve the main characters and core idea.
- Keep the language suitable for ages 5 to 10.
- Improve engagement without making the story overstimulating.
- Keep any challenge mild and emotionally safe.
- Avoid graphic violence, cruelty, intense fear, death, or unresolved distress.
- Maintain a clear story arc.
- Keep the requested style.
- End peacefully and reassuringly.
- Return only the title and revised story.
"""
    )

    return "\n".join(sections)
