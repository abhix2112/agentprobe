"""Graph state."""

from dataclasses import dataclass, field


@dataclass
class InputState:
    messages: list = field(default_factory=list)


@dataclass
class State(InputState):
    is_last_step: bool = False
