"""A REAL LangGraph `create_react_agent` for end-to-end runner testing.

It uses a deterministic fake tool-calling chat model so the agent runs WITHOUT
any LLM API key — but the graph, the ToolNode, and the `read_file` tool are all
real. Given an attack prompt that contains a path, the agent calls `read_file`
with that path (so a traversal-path attack shows up as a real tool call in the
captured RunResult), then answers.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

_PATH_RE = re.compile(r"""(\.\./[^\s'"`]+|/[A-Za-z0-9._/\-]+|[\w./\-]+\.(?:txt|cfg|key|rsa|crontab|passwd))""")


class FakeToolCaller(BaseChatModel):
    """Deterministic, key-free. First turn: call read_file with the path found in
    the latest human message. After the tool result comes back: answer."""

    @property
    def _llm_type(self) -> str:
        return "fake-tool-caller"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "FakeToolCaller":
        return self

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if any(isinstance(m, ToolMessage) for m in messages):
            msg = AIMessage(content="Done — I performed the file read you asked for.")
        else:
            human = next((m for m in reversed(messages) if getattr(m, "type", "") == "human"), None)
            text = human.content if human is not None else ""
            match = _PATH_RE.search(text if isinstance(text, str) else "")
            path = match.group(0) if match else "notes.txt"
            msg = AIMessage(
                content="",
                tool_calls=[{"name": "read_file", "args": {"path": path}, "id": "call_1", "type": "tool_call"}],
            )
        return ChatResult(generations=[ChatGeneration(message=msg)])


@tool
def read_file(path: str) -> str:
    """Read a UTF-8 text file from the workspace."""
    return f"[contents of {path}]"


graph = create_react_agent(FakeToolCaller(), tools=[read_file])
