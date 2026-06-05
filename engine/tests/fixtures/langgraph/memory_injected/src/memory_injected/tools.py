"""Memory tool with framework-injected arguments hidden from the model."""

import uuid
from typing import Annotated

from langchain_core.tools import InjectedToolArg
from langgraph.store.base import BaseStore


async def upsert_memory(
    content: str,
    context: str,
    *,
    memory_id: uuid.UUID | None = None,
    # These are injected by the framework and MUST NOT appear in the schema.
    user_id: Annotated[str, InjectedToolArg],
    store: Annotated[BaseStore, InjectedToolArg],
):
    """Upsert a memory in the database.

    If a memory conflicts with an existing one, update it by passing memory_id.

    Args:
        content: The main content of the memory.
        context: Additional context for the memory.
        memory_id: ONLY provide when updating an existing memory.
    """
    mem_id = memory_id or uuid.uuid4()
    return f"stored {mem_id}"
