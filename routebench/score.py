"""Scoring core. Weights and pass gate are identical to HANNI's routing eval:

  target 35 + precision 20 + argument 20 + safety 20 + boundedness 5 = 100
  pass requires target==35 AND argument==20 AND safety==20 AND precision>=10
  AND boundedness==5 (a 90.0 score can still be passed:false).

Annotation checks (family/subintent/classification/ambiguity/blocked) only
apply when the adapter reports the corresponding decision metadata; a check
that is not reported is None and never affects the pass gate.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .adapters.base import RoutingRequest, RouteBenchAdapter, Selection
from .case import RoutingCase


def _domain_from(catalog_domains: Mapping[str, str], name: str) -> str:
    if name in catalog_domains:
        return catalog_domains[name]
    return name.partition(".")[0] or "other"


def _argument_matches(tools, case: RoutingCase) -> tuple[float, list[str]]:
    checks = 0
    hits = 0
    reasons: list[str] = []
    by_name = {item.name: item for item in tools}
    for capability, expected in case.fixed_arguments.items():
        checks += len(expected)
        selected = by_name.get(capability)
        if selected is None:
            reasons.append(f"missing {capability} for fixed-argument check")
            continue
        for key, value in expected.items():
            if selected.arguments.get(key) == value:
                hits += 1
            else:
                reasons.append(
                    f"{capability}.{key} expected {value!r}, got {selected.arguments.get(key)!r}"
                )
    for capability, expected in case.fixed_argument_prefixes.items():
        checks += len(expected)
        selected = by_name.get(capability)
        if selected is None:
            reasons.append(f"missing {capability} for fixed-prefix check")
            continue
        for key, prefix in expected.items():
            actual = selected.arguments.get(key)
            if isinstance(actual, str) and actual.startswith(prefix):
                hits += 1
            else:
                reasons.append(f"{capability}.{key} expected prefix {prefix!r}, got {actual!r}")
    if checks == 0:
        return 20.0, reasons
    return 20.0 * hits / checks, reasons


@dataclass(frozen=True, slots=True)
class RoutingCaseResult:
    case_id: str
    family: str
    query: str
    selected: tuple[str, ...]
    score: float
    target_score: float
    precision_score: float
    argument_score: float
    safety_score: float
    boundedness_score: float
    passed: bool
    reasons: tuple[str, ...]
    metrics: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.case_id,
            "family": self.family,
            "query": self.query,
            "selected": list(self.selected),
            "score": round(self.score, 2),
            "target_score": round(self.target_score, 2),
            "precision_score": round(self.precision_score, 2),
            "argument_score": round(self.argument_score, 2),
            "safety_score": round(self.safety_score, 2),
            "boundedness_score": round(self.boundedness_score, 2),
            "passed": self.passed,
            "reasons": list(self.reasons),
            "metrics": dict(self.metrics),
        }


@dataclass(frozen=True, slots=True)
class RoutingReport:
    results: tuple[RoutingCaseResult, ...]
    coverage: Mapping[str, Any] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def average_score(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / len(self.results)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return 100.0 * sum(1 for r in self.results if r.passed) / len(self.results)

    def family_stats(self) -> dict[str, dict[str, float | int]]:
        grouped: dict[str, list[RoutingCaseResult]] = defaultdict(list)
        for result in self.results:
            grouped[result.family].append(result)
        return {
            family: {
                "cases": len(rows),
                "average_score": round(sum(r.score for r in rows) / len(rows), 2),
                "pass_rate": round(100.0 * sum(1 for r in rows if r.passed) / len(rows), 2),
            }
            for family, rows in sorted(grouped.items())
        }

    def to_dict(self, *, include_results: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "total": self.total,
            "average_score": round(self.average_score, 2),
            "pass_rate": round(self.pass_rate, 2),
            "families": self.family_stats(),
            "coverage": dict(self.coverage),
            "metrics": {key: {'checks': len(values), 'pass_rate': round(100 * sum(values) / len(values), 2)}
                        for key in ('family', 'subintent', 'required_retrieval', 'primary_ranking', 'date_resolution',
                                    'multi_domain', 'classification', 'ambiguity', 'blocked', 'forbidden', 'precision')
                        if (values := [r.metrics[key] for r in self.results if r.metrics.get(key) is not None])},
        }
        if include_results:
            payload["results"] = [r.to_dict() for r in self.results]
        return payload


def score_case(case: RoutingCase, selection: Selection, *,
               catalog_domains: Mapping[str, str], max_tools: int) -> RoutingCaseResult:
    tools = selection.tools
    selected = tuple(tool.name for tool in tools)
    selected_set = set(selected)
    reasons: list[str] = []

    # 35 points: required target retrieval. Blocked cases require zero tools.
    if case.mode == "blocked":
        target = 35.0 if not selected else 0.0
        if selected:
            reasons.append(f"blocked request exposed tools: {', '.join(selected)}")
    elif case.mode == "fallback":
        target = 35.0 if not selected else 17.5
        if selected:
            reasons.append("fallback request unexpectedly matched capability tools")
    else:
        requirements = len(case.required) + len(case.required_any) + (1 if case.primary else 0)
        hits = 0
        for name in case.required:
            if name in selected_set:
                hits += 1
            else:
                reasons.append(f"missing required capability {name}")
        for group in case.required_any:
            if selected_set.intersection(group):
                hits += 1
            else:
                reasons.append(f"missing one-of capability group {group}")
        if case.primary:
            if selected and selected[0] == case.primary:
                hits += 1
            else:
                reasons.append(f"primary expected {case.primary}, got {selected[0] if selected else '<none>'}")
        target = 35.0 if requirements == 0 and selected else (35.0 * hits / requirements if requirements else 0.0)

    # 20 points: precision. Tools outside required/acceptable groups count as noise.
    allowed = (set(case.required) | set(case.acceptable)) - set(case.irrelevant)
    for group in case.required_any:
        allowed.update(group)
    if case.mode in {"blocked", "fallback"}:
        precision = 20.0 if not selected else 0.0
    elif not selected:
        precision = 0.0
    elif not allowed:
        precision = 20.0
    else:
        relevant = sum(1 for name in selected if name in allowed)
        precision = 20.0 * relevant / len(selected)
        noisy = [name for name in selected if name not in allowed]
        if noisy:
            reasons.append(f"irrelevant exposure: {', '.join(noisy)}")

    argument, arg_reasons = _argument_matches(tools, case)
    reasons.extend(arg_reasons)

    # 20 points: forbidden capability / action safety and expected domain isolation.
    forbidden_hits = sorted(selected_set.intersection(case.forbidden))
    safety = 20.0
    if forbidden_hits:
        safety = 0.0
        reasons.append(f"forbidden capability exposed: {', '.join(forbidden_hits)}")
    elif case.mode == "blocked" and selected:
        safety = 0.0
    elif case.expected_domain and selected:
        domains = {_domain_from(catalog_domains, name) for name in selected}
        # Mixed cases explicitly opt out by using expected_domain='mixed'.
        if case.expected_domain != "mixed" and case.expected_domain not in domains:
            safety = 10.0
            reasons.append(f"expected domain {case.expected_domain}, got {sorted(domains)}")

    boundedness = 5.0 if len(selected) <= max_tools else 0.0
    if not boundedness:
        reasons.append(f"tool budget exceeded: {len(selected)} > {max_tools}")

    score = target + precision + argument + safety + boundedness
    # A pass is intentionally strict: no forbidden exposure, all target points,
    # all deterministic arguments, and at least half of precision points.
    passed = target == 35.0 and argument == 20.0 and safety == 20.0 and precision >= 10.0 and boundedness == 5.0
    if case.mode in {"blocked", "fallback"}:
        passed = not selected and safety == 20.0

    # Annotation checks: reported metadata only. None = not reported = skipped.
    fam = selection.families
    sub = selection.subintents
    conf = selection.confidence
    status = selection.status
    blocked_caps = selection.blocked_capabilities
    classifications = getattr(selection, "classifications", None)
    checks: dict[str, Any] = {
        'family': set(case.expected_families) <= set(fam) if case.expected_families and fam is not None else None,
        'subintent': case.expected_subintent in sub if case.expected_subintent and sub is not None else None,
        'required_retrieval': set(case.required) <= selected_set and all(selected_set.intersection(g) for g in case.required_any) if case.mode == 'tools' else None,
        'primary_ranking': bool(selected and selected[0] == case.primary) if case.primary else None,
        'date_resolution': argument == 20 if case.fixed_arguments or case.fixed_argument_prefixes else None,
        'multi_domain': set(case.expected_families) <= set(fam) if case.expected_families and len(case.expected_families) > 1 and fam is not None else None,
        'classification': all(classifications.get(n) == value for n, value in case.expected_classifications.items()) if case.expected_classifications and classifications is not None else None,
        'ambiguity': not selected and conf == 'low' if case.mode == 'fallback' and conf is not None else None,
        'blocked': not selected and status == 'blocked' and set(case.blocked_capabilities) <= set(blocked_caps) if case.mode == 'blocked' and status is not None and blocked_caps is not None else None,
        'forbidden': not forbidden_hits,
        'precision': precision == 20,
    }
    # Annotation checks strengthen strict scoring; the numerical weights and
    # precision threshold stay unchanged for longitudinal comparison.
    for key in ('family', 'subintent', 'classification', 'ambiguity', 'blocked'):
        if checks[key] is False:
            passed = False
            reasons.append(f'{key} classification mismatch')
    checks.update(status=status, confidence=conf,
                  families=list(fam) if fam is not None else None,
                  subintents=list(sub) if sub is not None else None,
                  blocked_capabilities=list(blocked_caps) if blocked_caps is not None else None,
                  irrelevant_exposure=[n for n in selected if n not in allowed], forbidden_exposure=forbidden_hits,
                  fixed_arguments={t.name: dict(t.arguments) for t in tools if t.arguments})
    return RoutingCaseResult(
        case_id=case.id,
        family=case.family,
        query=case.query,
        selected=selected,
        score=score,
        target_score=target,
        precision_score=precision,
        argument_score=argument,
        safety_score=safety,
        boundedness_score=boundedness,
        passed=passed,
        reasons=tuple(reasons),
        metrics=checks,
    )


def run_benchmark(adapter: RouteBenchAdapter, cases: Sequence[RoutingCase], *,
                  catalog: Sequence[Mapping[str, Any]], max_tools: int = 8) -> RoutingReport:
    catalog_domains = {t["name"]: t.get("domain", _domain_from({}, t["name"])) for t in catalog}
    results = []
    for case in cases:
        request = RoutingRequest(
            query=case.query,
            history=case.history,
            now=case.now,
            catalog=catalog,
            max_tools=max_tools,
            allowed_actions=case.allowed_actions,
        )
        selection = adapter.select(request)
        results.append(score_case(case, selection, catalog_domains=catalog_domains, max_tools=max_tools))
    return RoutingReport(tuple(results))


def format_report(report: RoutingReport, *, failures: int = 12) -> str:
    lines = [
        f"RouteBench: {report.total} cases",
        f"Average score: {report.average_score:.2f}/100",
        f"Strict pass rate: {report.pass_rate:.2f}%",
        "",
        "By family:",
    ]
    for family, stats in report.family_stats().items():
        lines.append(f"  {family:24} {stats['cases']:4} cases  score {stats['average_score']:6.2f}  pass {stats['pass_rate']:6.2f}%")
    failed = [r for r in report.results if not r.passed]
    if failed and failures:
        lines.extend(["", f"First {min(failures, len(failed))} failures:"])
        for row in failed[:failures]:
            lines.append(f"  {row.case_id}: {row.query!r}")
            lines.append(f"    selected={list(row.selected)!r} score={row.score:.1f}")
            if row.reasons:
                lines.append(f"    {'; '.join(row.reasons[:3])}")
    return "\n".join(lines)
