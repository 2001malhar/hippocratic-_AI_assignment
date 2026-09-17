"""Graph assembly.

    START -> plan_story -> generate_story -> judge -> threshold_detector
                                               ^              |
                                               |   below      |  at/above threshold,
                                               |   threshold  |  or budget spent
                                               +--- refine <--+------> publish -> END

The gate sits immediately after the first judge pass, so a strong first draft is
published without paying for a refine round. ``refine`` always loops back
through ``judge``, so nothing is ever published unscored, and the detector's
budget check makes the cycle finite.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.logging import get_logger
from app.graph.nodes import (
    generate_story_node,
    judge_node,
    plan_story_node,
    publish_node,
    refine_node,
    threshold_detector_node,
)
from app.graph.routing import route_after_threshold
from app.graph.state import StoryState
from app.schemas.story import Decision

logger = get_logger(__name__)

# Node names, also used as the conditional-edge branch labels.
PLAN_STORY = "plan_story"
GENERATE_STORY = "generate_story"
JUDGE = "judge"
THRESHOLD_DETECTOR = "threshold_detector"
REFINE = "refine"
PUBLISH = "publish"


def build_graph() -> CompiledStateGraph:
    """Wire and compile the story graph.

    No checkpointer: a run is single-shot and stateless, so there is nothing to
    resume. Adding ``MemorySaver`` here is the only change needed if thread-based
    resumption is wanted later.
    """
    graph = StateGraph(StoryState)

    graph.add_node(PLAN_STORY, plan_story_node)
    graph.add_node(GENERATE_STORY, generate_story_node)
    graph.add_node(JUDGE, judge_node)
    graph.add_node(THRESHOLD_DETECTOR, threshold_detector_node)
    graph.add_node(REFINE, refine_node)
    graph.add_node(PUBLISH, publish_node)

    graph.add_edge(START, PLAN_STORY)
    graph.add_edge(PLAN_STORY, GENERATE_STORY)
    graph.add_edge(GENERATE_STORY, JUDGE)
    graph.add_edge(JUDGE, THRESHOLD_DETECTOR)

    graph.add_conditional_edges(
        THRESHOLD_DETECTOR,
        route_after_threshold,
        {
            Decision.PUBLISH.value: PUBLISH,
            Decision.REFINE.value: REFINE,
        },
    )

    # The revision cycle: refine never publishes directly, it re-enters the judge.
    graph.add_edge(REFINE, JUDGE)
    graph.add_edge(PUBLISH, END)

    compiled = graph.compile()
    logger.info("Story graph compiled with %d nodes", 6)
    return compiled


@lru_cache(maxsize=1)
def get_graph() -> CompiledStateGraph:
    """Return the process-wide compiled graph."""
    return build_graph()


def render_mermaid() -> str:
    """Render the graph as Mermaid. Handy for the README and for debugging.

    Mermaid rather than ASCII because ``draw_ascii`` needs the optional
    ``grandalf`` dependency and this does not.
    """
    return get_graph().get_graph().draw_mermaid()
