"""Claude Agent SDK — file operations agent with full JSON-schema tools."""

from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server, tool

from .prompts import ASSISTANT_SYSTEM_PROMPT


@tool(
    "read_file",
    "Read a UTF-8 text file from the workspace",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Workspace-relative path"},
        },
        "required": ["path"],
    },
)
async def read_file(args):
    return {"content": [{"type": "text", "text": "..."}]}


@tool(
    "write_file",
    "Write text to a file in the workspace",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "contents": {"type": "string"},
            "overwrite": {"type": "boolean"},
        },
        "required": ["path", "contents"],
    },
)
async def write_file(args):
    return {"content": [{"type": "text", "text": "ok"}]}


fs_server = create_sdk_mcp_server(name="fs", version="0.1.0", tools=[read_file, write_file])

options = ClaudeAgentOptions(
    system_prompt=ASSISTANT_SYSTEM_PROMPT,
    mcp_servers={"fs": fs_server},
    allowed_tools=["mcp__fs__read_file", "mcp__fs__write_file"],
)
