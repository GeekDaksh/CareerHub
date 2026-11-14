# Careers classifier loop (train only, n=200)

| # | change | why tried | family | level | ml flag | non-tech | decision |
|---|---|---|---|---|---|---|---|
| 0 | baseline |  | 0.681 | 0.850 | 0.900 | 0.862 | baseline  |
| 1 | title_underscores | titles like 'Linux kernel developer_BSH' hide words behind underscores | 0.696 | 0.854 | 0.900 | 0.862 | ACCEPT family +0.015 |
| 2 | desc_fallback_tech_only | non-technical jobs became 'ML' because company boilerplate says 'AI' 3+ times | 0.719 | 0.854 | 0.958 | 0.862 | ACCEPT family +0.023 |
| 3 | nontech_ext | strategist, sourcer, accounting, writer, growth... were missed as non-technical | 0.792 | 0.854 | 0.958 | 0.935 | ACCEPT family +0.073 |
| 4 | other_tech | solutions architects, consultants, network / mechanical / IT ops were called Software | 0.808 | 0.854 | 0.962 | 0.935 | ACCEPT family +0.016 |
| 5 | hardware_ext | DFT, logic / physical design, verification, layout, product engineering were called Software | 0.838 | 0.854 | 0.962 | 0.935 | ACCEPT family +0.030 |
| 6 | swe_ext | architect / programming / kernel titles fell to 'Other' | 0.854 | 0.854 | 0.965 | 0.935 | ACCEPT family +0.016 |
| 7 | research_titles | researcher / student researcher / post-doc titles were called ML Engineer | 0.865 | 0.854 | 0.977 | 0.935 | ACCEPT family +0.011 |
| 8 | genai_ext | 'Voice AI', 'Agent Engineer', 'Agentic Systems' not seen as GenAI | 0.873 | 0.854 | 0.981 | 0.935 | REJECT not enough gain (family +0.008) |
| 9 | manager_not_level | 'Product / Program / Account Manager' is a job name, not a seniority | 0.865 | 0.885 | 0.977 | 0.935 | ACCEPT family same, up: level_accuracy |
| 10 | mts_levels | Salesforce SMTS / LMTS mean senior | 0.865 | 0.888 | 0.977 | 0.935 | REJECT not enough gain (family +0.000) |
| 11 | student_titles | 'Student Researcher' is an internship; post-doc is right after PhD | 0.865 | 0.892 | 0.977 | 0.935 | REJECT not enough gain (family +0.000) |
| 12 | year_ranges | '2–5 years in DevOps' (no word 'experience') was missed | 0.865 | 0.900 | 0.977 | 0.935 | ACCEPT family same, up: level_accuracy |
| 13 | title_level_first | dry run: 'Data Scientist II' read as entry because the description's years were checked first | 0.865 | 0.927 | 0.977 | 0.935 | ACCEPT family same, up: level_accuracy |
| 14 | product_titles_first | dry run: 'Technical Program Manager, AI Products' called an ML role | 0.877 | 0.927 | 0.981 | 0.935 | ACCEPT family +0.012 |
| 15 | years_required_only | dry run: 'preferred: 1+ years of X' made 'Data Scientist II' (requires 2+) look entry-level | 0.877 | 0.927 | 0.981 | 0.935 | REJECT not enough gain (family +0.000) |
| 16 | genai_ext (retry) | retry after other changes | 0.885 | 0.927 | 0.985 | 0.935 | REJECT not enough gain (family +0.008) |
| 17 | mts_levels (retry) | retry after other changes | 0.877 | 0.931 | 0.981 | 0.935 | REJECT not enough gain (family +0.000) |
| 18 | student_titles (retry) | retry after other changes | 0.877 | 0.935 | 0.981 | 0.935 | REJECT not enough gain (family +0.000) |
| 19 | years_required_only (retry) | retry after other changes | 0.877 | 0.927 | 0.981 | 0.935 | REJECT not enough gain (family +0.000) |

Accepted switches: title_underscores, desc_fallback_tech_only, nontech_ext, other_tech, hardware_ext, swe_ext, research_titles, manager_not_level, year_ranges, title_level_first, product_titles_first
