# Improvement loop log (train split only)

Each row is one proposed change, judged by the rule in `OBJECTIVE.md`. Rejected changes stay in the log.

| # | Filter | Change | Type | Before | After | Decision | Why |
|---|---|---|---|---|---|---|---|
| 1 | shield | `word_boundaries=True` | bugfix | catch 7.99%, false_block 0.62% | catch 5.85%, false_block 0.37% | **reject** | gain too small or not on both halves (catch -2.14 pp, false blocks -0.25 pp) |
| 2 | shield | `chat_contact_only=True` | bugfix | catch 7.99%, false_block 0.62% | catch 7.99%, false_block 0.34% | **ACCEPT** | bug-fix rule (fewer false blocks) |
| 3 | shield | `negation_guard=True` | bugfix | catch 7.99%, false_block 0.34% | catch 7.8%, false_block 0.31% | **reject** | gain too small or not on both halves (catch -0.19 pp, false blocks -0.03 pp) |
| 4 | shield | `normalize_text=True` | detector | catch 7.99%, false_block 0.34% | catch 7.99%, false_block 0.34% | **reject** | gain too small or not on both halves (catch +0.00 pp, false blocks +0.00 pp) |
| 5 | shield | `money_transfer_rules=True` | detector | catch 7.99%, false_block 0.34% | catch 7.99%, false_block 1.12% | **reject** | false blocks 1.12% break the guardrail |
| 6 | shield | `wfh_money_rules=True` | detector | catch 7.99%, false_block 0.34% | catch 12.28%, false_block 0.55% | **reject** | gain too small or not on both halves (catch +4.29 pp, false blocks +0.21 pp) |
| 7 | shield | `personal_email_cv=True` | detector | catch 7.99%, false_block 0.34% | catch 7.99%, false_block 0.34% | **reject** | gain too small or not on both halves (catch +0.00 pp, false blocks +0.00 pp) |
| 8 | shield | `weak_signal_combo=3` | threshold | catch 7.99%, false_block 0.34% | catch 9.16%, false_block 0.35% | **ACCEPT** | primary rule |
| 9 | level | `staff_needs_role=True` | bugfix | senior_leak 30.27%, entry_loss 14.29%, balanced_error 22.28% | senior_leak 30.39%, entry_loss 14.01%, balanced_error 22.2% | **reject** | balanced error change -0.09 pp too small / not on both halves / fixes ≤ breaks |
| 10 | level | `assistant_not_senior=True` | bugfix | senior_leak 30.27%, entry_loss 14.29%, balanced_error 22.28% | senior_leak 30.62%, entry_loss 13.03%, balanced_error 21.82% | **reject** | balanced error change -0.46 pp too small / not on both halves / fixes ≤ breaks |
| 11 | level | `entry_words_win=True` | bugfix | senior_leak 30.27%, entry_loss 14.29%, balanced_error 22.28% | senior_leak 30.31%, entry_loss 13.2%, balanced_error 21.75% | **ACCEPT** | primary rule |
| 12 | level | `years_patterns_ext=True` | detector | senior_leak 30.31%, entry_loss 13.2%, balanced_error 21.75% | senior_leak 27.06%, entry_loss 14.12%, balanced_error 20.59% | **ACCEPT** | primary rule |
| 13 | level | `senior_words_ext=True` | detector | senior_leak 27.06%, entry_loss 14.12%, balanced_error 20.59% | senior_leak 26.55%, entry_loss 14.24%, balanced_error 20.4% | **reject** | balanced error change -0.20 pp too small / not on both halves / fixes ≤ breaks |
| 14 | level | `senior_from_desc=True` | detector | senior_leak 27.06%, entry_loss 14.12%, balanced_error 20.59% | senior_leak 25.42%, entry_loss 14.93%, balanced_error 20.17% | **reject** | balanced error change -0.42 pp too small / not on both halves / fixes ≤ breaks |
| 15 | level | `hide_not_stated=True` | threshold | senior_leak 27.06%, entry_loss 14.12%, balanced_error 20.59% | senior_leak 0.94%, entry_loss 73.03%, balanced_error 36.98% | **reject** | guardrail broken (entry loss 73.0%, senior leak 0.9%) |
| 16 | shield | `word_boundaries=True` | bugfix | catch 9.16%, false_block 0.35% | catch 7.02%, false_block 0.1% | **reject** | gain too small or not on both halves (catch -2.14 pp, false blocks -0.25 pp) |
| 17 | shield | `negation_guard=True` | bugfix | catch 9.16%, false_block 0.35% | catch 8.97%, false_block 0.32% | **reject** | gain too small or not on both halves (catch -0.19 pp, false blocks -0.03 pp) |
| 18 | shield | `normalize_text=True` | detector | catch 9.16%, false_block 0.35% | catch 9.16%, false_block 0.35% | **reject** | gain too small or not on both halves (catch +0.00 pp, false blocks +0.00 pp) |
| 19 | shield | `money_transfer_rules=True` | detector | catch 9.16%, false_block 0.35% | catch 9.16%, false_block 1.13% | **reject** | false blocks 1.13% break the guardrail |
| 20 | shield | `wfh_money_rules=True` | detector | catch 9.16%, false_block 0.35% | catch 12.48%, false_block 0.56% | **reject** | gain too small or not on both halves (catch +3.31 pp, false blocks +0.21 pp) |
| 21 | shield | `personal_email_cv=True` | detector | catch 9.16%, false_block 0.35% | catch 9.16%, false_block 0.35% | **reject** | gain too small or not on both halves (catch +0.00 pp, false blocks +0.00 pp) |
| 22 | level | `staff_needs_role=True` | bugfix | senior_leak 27.06%, entry_loss 14.12%, balanced_error 20.59% | senior_leak 27.18%, entry_loss 13.83%, balanced_error 20.51% | **reject** | balanced error change -0.09 pp too small / not on both halves / fixes ≤ breaks |
| 23 | level | `assistant_not_senior=True` | bugfix | senior_leak 27.06%, entry_loss 14.12%, balanced_error 20.59% | senior_leak 27.41%, entry_loss 13.6%, balanced_error 20.51% | **reject** | balanced error change -0.08 pp too small / not on both halves / fixes ≤ breaks |
