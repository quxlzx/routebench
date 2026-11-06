"""Adapter contract.

A system under test answers one question per case: given the query, the
conversation history, the wall clock, and the fixed tool catalog, which tools
would you expose/call, with what deterministic arguments?

Implement `RouteBenchAdapter.select(request) -> Selection`.
Optional decision metadata (status/confidence/families/subintents/
blocked_capabilities) unlocks the annotation checks; adapters that omit them
simply skip those checks (they never fail the pass gate spuriously).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class SelectedTool:
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Selection:
    """Ordered tool selection. First entry is the primary tool."""
    tools: tuple[SelectedTool, ...]
    # Optional decision metadata; None fields mean "not reported" and their
    # annotation checks are skipped.
    status: str | None = None            # e.g. "ok" | "blocked"
    confidence: str | None = None        # e.g. "low" | "high"
    families: Sequence[str] | None = None
    subintents: Sequence[str] | None = None
    blocked_capabilities: Sequence[str] | None = None
    classifications: Mapping[str, str] | None = None  # tool name -> classification label


@dataclass(frozen=True, slots=True)
class RoutingRequest:
    query: str
    history: tuple[Mapping[str, Any], ...]
    now: datetime | None
    catalog: Sequence[Mapping[str, Any]]   # tool defs: name/description/parameters/domain
    max_tools: int
    allowed_actions: tuple[str, ...] | None = None


class RouteBenchAdapter(Protocol):
    name: str

    def select(self, request: RoutingRequest) -> Selection: ...
