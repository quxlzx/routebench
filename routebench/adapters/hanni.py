"""Reference adapter for HANNI (https://github.com/quxlzx/hanni-core).

Requires the `hanni` package importable (PYTHONPATH=src from a hanni-core clone).
Calls HANNI's own retrieval/routing host — the same decision path the text,
voice and dashboard frontends use — and maps it onto the RouteBench contract.
"""
from __future__ import annotations

from .base import RoutingRequest, SelectedTool, Selection


class HanniAdapter:
    name = "hanni"

    def __init__(self, *, config_dir: str = "config", data_dir: str = "data/eval-routing",
                 timezone_name: str | None = None):
        from pathlib import Path
        from hanni.config.loader import load_config
        from hanni.mcp.host import McpHost
        from hanni.tools.registry import build_default_registry
        from hanni.evals.isolation import isolated_host

        config = load_config(Path(config_dir), data_dir=Path(data_dir), env={})
        registry = build_default_registry(config)
        mcp = config.hanni.mcp
        self._host = isolated_host(McpHost(registry, read_only=mcp.read_only,
                                           max_tools=mcp.max_tools_per_turn,
                                           allowed_actions=mcp.allowed_actions,
                                           timezone_name=timezone_name))

    def select(self, request: RoutingRequest) -> Selection:
        from hanni.mcp.host import classification
        from hanni.evals.isolation import isolated_host
        host = isolated_host(self._host, allowed_actions=request.allowed_actions)
        decision = host.route(request.query, history=request.history, now=request.now)
        tools = tuple(SelectedTool(name=t.capability_id, arguments=dict(t.fixed_arguments))
                      for t in decision.tools)
        return Selection(
            tools=tools,
            status=decision.status,
            confidence=decision.confidence,
            families=list(decision.families),
            subintents=list(decision.subintents),
            blocked_capabilities=list(decision.blocked_capabilities),
            classifications={t.capability_id: classification(host.registry.get(t.capability_id))
                             for t in decision.tools},
        )
