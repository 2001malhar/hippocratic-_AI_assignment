"""The storytelling style catalogue.

One source of truth shared by the API, the Gradio dropdown and the CLI menu, so
the three interfaces can never drift apart. Each style pairs a stable key with a
display label and the description interpolated into the prompts.
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple

# What the planner/storyteller prompts receive when the user picks "surprise me".
AUTO_STYLE_DESCRIPTION = "choose the style that best fits the request"


class StyleKey(str, Enum):
    """Stable identifiers used by the API and the UI."""

    COZY = "cozy"
    FUNNY = "funny"
    MAGICAL = "magical"
    ADVENTURE = "adventure"
    AUTO = "auto"


class Style(NamedTuple):
    """A selectable style and the prompt fragment it expands to."""

    key: StyleKey
    label: str
    description: str


STYLES: tuple[Style, ...] = (
    Style(StyleKey.COZY, "Cozy", "cozy and gentle"),
    Style(StyleKey.FUNNY, "Funny", "playful and funny"),
    Style(StyleKey.MAGICAL, "Magical", "magical and imaginative"),
    Style(StyleKey.ADVENTURE, "Adventure", "adventurous but bedtime-friendly"),
    Style(StyleKey.AUTO, "Surprise me", AUTO_STYLE_DESCRIPTION),
)

_BY_KEY: dict[StyleKey, Style] = {style.key: style for style in STYLES}
_BY_LABEL: dict[str, Style] = {style.label.casefold(): style for style in STYLES}

DEFAULT_STYLE: StyleKey = StyleKey.AUTO


def describe(key: StyleKey | str | None) -> str:
    """Expand a style key into the prompt fragment for it.

    Unknown or missing input falls back to the auto description, so a stray
    value from any interface resolves to something usable.
    """
    if key is None:
        return AUTO_STYLE_DESCRIPTION
    if isinstance(key, StyleKey):
        return _BY_KEY[key].description

    candidate = key.strip()
    if not candidate:
        return AUTO_STYLE_DESCRIPTION

    try:
        return _BY_KEY[StyleKey(candidate.casefold())].description
    except (KeyError, ValueError):
        pass

    matched = _BY_LABEL.get(candidate.casefold())
    return matched.description if matched else AUTO_STYLE_DESCRIPTION


def labels() -> list[str]:
    """Human-readable labels, for dropdowns and menus."""
    return [style.label for style in STYLES]


def key_for_label(label: str) -> StyleKey:
    """Map a display label back to its key."""
    matched = _BY_LABEL.get(label.strip().casefold())
    return matched.key if matched else DEFAULT_STYLE
