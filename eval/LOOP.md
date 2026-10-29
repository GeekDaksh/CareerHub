# Improvement loop log (train split only)

Each row is one proposed change, judged by the rule in `OBJECTIVE.md`. Rejected changes stay in the log.

| # | Filter | Change | Type | Before | After | Decision | Why |
|---|---|---|---|---|---|---|---|
| 1 | shield | `word_boundaries=True` `f8972774f3` | bugfix | catch 7.99%, false_block 0.62% | catch 7.99%, false_block 0.37% | **ACCEPT** | bug-fix rule (fewer false blocks) |
| 2 | shield | `chat_contact_only=True` `5fe7d6a8a5` | bugfix | catch 7.99%, false_block 0.37% | catch 7.99%, false_block 0.09% | **ACCEPT** | bug-fix rule (fewer false blocks) |
| 3 | shield | `negation_guard=True` `a386b78d87` | bugfix | catch 7.99%, false_block 0.09% | catch 7.8%, false_block 0.07% | **reject** | gain too small or not on both halves (catch -0.19 pp, false blocks -0.02 pp) |
| 4 | shield | `normalize_text=True` `8dbd6bb946` | detector | catch 7.99%, false_block 0.09% | catch 7.99%, false_block 0.09% | **reject** | gain too small or not on both halves (catch +0.00 pp, false blocks +0.00 pp) |
| 5 | shield | `money_transfer_rules=True` `7424afdc88` | detector | catch 7.99%, false_block 0.09% | catch 7.99%, false_block 0.88% | **reject** | gain too small or not on both halves (catch +0.00 pp, false blocks +0.80 pp) |
| 6 | shield | `wfh_money_rules=True` `0e1752f907` | detector | catch 7.99%, false_block 0.09% | catch 11.31%, false_block 0.16% | **ACCEPT** | primary rule |
| 7 | shield | `personal_email_cv=True` `b256feb838` | detector | catch 11.31%, false_block 0.16% | catch 11.31%, false_block 0.16% | **reject** | gain too small or not on both halves (catch +0.00 pp, false blocks +0.00 pp) |
| 8 | shield | `weak_signal_combo=2` `c9a0946f1f` | threshold | catch 11.31%, false_block 0.16% | catch 16.18%, false_block 0.65% | **reject** | gain too small or not on both halves (catch +4.87 pp, false blocks +0.50 pp) |
| 9 | level | `staff_needs_role=True` `d797df6454` | bugfix | senior_leak 30.27%, entry_loss 14.29%, balanced_error 22.28% | senior_leak 30.39%, entry_loss 14.01%, balanced_error 22.2% | **reject** | balanced error change -0.09 pp too small / not on both halves / fixes ≤ breaks |
| 10 | level | `assistant_not_senior=True` `d797df6454` | bugfix | senior_leak 30.27%, entry_loss 14.29%, balanced_error 22.28% | senior_leak 30.62%, entry_loss 13.03%, balanced_error 21.82% | **reject** | balanced error change -0.46 pp too small / not on both halves / fixes ≤ breaks |
| 11 | level | `entry_words_win=True` `d797df6454` | bugfix | senior_leak 30.27%, entry_loss 14.29%, balanced_error 22.28% | senior_leak 30.31%, entry_loss 13.2%, balanced_error 21.75% | **ACCEPT** | primary rule |
| 12 | level | `years_patterns_ext=True` `d797df6454` | detector | senior_leak 30.31%, entry_loss 13.2%, balanced_error 21.75% | senior_leak 27.06%, entry_loss 14.12%, balanced_error 20.59% | **ACCEPT** | primary rule |
| 13 | level | `senior_words_ext=True` `d797df6454` | detector | senior_leak 27.06%, entry_loss 14.12%, balanced_error 20.59% | senior_leak 26.55%, entry_loss 14.24%, balanced_error 20.4% | **reject** | balanced error change -0.20 pp too small / not on both halves / fixes ≤ breaks |
| 14 | level | `senior_from_desc=True` `d797df6454` | detector | senior_leak 27.06%, entry_loss 14.12%, balanced_error 20.59% | senior_leak 25.42%, entry_loss 14.93%, balanced_error 20.17% | **reject** | balanced error change -0.42 pp too small / not on both halves / fixes ≤ breaks |
| 15 | level | `hide_not_stated=True` `d797df6454` | threshold | senior_leak 27.06%, entry_loss 14.12%, balanced_error 20.59% | senior_leak 0.94%, entry_loss 73.03%, balanced_error 36.98% | **reject** | guardrail broken (entry loss 73.0%, senior leak 0.9%) |
| 16 | shield | `negation_guard=True` `a386b78d87` | bugfix | catch 11.31%, false_block 0.16% | catch 11.11%, false_block 0.14% | **reject** | gain too small or not on both halves (catch -0.19 pp, false blocks -0.02 pp) |
| 17 | shield | `normalize_text=True` `8dbd6bb946` | detector | catch 11.31%, false_block 0.16% | catch 11.31%, false_block 0.16% | **reject** | gain too small or not on both halves (catch +0.00 pp, false blocks +0.00 pp) |
| 18 | shield | `money_transfer_rules=True` `7424afdc88` | detector | catch 11.31%, false_block 0.16% | catch 11.31%, false_block 0.95% | **reject** | false blocks 0.95% break the guardrail |
| 19 | level | `staff_needs_role=True` `d797df6454` | bugfix | senior_leak 27.06%, entry_loss 14.12%, balanced_error 20.59% | senior_leak 27.18%, entry_loss 13.83%, balanced_error 20.51% | **reject** | balanced error change -0.09 pp too small / not on both halves / fixes ≤ breaks |
| 20 | level | `assistant_not_senior=True` `d797df6454` | bugfix | senior_leak 27.06%, entry_loss 14.12%, balanced_error 20.59% | senior_leak 27.41%, entry_loss 13.6%, balanced_error 20.51% | **reject** | balanced error change -0.08 pp too small / not on both halves / fixes ≤ breaks |
