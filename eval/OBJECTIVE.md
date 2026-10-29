# Objective, guardrails and accept rule — declared BEFORE tuning

Committed after the baseline and before the improvement loop ran. Changing this file after tuning starts is not allowed.

## Why these metrics
Career Hub's two filters decide what Daksh sees:
- **Scam shield.** A missed scam can cost money and personal data, so the **catch rate** matters most. A wrongly blocked real post costs an opportunity, so **false blocks** must stay very low.
- **Fresher filter.** Showing senior jobs wastes his time (**senior leak**). Hiding real entry-level jobs costs opportunities (**entry loss**). Both matter, so the primary is their average.

## Baseline (train split, all switches off) — `eval/baseline_train.json`
| Metric | Value | 95% range | n |
|---|---|---|---|
| catch rate | 7.99% | 5.85–10.33 | 513 scams |
| false blocks | 0.62% | 0.49–0.77 | 10,289 real posts |
| senior leak | 30.27% | 28.63–31.91 | 2,557 senior jobs |
| entry loss | 14.29% | 12.62–15.91 | 1,735 entry jobs |
| India hard set | scam 37/43 · level 42/43 | | 43 frozen cases |

## Scam shield
- **Primary:** catch rate on train (higher is better).
- **Guardrails:** false blocks ≤ 1.00% and ≤ baseline + 0.30 pp (≤ 0.92%). No India hard-set scam case that is currently right may become wrong.
- **Accept rule:** catch rate improves by **≥ 1.0 pp** (about 5 scams). It must also improve on **both** fixed halves of train (A and B). Newly caught scams must outnumber newly blocked real posts. Guardrails must hold. Ties are rejected.
- **Separate rule for bug fixes that cut false blocks:** accept if false blocks fall by **≥ 0.10 pp** on train, the catch rate drops by at most 0.5 pp, the drop in false blocks holds on both halves, and the hard set does not regress.

## Fresher filter
- **Primary:** balanced error = (senior leak + entry loss) / 2 on train (lower is better).
- **Guardrails:** entry loss ≤ 15.0%, senior leak ≤ 35.0%, no India hard-set level case that is currently right may become wrong.
- **Accept rule:** balanced error falls by **≥ 0.5 pp**. It must also fall on both halves. More cases must be fixed than broken. Guardrails must hold. Ties are rejected.

## Loop rules
- Train split only. The loop has no code path to the test split.
- One change per iteration, taken from a fixed rulebook in a fixed order: bug fixes first, then new detectors, then thresholds. It's deterministic and resumable from `eval/loop_log.jsonl`.
- A rejected change may be retried at most twice, and only after another switch in the same filter has changed.
- No campaign-specific phrases (e.g. a named scam company's boilerplate). They would memorise this dataset, not generalise. EMSCAD repeats whole scam campaigns across many ads.

## Test
`python -m eval.run_eval --final` runs **once**, after the loop and the red-team fixes. Every run is appended to `eval/test_runs.log`, which is committed.
