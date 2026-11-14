# Careers classifier loop (train only, n=200)

| # | change | why tried | family | level | ml flag | non-tech | decision |
|---|---|---|---|---|---|---|---|
| 0 | baseline |  | 0.665 | 0.846 | 0.883 | 0.853 | baseline  |
| 1 | title_underscores | titles like 'Linux kernel developer_BSH' hide words behind underscores | 0.680 | 0.850 | 0.883 | 0.853 | ACCEPT family +0.015 |
| 2 | desc_fallback_tech_only | non-technical jobs became 'ML' because company boilerplate says 'AI' 3+ times | 0.703 | 0.850 | 0.940 | 0.853 | ACCEPT family +0.023 |
| 3 | nontech_ext | strategist, sourcer, accounting, writer, growth... were missed as non-technical | 0.774 | 0.850 | 0.940 | 0.925 | ACCEPT family +0.071 |
| 4 | other_tech | solutions architects, consultants, network / mechanical / IT ops were called Software | 0.789 | 0.850 | 0.944 | 0.925 | ACCEPT family +0.015 |
| 5 | hardware_ext | DFT, logic / physical design, verification, layout, product engineering were called Software | 0.820 | 0.850 | 0.944 | 0.925 | ACCEPT family +0.031 |
| 6 | swe_ext | architect / programming / kernel titles fell to 'Other' | 0.835 | 0.850 | 0.947 | 0.925 | ACCEPT family +0.015 |
| 7 | research_titles | researcher / student researcher / post-doc titles were called ML Engineer | 0.846 | 0.850 | 0.959 | 0.925 | ACCEPT family +0.011 |
| 8 | genai_ext | 'Voice AI', 'Agent Engineer', 'Agentic Systems' not seen as GenAI | 0.853 | 0.850 | 0.962 | 0.925 | REJECT not enough gain (family +0.007) |
| 9 | manager_not_level | 'Product / Program / Account Manager' is a job name, not a seniority | 0.846 | 0.880 | 0.959 | 0.925 | ACCEPT family same, up: level_accuracy |
| 10 | mts_levels | Salesforce SMTS / LMTS mean senior | 0.846 | 0.883 | 0.959 | 0.925 | REJECT not enough gain (family +0.000) |
| 11 | student_titles | 'Student Researcher' is an internship; post-doc is right after PhD | 0.846 | 0.887 | 0.959 | 0.925 | REJECT not enough gain (family +0.000) |
| 12 | year_ranges | '2–5 years in DevOps' (no word 'experience') was missed | 0.846 | 0.895 | 0.959 | 0.925 | ACCEPT family same, up: level_accuracy |
| 13 | title_level_first | dry run: 'Data Scientist II' read as entry because the description's years were checked first | 0.846 | 0.921 | 0.959 | 0.925 | ACCEPT family same, up: level_accuracy |
| 14 | product_titles_first | dry run: 'Technical Program Manager, AI Products' called an ML role | 0.857 | 0.921 | 0.962 | 0.925 | ACCEPT family +0.011 |
| 15 | years_required_only | dry run: 'preferred: 1+ years of X' made 'Data Scientist II' (requires 2+) look entry-level | 0.857 | 0.921 | 0.962 | 0.925 | REJECT not enough gain (family +0.000) |
| 16 | cv_strict | screenshot: 'Software Development Engineer ... Prime Video' called Computer Vision (team name) | 0.865 | 0.921 | 0.985 | 0.925 | REJECT not enough gain (family +0.008) |
| 17 | genai_ext (retry) | retry after other changes | 0.865 | 0.921 | 0.966 | 0.925 | REJECT not enough gain (family +0.008) |
| 18 | mts_levels (retry) | retry after other changes | 0.857 | 0.925 | 0.962 | 0.925 | REJECT not enough gain (family +0.000) |
| 19 | student_titles (retry) | retry after other changes | 0.857 | 0.929 | 0.962 | 0.925 | REJECT not enough gain (family +0.000) |
| 20 | years_required_only (retry) | retry after other changes | 0.857 | 0.921 | 0.962 | 0.925 | REJECT not enough gain (family +0.000) |
| 21 | cv_strict (retry) | retry after other changes | 0.865 | 0.921 | 0.985 | 0.925 | REJECT not enough gain (family +0.008) |

Accepted switches: title_underscores, desc_fallback_tech_only, nontech_ext, other_tech, hardware_ext, swe_ext, research_titles, manager_not_level, year_ranges, title_level_first, product_titles_first
