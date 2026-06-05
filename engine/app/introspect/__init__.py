"""Static agent introspection — factory keyed on framework.

NEVER executes cloned repo code; everything is `ast`-based static analysis.
"""

from __future__ import annotations

from ..contract import Framework, IntrospectResult
from . import claude, langgraph, openai
from .errors import AgentNotFound

__all__ = ["introspect", "AgentNotFound"]

# Each per-framework parser returns a single AgentSpec (or raises AgentNotFound).
# The factory wraps it in the plural IntrospectResult container. When the
# parsers learn to find multiple agents per repo, they can return several here
# without any change to this contract.
_PARSERS = {
    Framework.langgraph: langgraph.introspect,
    Framework.openai: openai.introspect,
    Framework.claude: claude.introspect,
}


def introspect(repo_path: str, framework: Framework) -> IntrospectResult:
    parser = _PARSERS.get(framework)
    if parser is None:  # pragma: no cover - enum is exhaustive
        raise AgentNotFound(f"unsupported framework: {framework}", str(framework))
    spec = parser(repo_path)  # raises AgentNotFound if nothing is located
    result = IntrospectResult(agents=[spec])
    if not result.agents:  # defensive: never return an empty list
        raise AgentNotFound("no agents located in repo", str(framework))
    return result
