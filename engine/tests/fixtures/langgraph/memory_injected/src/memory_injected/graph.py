"""Memory-extracting agent. Tools are bound inline (no module TOOLS list)."""

from langgraph.graph import END, StateGraph
from langgraph.runtime import Runtime

from memory_injected import tools, utils
from memory_injected.context import Context
from memory_injected.state import State


async def call_model(state: State, runtime: Runtime[Context]) -> dict:
    system_prompt = runtime.context.system_prompt
    llm = utils.load_chat_model(runtime.context.model)
    sys = system_prompt.format(user_info="", time="now")
    # Inline list passed directly to bind_tools — references tools.upsert_memory.
    msg = await llm.bind_tools([tools.upsert_memory]).ainvoke(
        [{"role": "system", "content": sys}, *state.messages]
    )
    return {"messages": [msg]}


def route_message(state: State):
    if getattr(state.messages[-1], "tool_calls", None):
        return "store_memory"
    return END


builder = StateGraph(State, context_schema=Context)
builder.add_node(call_model)
builder.add_edge("__start__", "call_model")
builder.add_conditional_edges("call_model", route_message, ["store_memory", END])
graph = builder.compile()
graph.name = "MemoryAgent"
