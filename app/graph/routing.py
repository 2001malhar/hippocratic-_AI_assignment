"""Conditional edges.

The decision itself is made in the ``threshold_detector`` node so it lands in
state and in the trace; this is just the lookup LangGraph needs to pick a branch.
"""

from __future__ import annotations

from app.graph.state import StoryState
from app.schemas.story import Decision


def route_after_threshold(state: StoryState) -> str:
    """Return the next node name after the threshold detector.

    Defaults to publishing: if the decision is somehow missing, ending the run
    with the best draft is strictly safer than looping.
    """
    return state.get("decision", Decision.PUBLISH.value)
