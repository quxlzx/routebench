"""RouteBench CLI.

  routebench run --corpus corpora/language_generalization_v4b.jsonl --adapter null
  routebench run --corpus ... --adapter hanni --hanni-dir /path/to/hanni-core
  routebench run --corpus ... --adapter openai --base-url http://127.0.0.1:8080/v1 --model qwen3.5-4b
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .case import load_cases
from .score import format_report, run_benchmark

HERE = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = HERE / "catalog" / "tools.json"


def build_adapter(args):
    if args.adapter == "null":
        from .adapters.null import NullAdapter
        return NullAdapter()
    if args.adapter == "hanni":
        from .adapters.hanni import HanniAdapter
        root = Path(args.hanni_dir)
        try:
            from hanni.evals.fixtures import fixture_timezone
            tz = fixture_timezone(args.corpus)
        except Exception:
            tz = None
        return HanniAdapter(config_dir=str(root / "config"),
                            data_dir=str(root / "data" / "eval-routing"),
                            timezone_name=tz)
    if args.adapter == "openai":
        from .adapters.openai_compat import OpenAICompatAdapter
        return OpenAICompatAdapter(base_url=args.base_url, api_key=args.api_key,
                                   model=args.model, temperature=args.temperature)
    raise SystemExit(f"unknown adapter: {args.adapter}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="routebench", description="Open benchmark for natural-language -> MCP tool routing")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="score one adapter against one corpus")
    run.add_argument("--corpus", type=Path, required=True)
    run.add_argument("--adapter", required=True, choices=["null", "hanni", "openai"])
    run.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    run.add_argument("--max-tools", type=int, default=8)
    run.add_argument("--json", type=Path, help="write full JSON report")
    run.add_argument("--failures", type=int, default=12)
    run.add_argument("--min-pass-rate", type=float, default=0.0)
    run.add_argument("--hanni-dir", default=".", help="hanni-core clone root (for --adapter hanni)")
    run.add_argument("--base-url", default=None)
    run.add_argument("--api-key", default=None)
    run.add_argument("--model", default=None)
    run.add_argument("--temperature", type=float, default=0.0)

    args = parser.parse_args(argv)
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    cases = load_cases(args.corpus)
    adapter = build_adapter(args)
    report = run_benchmark(adapter, cases, catalog=catalog, max_tools=args.max_tools)
    print(format_report(report, failures=args.failures))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = report.to_dict()
        payload["adapter"] = getattr(adapter, "name", args.adapter)
        payload["corpus"] = str(args.corpus)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0 if report.pass_rate >= args.min_pass_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
