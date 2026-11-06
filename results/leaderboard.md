# Leaderboard

Strict pass rate is the headline metric. All runs use the 181-tool reference
catalog and `max_tools=8`. Reproduce with the commands shown.

| System | Adapter | Cases | Avg score | Pass rate | Date |
|---|---|---|---|---|---|
| null floor (select nothing) | `null` | 1,975 | 50.01 | 13.57% | 2026-11-06 |
| HANNI routing v4 (retrieval-first reference) | `hanni` | 1,975 | 99.09 | 94.99% | 2026-11-06 |

## Per-corpus reference (HANNI v4)

| Corpus | Cases | Avg | Pass |
|---|---|---|---|
| academic_calendar | 11 | 100.00 | 100.00% |
| cases | 1,149 | 99.43 | 93.30% |
| false_positive_v4 | 20 | 100.00 | 100.00% |
| language_generalization_v2 | 200 | 98.82 | 97.50% |
| language_generalization_v3 | 150 | 99.14 | 99.33% |
| language_generalization_v4 | 300 | 98.58 | 97.00% |
| language_generalization_v4b | 100 | 97.41 | 94.00% |
| phrase_probe_v2 | 30 | 98.34 | 96.67% |
| voice_routing_v1 | 15 | 96.89 | 100.00% |

## Model bake-offs (openai adapter)

Pending — local GGUFs via llama-server and hosted models will be added here.
Each entry must state: model + quantization, serving stack, hardware, and the
exact command.
