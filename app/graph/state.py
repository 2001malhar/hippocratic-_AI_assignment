"""The state carried through the story graph.

Models are stored as dicts rather than as Pydantic instances because LangGraph
serialises state between steps; validation happens at the node boundary, and
``app.graph.helpers`` converts back when a node needs the typed object.

Only ``history`` needs a reducer -- each judge pass appends one record, so the
full revision trail survives the loop. Every other key is last-write-wins.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class StoryState(TypedDict, total=False):
    """Everything the graph reads and writes."""

    # --- Inputs (set once, before the graph runs) ------------------------
    run_id: str
    user_request: str
    style: str
    max_revisions: int

    # --- Working values --------------------------------------------------
    plan: dict[str, Any]
    story: str
    scorecard: dict[str, Any]
    feedback: list[str]

    # --- Loop bookkeeping -------------------------------------------------
    iteration: int
    revisions_used: int
    history: Annotated[list[dict[str, Any]], operator.add]

    # --- Best draft seen so far ------------------------------------------
    # Tracked so the exhausted-revisions path publishes the strongest draft
    # rather than whatever the final refine happened to produce.
    best_story: str
    best_scorecard: dict[str, Any]
    best_iteration: int

    # --- Routing and output ------------------------------------------------
    decision: str
    terminal_reason: str
    published_story: str
    published_title: str


def initial_state(
    run_id: str,
    user_request: str,
    style: str,
    max_revisions: int,
) -> StoryState:
    """Build the starting state for one run."""
    return StoryState(
        run_id=run_id,
        user_request=user_request,
        style=style,
        max_revisions=max_revisions,
        iteration=0,
        revisions_used=0,
        history=[],
        feedback=[],
    )
