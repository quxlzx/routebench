"""Trivial floor adapter: selects nothing. Scores full marks on fallback/blocked
cases and zero target on tools cases. Use it to sanity-check the scorer."""
from __future__ import annotations

from .base import RoutingRequest, Selection


class NullAdapter:
    name = "null"

    def select(self, request: RoutingRequest) -> Selection:
        return Selection(tools=())
