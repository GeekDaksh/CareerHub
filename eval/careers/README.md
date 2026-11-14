# Careers classification gold set (frozen)

- `gold.jsonl`: 200 real jobs from the companies' own careers sites, collected by the probe workflow on 2026-11-14 (`probe-data` branch).
  Drawn with a fixed seed (20261115), at most 12 per company, so no single company dominates.
- Hand-labelled by reading the title and description, **before** the classifier was run on these jobs.
- Labels: `gold_family` (role family) and `gold_level` (Intern / New grad / Early career / Mid / Senior+ / Not stated).
- Level rule used when labelling: title words decide first (Senior/Staff/Principal/Lead/Manager/Director → Senior+,
  II/III → Mid, Intern/Apprentice/Student → Intern). Otherwise the smallest years asked: ≤1 → New grad, 2 → Early,
  3–5 → Mid, 6+ → Senior+. Nothing → Not stated.
- `gold.sha256` locks the file. Tests fail if it changes. Tuning must not edit it.
- Known weakness: only 8 of 200 are fresher-level. That is itself a finding: big-company careers sites list very few
  fresher jobs, so the app must surface those few clearly.
