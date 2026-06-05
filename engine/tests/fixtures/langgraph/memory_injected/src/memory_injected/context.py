"""Runtime context."""

from dataclasses import dataclass, field

from . import prompts


@dataclass(kw_only=True)
class Context:
    user_id: str = "default"
    model: str = "anthropic/claude-sonnet-4-5"
    system_prompt: str = field(default=prompts.SYSTEM_PROMPT)
