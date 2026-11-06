"""Pinned scoring contract. These numbers are the benchmark; if they move,
the benchmark version moves with them."""
from pathlib import Path

from routebench.adapters.null import NullAdapter
from routebench.case import load_cases
from routebench.score import run_benchmark
import json

ROOT = Path(__file__).resolve().parent.parent
CATALOG = json.loads((ROOT / "catalog" / "tools.json").read_text())


def test_null_floor_on_false_positives():
    cases = load_cases(ROOT / "corpora" / "false_positive_v4.jsonl")
    report = run_benchmark(NullAdapter(), cases, catalog=CATALOG)
    assert report.total == 20
    assert report.average_score == 100.0
    assert report.pass_rate == 100.0


def test_null_floor_on_tools():
    cases = load_cases(ROOT / "corpora" / "voice_routing_v1.jsonl")
    report = run_benchmark(NullAdapter(), cases, catalog=CATALOG)
    # empty selection: 0 target, 0 precision, 20 argument (no checks),
    # 20 safety (nothing forbidden), 5 boundedness = 45.0
    assert report.average_score == 45.0
    assert report.pass_rate == 0.0


def test_case_loader_semantics():
    raw = {"id": "X", "family": "f", "query": "q", "required_capabilities": ["a.b"],
           "expected_blocked": True, "now": "2026-01-01T00:00:00"}
    from routebench.case import RoutingCase
    case = RoutingCase.from_dict(raw)
    assert case.mode == "blocked"
    assert case.required == ("a.b",)
    assert case.expected_domain == "other"  # default pitfall: empty domain drops safety to 10
