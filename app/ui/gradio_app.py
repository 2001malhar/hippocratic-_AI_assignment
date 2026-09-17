"""Gradio UI, mounted onto the same FastAPI app at ``/ui``.

The UI calls ``StoryService`` directly in-process rather than going back out
over HTTP to its own server: a self-request from inside the same event loop is a
pointless round trip and, on a single worker, a deadlock risk.
"""

from __future__ import annotations

import gradio as gr

from app.core.exceptions import StoryAgentError
from app.core.logging import get_logger
from app.graph.nodes.publish import split_title
from app.schemas.api import DEFAULT_REQUEST, StoryResponse
from app.services.story_service import StoryService
from app.styles import DEFAULT_STYLE, STYLES, key_for_label, labels

logger = get_logger(__name__)

EXAMPLES = [
    ["A tiny fox helps a lost bunny in a moonlit garden.", "Cozy"],
    ["A sleepy dragon who cannot find his favourite blanket.", "Funny"],
    ["Two sisters plant a garden that grows starlight.", "Magical"],
    ["A young otter learns to swim across the wide river.", "Adventure"],
]

CSS = """
.story-output textarea { font-size: 1.05rem; line-height: 1.7; }
footer { display: none !important; }
"""


def build_blocks(service: StoryService | None = None) -> gr.Blocks:
    """Construct the Gradio interface."""
    service = service or StoryService()

    async def on_generate(
        request: str,
        style_label: str,
        max_revisions: int,
        progress: gr.Progress = gr.Progress(),
    ):
        """Generate a story and populate every output panel."""
        if not request or not request.strip():
            raise gr.Error("Please describe the bedtime story you want.")

        progress(0.1, desc="Planning the story...")
        try:
            result = await service.generate(
                request=request,
                style=key_for_label(style_label),
                max_revisions=int(max_revisions),
            )
        except StoryAgentError as exc:
            logger.error("Generation failed: %s", exc)
            raise gr.Error(exc.user_message) from exc

        progress(1.0, desc="Done")
        return (
            f"## {result.title}",
            _body_of(result),
            _summary_markdown(result),
            result.plan.model_dump(),
            _history_rows(result),
            _feedback_markdown(result),
            result.model_dump(mode="json"),
        )

    with gr.Blocks(title="Bedtime Story Agent", theme=gr.themes.Soft(), css=CSS) as blocks:
        gr.Markdown(
            """
            # 🌙 Bedtime Story Agent

            Stories for ages 5-10, written by a LangGraph pipeline that plans,
            writes, judges and revises until the story clears a strict safety and
            bedtime-quality bar.
            """
        )

        with gr.Row():
            with gr.Column(scale=2):
                request_box = gr.Textbox(
                    label="What kind of bedtime story do you want?",
                    placeholder=DEFAULT_REQUEST,
                    value=DEFAULT_REQUEST,
                    lines=3,
                )
                with gr.Row():
                    style_dropdown = gr.Dropdown(
                        choices=labels(),
                        value=_label_for(DEFAULT_STYLE),
                        label="Style",
                    )
                    revisions_slider = gr.Slider(
                        minimum=0,
                        maximum=5,
                        value=2,
                        step=1,
                        label="Max revisions",
                        info="How many times the judge may send the story back.",
                    )
                generate_button = gr.Button("Generate story", variant="primary", size="lg")
                gr.Examples(examples=EXAMPLES, inputs=[request_box, style_dropdown])

            with gr.Column(scale=3):
                title_output = gr.Markdown()
                story_output = gr.Textbox(
                    label="Story",
                    lines=22,
                    show_copy_button=True,
                    elem_classes="story-output",
                )
                summary_output = gr.Markdown()

        with gr.Accordion("Debug / trace", open=False):
            gr.Markdown(
                "Everything the pipeline produced along the way: the plan, every "
                "judge pass, and the raw response payload."
            )
            plan_output = gr.JSON(label="Story plan")
            history_output = gr.Dataframe(
                headers=["Pass", "Overall", "Passed", "Adherence", "Age", "Quality",
                         "Structure", "Safety", "Bedtime", "Violations"],
                label="Judge passes",
                wrap=True,
            )
            feedback_output = gr.Markdown()
            raw_output = gr.JSON(label="Full response")

        generate_button.click(
            fn=on_generate,
            inputs=[request_box, style_dropdown, revisions_slider],
            outputs=[
                title_output,
                story_output,
                summary_output,
                plan_output,
                history_output,
                feedback_output,
                raw_output,
            ],
            api_name="generate_story",
        )

    return blocks


# --- Presentation helpers -------------------------------------------------


def _label_for(key) -> str:
    return next(style.label for style in STYLES if style.key == key)


def _body_of(result: StoryResponse) -> str:
    """Strip the title line off, since it is rendered separately.

    Reuses the publish node's parser so the UI and the API can never disagree
    about where the title ends.
    """
    return split_title(result.story)[1]


def _summary_markdown(result: StoryResponse) -> str:
    card = result.scorecard
    stars = "⭐" * card.rating + "☆" * (5 - card.rating)
    verdict = "✅ Passed the quality bar" if card.passed else "⚠️ Published best available draft"
    reason = result.terminal_reason.value.replace("_", " ")

    lines = [
        f"### {stars} &nbsp; {card.overall_score} / 5",
        f"**{verdict}** — {reason} after {result.judge_passes} judge "
        f"pass{'es' if result.judge_passes != 1 else ''} "
        f"and {result.revisions_used} revision{'s' if result.revisions_used != 1 else ''} "
        f"({result.elapsed_seconds}s).",
    ]

    if card.safety_violations:
        lines.append(f"**⚠️ Content flags:** {', '.join(card.safety_violations)}")
    if card.failed_metrics:
        lines.append(f"**Below threshold:** {', '.join(card.failed_metrics)}")
    if not card.calming_ending_met:
        lines.append("**Note:** the judge did not consider the ending fully calming.")

    return "\n\n".join(lines)


def _history_rows(result: StoryResponse) -> list[list]:
    return [
        [
            item.iteration,
            item.overall_score,
            "yes" if item.passed else "no",
            item.scores["request_adherence"],
            item.scores["age_appropriateness"],
            item.scores["story_quality"],
            item.scores["story_structure"],
            item.scores["emotional_safety"],
            item.scores["bedtime_quality"],
            ", ".join(item.safety_violations) or "-",
        ]
        for item in result.history
    ]


def _feedback_markdown(result: StoryResponse) -> str:
    sections = [
        f"**Published draft:** judge pass {result.published_iteration} "
        f"(the highest-scoring version produced).",
        "",
    ]
    for item in result.history:
        marker = " ← published" if item.iteration == result.published_iteration else ""
        sections.append(f"**Judge pass {item.iteration}** — {item.overall_score}/5{marker}")
        sections.extend(f"- {note}" for note in item.feedback)
        sections.append("")
    return "\n".join(sections)
