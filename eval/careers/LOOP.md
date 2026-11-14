# Careers classifier loop (train only, n=200)

| # | change | why tried | family | level | ml flag | non-tech | decision |
|---|---|---|---|---|---|---|---|
| 0 | baseline |  | 0.670 | 0.890 | 0.905 | 0.880 | baseline  |
| 1 | title_underscores | titles like 'Linux kernel developer_BSH' hide words behind underscores | 0.690 | 0.895 | 0.905 | 0.880 | ACCEPT family +0.020 |
| 2 | desc_fallback_tech_only | non-technical jobs became 'ML' because company boilerplate says 'AI' 3+ times | 0.720 | 0.895 | 0.970 | 0.880 | ACCEPT family +0.030 |
| 3 | nontech_ext | strategist, sourcer, accounting, writer, growth... were missed as non-technical | 0.810 | 0.895 | 0.970 | 0.970 | ACCEPT family +0.090 |
| 4 | other_tech | solutions architects, consultants, network / mechanical / IT ops were called Software | 0.830 | 0.895 | 0.975 | 0.970 | ACCEPT family +0.020 |
| 5 | hardware_ext | DFT, logic / physical design, verification, layout, product engineering were called Software | 0.870 | 0.895 | 0.975 | 0.970 | ACCEPT family +0.040 |
| 6 | swe_ext | architect / programming / kernel titles fell to 'Other' | 0.890 | 0.895 | 0.980 | 0.970 | ACCEPT family +0.020 |
| 7 | research_titles | researcher / student researcher / post-doc titles were called ML Engineer | 0.905 | 0.895 | 0.995 | 0.970 | ACCEPT family +0.015 |
| 8 | genai_ext | 'Voice AI', 'Agent Engineer', 'Agentic Systems' not seen as GenAI | 0.915 | 0.895 | 1.000 | 0.970 | ACCEPT family +0.010 |
| 9 | manager_not_level | 'Product / Program / Account Manager' is a job name, not a seniority | 0.915 | 0.935 | 1.000 | 0.970 | ACCEPT family same, up: level_accuracy |
| 10 | mts_levels | Salesforce SMTS / LMTS mean senior | 0.915 | 0.940 | 1.000 | 0.970 | REJECT not enough gain (family +0.000) |
| 11 | student_titles | 'Student Researcher' is an internship; post-doc is right after PhD | 0.915 | 0.945 | 1.000 | 0.970 | ACCEPT family same, up: level_accuracy |
| 12 | year_ranges | '2–5 years in DevOps' (no word 'experience') was missed | 0.915 | 0.965 | 1.000 | 0.970 | ACCEPT family same, up: level_accuracy |
| 13 | title_level_first | dry run: 'Data Scientist II' read as entry because the description's years were checked first | 0.915 | 0.965 | 1.000 | 0.970 | REJECT not enough gain (family +0.000) |
| 14 | product_titles_first | dry run: 'Technical Program Manager, AI Products' called an ML role | 0.925 | 0.965 | 1.000 | 0.970 | ACCEPT family +0.010 |
| 15 | years_required_only | dry run: 'preferred: 1+ years of X' made 'Data Scientist II' (requires 2+) look entry-level | 0.925 | 0.965 | 1.000 | 0.970 | REJECT not enough gain (family +0.000) |

Accepted switches: title_underscores, desc_fallback_tech_only, nontech_ext, other_tech, hardware_ext, swe_ext, research_titles, genai_ext, manager_not_level, student_titles, year_ranges, product_titles_first
