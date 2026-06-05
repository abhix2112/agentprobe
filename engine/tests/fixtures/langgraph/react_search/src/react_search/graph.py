"""A ReAct-style research agent built on StateGraph."""

from typing import Dict, List, Literal

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime

from react_search.context import Context
from react_search.state import InputState, State
from react_search.tools import TOOLS
from react_search.utils import load_chat_model


async def call_model(state: State, runtime: Runtime[Context]) -> Dict[str, List[AIMessage]]:
    """Call the LLM, binding the research tools."""
    model = load_chat_model(runtime.context.model).bind_tools(TOOLS)
    system_message = runtime.context.system_prompt.format(system_time="now")
    response = await model.ainvoke(
        [{"role": "system", "content": system_message}, *state.messages]
    )
    return {"messages": [response]}


def route_model_output(state: State) -> Literal["__end__", "tools"]:
    last_message = state.messages[-1]
    if not last_message.tool_calls:
        return "__end__"
    return "tools"


builder = StateGraph(State, input_schema=InputState, context_schema=Context)
builder.add_node(call_model)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_edge("__start__", "call_model")
builder.add_conditional_edges("call_model", route_model_output)
builder.add_edge("tools", "call_model")

graph = builder.compile(name="ReAct Research Agent")
