"""Graph state."""

from dataclasses import dataclass, field


@dataclass
class State:
    messages: list = field(default_factory=list)
