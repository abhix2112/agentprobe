"""Claude Agent SDK — calculator with shorthand tool schemas."""

from claude_agent_sdk import (
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    tool,
)


@tool("add", "Add two numbers and return the sum", {"a": float, "b": float})
async def add(args):
    return {"content": [{"type": "text", "text": str(args["a"] + args["b"])}]}


@tool("divide", "Divide a by b", {"a": float, "b": float})
async def divide(args):
    return {"content": [{"type": "text", "text": str(args["a"] / args["b"])}]}


calc_server = create_sdk_mcp_server(name="calc", version="1.0.0", tools=[add, divide])

options = ClaudeAgentOptions(
    system_prompt="You are a calculator assistant. Only do arithmetic the user asks for.",
    mcp_servers={"calc": calc_server},
    allowed_tools=["mcp__calc__add", "mcp__calc__divide"],
)
