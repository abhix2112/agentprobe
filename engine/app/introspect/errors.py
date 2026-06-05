"""Introspection errors."""

from __future__ import annotations


class AgentNotFound(Exception):
    """Raised when no agent could be statically located in a repo.

    The orchestrator surfaces this as HTTP 422 so the user can specify the
    entry file rather than the engine guessing.
    """

    def __init__(self, message: str, framework: str | None = None) -> None:
        self.message = message
        self.framework = framework
        super().__init__(message)
