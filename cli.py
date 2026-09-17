"""Command-line entrypoint.

Runs interactively when no flags are given, and non-interactively when they are:

    python cli.py                                  # interactive prompts
    python cli.py --request "..." --style cozy     # non-interactive
    python cli.py --request "..." --debug          # plan + judge trace
    python cli.py --request "..." --json           # machine-readable output
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.core.exceptions import StoryAgentError
from app.core.logging import configure_logging
from app.schemas.api import DEFAULT_REQUEST, StoryResponse
from app.services.story_service import StoryService
from app.settings import get_settings
from app.styles import STYLES, StyleKey

RULE = "=" * 60


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Generate a bedtime story for children aged 5-10.",
    )
    parser.add_argument("--request", "-r", help="What the story should be about.")
    parser.add_argument(
        "--style",
        "-s",
        choices=[style.key.value for style in STYLES],
        help="Storytelling style (default: auto).",
    )
    parser.add_argument(
        "--max-revisions",
        type=int,
        help="Override the configured revision budget.",
    )
    parser.add_argument("--debug", action="store_true", help="Show the plan and judge trace.")
    parser.add_argument("--json", action="store_true", help="Emit the full result as JSON.")
    parser.add_argument(
        "--log-level",
        default="WARNING",
        help="Logging verbosity (default: WARNING, so the story stays readable).",
    )
    return parser.parse_args(argv)


def prompt_for_request() -> str:
    """Ask for the story request, falling back to the default prompt text."""
    entered = input(
        f"What kind of bedtime story do you want? (Default: {DEFAULT_REQUEST}) "
    ).strip()
    return entered or DEFAULT_REQUEST


def prompt_for_style() -> StyleKey:
    """Show the style menu and read a choice."""
    print("\nChoose a story style:")
    for index, style in enumerate(STYLES, start=1):
        print(f"{index}. {style.label}")

    choice = input("Style [default: Surprise me]: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(STYLES):
        return STYLES[int(choice) - 1].key
    return StyleKey.AUTO


def print_story(result: StoryResponse) -> None:
    """Print the published story."""
    print(f"\n{RULE}\nFINAL STORY\n{RULE}\n")
    print(result.story)


def print_debug(result: StoryResponse) -> None:
    """Print the plan and the full judge trace."""
    print(f"\n{RULE}\nDEBUG INFO\n{RULE}")

    print("\nSTORY PLAN:")
    print(json.dumps(result.plan.model_dump(), indent=2))

    print("\nJUDGE PASSES:")
    for item in result.history:
        marker = "  <- published" if item.iteration == result.published_iteration else ""
        print(f"\n  Pass {item.iteration}: {item.overall_score}/5 "
              f"({'passed' if item.passed else 'failed'}){marker}")
        for name, score in item.scores.items():
            print(f"    {name:<22} {score}")
        if item.safety_violations:
            print(f"    content flags: {', '.join(item.safety_violations)}")
        for note in item.feedback:
            print(f"    - {note}")

    card = result.scorecard
    print(f"\nFINAL SCORE:   {card.overall_score}/5  ({card.rating} stars)")
    print(f"Passed:        {card.passed}")
    print(f"Calming end:   {card.calming_ending_met}")
    print(f"Revisions:     {result.revisions_used} of {get_settings().max_revisions} allowed")
    print(f"Stopped after: {result.terminal_reason.value}")
    print(f"Elapsed:       {result.elapsed_seconds}s")


async def run(args: argparse.Namespace) -> int:
    """Generate one story and print it."""
    request = args.request or prompt_for_request()
    style = StyleKey(args.style) if args.style else (
        StyleKey.AUTO if args.request else prompt_for_style()
    )

    if not args.json:
        print("\nWriting your story. This takes a few moments...")

    try:
        result = await StoryService().generate(
            request=request,
            style=style,
            max_revisions=args.max_revisions,
        )
    except StoryAgentError as exc:
        print(f"\nError: {exc.user_message}", file=sys.stderr)
        print(f"Detail: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return 0

    print_story(result)
    if args.debug:
        print_debug(result)
    return 0


def main() -> int:
    """CLI entry point."""
    args = parse_args()
    configure_logging("DEBUG" if args.debug else args.log_level)
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
