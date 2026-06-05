"""A single-file prebuilt ReAct agent using create_react_agent + @tool."""

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from .model import load_model

SYSTEM_PROMPT = "You are a precise calculator. Show each step of your work."


@tool
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


@tool("multiply", description="Multiply two numbers together.")
def multiply(a: float, b: float) -> float:
    return a * b


@tool
def power(base: float, exponent: int = 2) -> float:
    """Raise base to the given exponent (defaults to squaring)."""
    return base ** exponent


graph = create_react_agent(
    load_model(),
    tools=[add, multiply, power],
    prompt=SYSTEM_PROMPT,
)
