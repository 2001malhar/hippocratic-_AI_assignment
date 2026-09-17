"""Node 6 (deterministic): finalise and emit the story.

No LLM call and no persistence -- the run ends by logging the story and placing
it, with its title split out, into the terminal state for the API and the UI to
read. A future version could write to a store here without touching any other
node.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.graph.state import StoryState
from app.schemas.story import ScoreCard, TerminalReason

logger = get_logger(__name__)


async def publish_node(state: StoryState) -> dict:
    """Publish the best draft produced during the run."""
    # `best_*` is always populated by the threshold detector, which runs before
    # every route into this node; the fallbacks are belt and braces.
    story = state.get("best_story") or state["story"]
    scorecard_raw = state.get("best_scorecard") or state["scorecard"]
    scorecard = ScoreCard.model_validate(scorecard_raw)

    title, _body = split_title(story)
    reason = state.get("terminal_reason", TerminalReason.PASSED_THRESHOLD.value)

    logger.info(
        "Published %r (rating=%d/5, overall=%.2f, reason=%s, revisions=%d)",
        title,
        scorecard.rating,
        scorecard.overall_score,
        reason,
        state.get("revisions_used", 0),
    )
    logger.debug("Final story:\n%s", story)

    return {
        "published_story": story,
        "published_title": title,
        "scorecard": scorecard.model_dump(),
        # Surface the published draft's story as the canonical one so any
        # consumer reading `story` gets the same text that was published.
        "story": story,
        "terminal_reason": reason,
    }


#: Prefixes the model prepends to the title line despite being told not to.
_TITLE_PREFIXES = ("title:", "story title:", "**title:**", "#")

#: Wrapping characters to peel off a title line. The curly quotes are
#: deliberate -- the model emits them as often as the straight ones.
_TITLE_WRAPPERS = '"\'*_#`“”‘’ \t'  # noqa: RUF001


def _clean_title_line(line: str) -> str:
    """Strip decoration off a candidate title line.

    Peel wrappers, drop any "Title:" label, then peel again -- the label turns
    up both inside the wrappers (``**Title:** "Name"``) and outside them
    (``**Title: Name**``). Returns "" if the line was nothing but decoration.
    """
    title = line.strip()
    for _ in range(2):
        title = title.strip(_TITLE_WRAPPERS)
        lowered = title.lower()
        for prefix in _TITLE_PREFIXES:
            if lowered.startswith(prefix):
                title = title[len(prefix) :]
                break
    return title.strip(_TITLE_WRAPPERS)


def split_title(story: str) -> tuple[str, str]:
    """Split the title off the top of the story, per the storyteller's contract.

    ``gpt-3.5-turbo`` decorates the title line in several ways despite the
    instruction: ``# Title``, ``Title: Name``, ``**Title:** "Name"``, and
    sometimes a bare ``**Title:**`` label with the actual title on the next
    line. A line that is pure decoration is skipped rather than published as
    "Untitled Story".
    """
    lines = story.strip().splitlines()

    for index, line in enumerate(lines):
        if not line.strip():
            continue

        title = _clean_title_line(line)
        if not title:
            # A bare label such as "**Title:**"; the real title is below it.
            continue

        # A "title" that runs on is really the opening sentence: keep the whole
        # story as the body rather than silently eating its first line.
        if len(title) > 120:
            return title[:117].rstrip() + "...", story

        body = "\n".join(lines[index + 1 :]).strip()
        return title, body or story

    return "Untitled Story", story
