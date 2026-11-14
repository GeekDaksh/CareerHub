# Careers classifier — objective (declared before tuning, 2026-11-14)

Sets
- **train** = `gold.jsonl` (200). Tuning looks only at this.
- **test** = `test.jsonl` (100, different jobs, labelled blind, never shown to the classifier until the final run).
  Test runs need `--final` and are appended to `test_runs.log`.

Primary metric: **family_accuracy** on train (the user asked for good role segmentation first).
Guardrails (must not get worse than baseline by more than 1 point on train):
- level_accuracy, ml_flag_accuracy, nontech_accuracy
Fresher metrics (n=8) are reported but too small to judge changes by.

Accept rule for each change: primary goes up by ≥ 1 point (2 jobs), or a guardrail goes up by ≥ 1 point with
primary unchanged; no guardrail drops by more than 1 point; ties rejected.
Baseline (v1): family 0.670 · level 0.890 · ml_flag 0.905 · nontech 0.880 (train, n=200).
