"""Runtime context (configurable fields) for the react search agent."""

from dataclasses import dataclass, field

from . import prompts


@dataclass(kw_only=True)
class Context:
    """Configurable parameters for the agent."""

    system_prompt: str = field(
        default=prompts.SYSTEM_PROMPT,
        metadata={"description": "The system prompt for the agent."},
    )
    model: str = field(default="anthropic/claude-sonnet-4-5")
    max_search_results: int = field(default=10)
