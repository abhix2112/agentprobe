"""Example tools for the research agent (bare functions in a TOOLS list)."""

from typing import Any, Callable, List, Optional


async def search(query: str, max_results: Optional[int] = None) -> dict[str, Any]:
    """Search for general web results.

    Performs a web search and returns a structured list of results. Useful for
    answering questions about current events.
    """
    return {"query": query, "results": []}


async def fetch_url(url: str) -> str:
    """Fetch the raw text content at a URL."""
    return ""


TOOLS: List[Callable[..., Any]] = [search, fetch_url]
