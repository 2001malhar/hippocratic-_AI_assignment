"""Domain exception hierarchy.

The API layer maps each of these to an HTTP status, which is why they exist as
distinct types rather than as bare ``ValueError``s. Each carries both the status
and a message that is safe to show a caller.
"""

from __future__ import annotations


class StoryAgentError(Exception):
    """Base class for every error raised by this application."""

    http_status: int = 500
    user_message: str = "The story agent hit an unexpected problem."


class ConfigurationError(StoryAgentError):
    """Something required to run is missing or malformed (e.g. no API key)."""

    http_status = 500
    user_message = "The story agent is not configured correctly."


class LLMError(StoryAgentError):
    """The model could not be reached, timed out, or refused the request."""

    http_status = 503
    user_message = "The language model is unavailable right now. Please try again."


class JSONParseError(StoryAgentError):
    """The model returned something that is not recoverable as JSON."""

    http_status = 502
    user_message = "The language model returned malformed output."

    def __init__(self, message: str, raw_response: str = "") -> None:
        super().__init__(message)
        self.raw_response = raw_response


class PlanValidationError(StoryAgentError):
    """The planner produced JSON that does not match the story-plan schema."""

    http_status = 502
    user_message = "The story planner returned an unusable plan."


class JudgeValidationError(StoryAgentError):
    """The judge produced JSON that does not match the verdict schema."""

    http_status = 502
    user_message = "The story judge returned an unusable evaluation."
