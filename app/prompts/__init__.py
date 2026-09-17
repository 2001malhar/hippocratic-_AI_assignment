"""Prompt templates, one module per pipeline role.

Kept as Python modules rather than external text files: the prompts already rely
on interpolation, this keeps them type-checked and importable with no loader or
packaging-data concerns, and each one sits next to the node that uses it.
"""

from app.prompts import judge, planner, reviser, storyteller

__all__ = ["judge", "planner", "reviser", "storyteller"]
