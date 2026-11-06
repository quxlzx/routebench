"""Corpus case model. Field semantics are identical to HANNI's hanni.evals.routing.RoutingCase."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


@dataclass(frozen=True, slots=True)
class RoutingCase:
    id: str
    family: str
    query: str
    expected_domain: str
    expected_intent: str
    mode: str = "tools"  # tools | blocked | fallback
    required: tuple[str, ...] = ()
    required_any: tuple[tuple[str, ...], ...] = ()
    acceptable: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    primary: str | None = None
    fixed_arguments: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    fixed_argument_prefixes: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    history: tuple[Mapping[str, Any], ...] = ()
    now: datetime | None = None
    tags: tuple[str, ...] = ()
    irrelevant: tuple[str, ...] = ()
    expected_families: tuple[str, ...] = ()
    expected_subintent: str | None = None
    expected_classifications: Mapping[str, str] = field(default_factory=dict)
    blocked_capabilities: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RoutingCase":
        required_any = tuple(tuple(str(v) for v in group) for group in raw.get("required_any", ()))
        now = raw.get("now")
        if now:
            now = datetime.fromisoformat(str(now))
        return cls(
            id=str(raw["id"]),
            family=str(raw["family"]),
            query=str(raw["query"]),
            expected_domain=str(raw.get("expected_domain", "other")),
            expected_intent=str(raw.get("expected_intent", "unknown")),
            mode='blocked' if raw.get('expected_blocked') else str(raw.get("mode", "tools")),
            required=_tuple(raw.get("required_capabilities", raw.get("required"))),
            required_any=required_any,
            acceptable=_tuple(raw.get("acceptable_capabilities", raw.get("acceptable"))),
            forbidden=_tuple(raw.get("forbidden_capabilities", raw.get("forbidden"))),
            primary=str(raw["primary"]) if raw.get("primary") else None,
            fixed_arguments=dict(raw.get("expected_resolved_arguments", raw.get("fixed_arguments", {}))),
            fixed_argument_prefixes=dict(raw.get("fixed_argument_prefixes", {})),
            history=tuple(raw.get("history", ())),
            now=now,
            tags=_tuple(raw.get("tags")),
            irrelevant=_tuple(raw.get('irrelevant_capabilities')),
            expected_families=_tuple(raw.get('expected_families', raw.get('expected_family'))),
            expected_subintent=raw.get('expected_subintent'),
            expected_classifications=dict(raw.get('expected_classifications', {})),
            blocked_capabilities=_tuple(raw.get('blocked_capabilities')),
            allowed_actions=tuple(raw['allowed_actions']) if 'allowed_actions' in raw else None,
        )


def load_cases(path: Path | str) -> tuple[RoutingCase, ...]:
    path = Path(path)
    cases: list[RoutingCase] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            raw = json.loads(line)
            cases.append(RoutingCase.from_dict(raw))
        except Exception as exc:
            raise ValueError(f"{path}:{lineno}: invalid routing case: {exc}") from exc
    if len({case.id for case in cases}) != len(cases):
        raise ValueError(f'{path}: duplicate routing case IDs')
    return tuple(cases)
