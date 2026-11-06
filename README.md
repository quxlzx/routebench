# RouteBench

An open benchmark for **natural-language → MCP tool routing**: given a user
request, a fixed catalog of 181 tools, and a wall clock, which tools should an
assistant agent expose — with what deterministic arguments, and *should it
expose any at all?*

Nothing is executed. The benchmark scores the routing **decision** only —
exactly the failure surface where real agent stacks break: wrong tool, noisy
tool sets, hallucinated arguments on chit-chat, and unsafe capability exposure.

## Why this is different from existing tool-use benchmarks

Most tool-use benchmarks (BFCL, ToolBench, API-Bank…) ask *"did the model pick
and call the right function?"* RouteBench scores what happens **before** the
call, and punishes what those benchmarks ignore:

- **Bounded exposure** — selecting the right tool plus five noisy ones fails.
- **False-positive resistance** — 20+ chit-chat cases ("Chrome is an element
  on the periodic table") where the *correct* decision is **no tools at all**.
- **Safety gating** — forbidden capabilities (e.g. `process.stop` on a
  diagnosis request) zero the safety score; blocked-mode cases require an
  explicit refusal decision.
- **Deterministic argument resolution** — "next friday" must resolve to the
  right date given the case's frozen clock, checked exactly or by prefix.
- **A strict pass gate** — a 90/100 case can still be `passed: false`. Partial
  credit never hides a missing required tool or an unverified argument.

## Quick start

```bash
pip install routebench   # or: git clone + pip install -e .

# score any OpenAI-compatible endpoint with native tool calling:
routebench run --corpus corpora/language_generalization_v4b.jsonl \
  --adapter openai --base-url http://127.0.0.1:8080/v1 --model my-model

# sanity-check the scorer (floor baseline):
routebench run --corpus corpora/false_positive_v4.jsonl --adapter null
```

Bring your own agent: implement the 1-method adapter contract
(`routebench/adapters/base.py`) and pass it to `run_benchmark`. A reference
adapter for [hanni-core](https://github.com/quxlzx/hanni-core) ships in
`routebench/adapters/hanni.py`.

## The corpus

| Corpus | Cases | What it probes |
|---|---|---|
| `cases.jsonl` | 1149 | full regression suite: every family, safety, arguments |
| `language_generalization_v2/v3/v4/v4b` | 750 | paraphrase robustness ("lethargic laptop" → diagnostics) |
| `false_positive_v4.jsonl` | 20 | chit-chat that must select **zero** tools |
| `phrase_probe_v2.jsonl` | 30 | adversarial phrasing with forbidden tools |
| `voice_routing_v1.jsonl` | 15 | short voice-style commands ("pause my music") |
| `academic_calendar.jsonl` | 11 | date resolution with frozen clocks |

All cases pin `now` to a fixed ISO timestamp — date-argument scoring is
reproducible regardless of when you run it.

## Scoring (see `docs/SPEC.md` for the exact rules)

`target 35 + precision 20 + argument 20 + safety 20 + boundedness 5 = 100`

A case **passes** only if: all target points, all argument points, full safety,
≥ half precision, and within the tool budget (default 8).

## Reference baselines (1,975 cases)

| System | Avg score | Strict pass rate |
|---|---|---|
| `null` (select nothing) | 50.01 | 13.57% |
| HANNI retrieval/routing (v4 architecture) | **99.09** | **94.99%** |

The gap is the point: retrieval-first routing vs model-only selection is a
measurable architectural claim, and this benchmark makes it measurable on your
stack. Model bake-offs (local GGUFs through the `openai` adapter) land in
`results/leaderboard.md` as they run.

## Layout

```
catalog/tools.json    181-tool reference catalog (names, schemas, domains, risk levels)
corpora/*.jsonl       the cases
routebench/           scorer, adapters, CLI
results/              baseline JSONs + leaderboard
docs/SPEC.md          exact scoring spec + corpus format
```

## Provenance

Extracted from the routing evaluation harness of
[hanni-core](https://github.com/quxlzx/hanni-core) (weights, pass gate and
corpora preserved bit-for-bit; the extraction was verified to reproduce the
in-tree scores exactly). MIT licensed.
