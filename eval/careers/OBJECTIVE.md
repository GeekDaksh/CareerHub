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

## Amendment (2026-11-14, before loop run 3)
The dry run on all 2,002 jobs showed level mistakes on Amazon jobs, which train barely covered (Amazon is 21% of all
jobs but 6% of train). Added `gold2.jsonl`: 60 more FAANG+ jobs (seed 31415), labelled blind the same way, except
years are read from the *required* qualifications (the more correct reading). Train is now gold + gold2 (n=260).
Objective, guardrails and accept rule unchanged. The old loop log is archived; the loop is re-run from scratch.
The test set is unchanged; its next run will be logged as the second final run.

## Amendment 2 (2026-11-14, before loop run 4)
`gold3_hard.jsonl`: 6 jobs found by looking at the app (every 'Prime Video' job outside train/test was called
Computer Vision because of the team name). They were picked BECAUSE they were wrong, so they are not a random
sample — they only steer tuning; all reported accuracy claims come from the untouched test set. Train n=266.
