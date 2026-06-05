"""Support tools. The leading RunContextWrapper arg is framework-injected."""

from dataclasses import dataclass

from agents import RunContextWrapper, function_tool


@dataclass
class SupportContext:
    user_id: str


@function_tool
def lookup_order(ctx: RunContextWrapper[SupportContext], order_id: str) -> str:
    """Look up the status of an order by its ID."""
    return f"order {order_id} for {ctx.context.user_id}"


@function_tool(name_override="issue_refund")
def refund(ctx: RunContextWrapper[SupportContext], order_id: str, amount: float) -> str:
    """Issue a refund for an order."""
    return "refunded"
