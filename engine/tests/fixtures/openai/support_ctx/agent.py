"""OpenAI Agents SDK — customer support agent.

instructions is sourced from a module constant (common in real repos).
"""

from agents import Agent

from .tools import lookup_order, refund

SUPPORT_INSTRUCTIONS = (
    "You are a customer support agent for an e-commerce store. "
    "Verify the customer's identity before issuing refunds. "
    "Never refund more than the original order amount."
)

support_agent = Agent(
    name="Support Agent",
    instructions=SUPPORT_INSTRUCTIONS,
    tools=[lookup_order, refund],
)
