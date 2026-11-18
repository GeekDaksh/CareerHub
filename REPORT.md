# Career Hub — build → break → rebuild report

## 1. Summary
Career Hub collects fresher jobs and freelance gigs for Daksh. Two filters decide what he sees: the **scam shield** and the **fresher filter**. Both were measured on EMSCAD (17,880 real job ads, 866 confirmed scams), improved with a logged loop on the train split, attacked on purpose, fixed, then scored **once** on the locked test split.

| Test split (7,078 ads) | Baseline | Final | Change (95 % range, paired) |
|---|---|---|---|
| Scams blocked (catch rate) | 8.22 % | **12.18 %** | +3.97 pp [+1.55 … +7.94], a real change |
| Real ads wrongly blocked | 1.01 % | **0.24 %** | −0.77 pp [−1.06 … −0.53], a real change |
| Senior jobs still shown | 27.83 % | **25.09 %** | −2.74 pp [−3.60 … −1.83], a real change |
| Entry jobs wrongly hidden | 16.03 % | **16.03 %** | +0.00 pp [−0.83 … +0.70], could be luck |
| Scams blocked, **unseen campaigns only** (224 scams) | — | **4.91 %** [1.83 … 8.22] | the stricter number |

**The honest headline:** the text rules now block 4× fewer real jobs, with a real but modest gain in scams caught. Most of that gain comes from re-catching copies of scam campaigns already seen in train. On brand-new campaigns, the rules alone catch about 1 in 20. This is why the app does not rely on text rules: trust also comes from *where* a post comes from (official ATS pages, DKIM-checked alert emails, known platforms) and from Daksh's own reports.

## 2. Design
- **Collectors** (GitHub Actions, 4×/day): the gig radar (Freelancer.com API, RemoteOK, Himalayas, Jobicy, Remotive, WWR, the HN thread), the role radar (company ATS boards, Gmail job-alert emails, remote boards, web search), and the job finder (startups, people, graded work emails), Mon/Thu.
- **Storage:** a private Hugging Face dataset. **App:** FastAPI + one HTML page on a private HF Space.
- **Filters:** regex rules with plain-language reasons (`common/trust.py`), a level classifier (`common/levels.py`), and a trust verdict from the source.
- **Why rules, not a trained model:** every block carries a reason Daksh can read and overrule, they run free in CI, and a model trained on EMSCAD (US ads, 2012–14) would mostly learn its repeated campaigns (see §6).
- **Alternatives considered:** an LLM judging every post (rejected: free quotas, and prompt injection — the post's own text would steer the verdict); scraping LinkedIn (rejected: ToS, account bans).

**LLM use and privacy:** Gemini/Groq write gig summaries and proposal drafts, and read alert emails. AI output never decides whether a post is blocked or shown (tested). For alert emails, the AI may only choose among the email's own job links, and a title must appear in the email. No AI reads feedback reports. Contacts, the tracker and earnings stay in the private dataset. Deploy refuses to run if the Space or dataset is public.

## 3. Evaluation setup
- **Data:** EMSCAD, SHA-256 pinned (`eval/fetch_emscad.sh`). G1 data gate: hash, 17,880 rows, 866 scams, unique ids, no train/test overlap.
- **Split:** 60/40 by a hash of `job_id`. Train has two fixed halves (A/B); an accepted change must help on both. The test split opens only with `--final` (enforced in code, and the run is logged).
- **Labels:** scam = `fraudulent`. Senior = Mid-Senior / Director / Executive. Entry = Entry level / Internship. Ads with no stated level are excluded from the level metrics.
- **Ranges:** 95 % **campaign bootstrap**. Ads with the same opening text are resampled together, because 513 train scams are only 361 campaigns. Changes vs baseline use a paired bootstrap of the difference.
- **Metric code** verified against scikit-learn on 200 random cases (max difference 0.0).
- **India hard set:** 43 hand-written cases, hash-locked before tuning, used only as a "no regression" guardrail.
- **Objective** declared before tuning (`eval/OBJECTIVE.md`).

## 4. Baseline vs final
| | Train baseline | Train final | Test baseline | Test final |
|---|---|---|---|---|
| Catch rate | 7.99 % | 11.31 % | 8.22 % | 12.18 % |
| False blocks | 0.62 % | 0.16 % | 1.01 % | 0.24 % |
| Senior leak | 30.27 % | 27.06 % | 27.83 % | 25.09 % |
| Entry loss | 14.29 % | 14.12 % | 16.03 % | 16.03 % |
| Hard set (scam / level) | 37/43 · 42/43 | 41/43 · 43/43 | | |

**Train vs test gap:** catch rate and false blocks hold up on test. Entry loss on test (16.03 %) is above the 15 % guardrail set on train, but the test **baseline** is already 16.03 %. The tuning didn't cause it; the guardrail level was simply set from train. Nothing was tuned after the test run.

**Calibration (test):**
- A post with a scam sign is really a scam **72.9 %** of the time (43 of 59). With no sign, 4.4 %.
- Level label "entry" → 93.4 % really entry.
- "Senior" → 86.9 % really senior.
- "Not stated" → 62.7 % entry. These are shown with a "check level" tag, not hidden.

## 5. Iteration history (`eval/LOOP.md`, run 4)
Run 4: 20 iterations, 5 accepted, 15 rejected. Runs 1–3 are archived in `eval/archive/` (see "loop bugs" below).

| Accepted | Effect on train |
|---|---|
| `word_boundaries` (whole words only) | false blocks 0.62 → 0.37 % |
| `chat_contact_only` (WhatsApp/Telegram only when used as the contact) | false blocks 0.37 → 0.09 % |
| `wfh_money_rules` ("earn $X/week from home") | catch 7.99 → 11.31 % (+17 scams, +7 false blocks) |
| `entry_words_win` (junior word beats senior word in a title) | entry loss 14.29 → 13.20 % |
| `years_patterns_ext` ("3+ yrs", "4 years' experience") | senior leak 30.31 → 27.06 % |

| Rejected (examples) | Why |
|---|---|
| `weak_signal_combo=2` | +25 scams but +51 real jobs blocked (0.65 %), so newly caught ≤ newly blocked |
| `money_transfer_rules` | 0 extra scams, false blocks 0.95 % (breaks the guardrail) |
| `hide_not_stated` | entry loss 73 % |
| `negation_guard` | lost 1 real scam for 2 fewer false blocks |
| `normalize_text` | no EMSCAD evidence. Later turned on as a **red-team security fix**, with 0 changed decisions on 10,802 train ads. This is labelled separately and is not a loop acceptance. |

**Loop bugs found and fixed openly:**
1. On resume, the loop retried rejected ideas when nothing they depend on had changed, against the declared rule.
2. Version labels didn't track the code that actually ran.
3. Fingerprints used `str(set)`, which changes with Python's hash seed.

Each fix got its own commit, the old logs were archived, and the loop was re-run from scratch. Run 4 resumes with 0 new iterations under a different hash seed.

## 6. Failures, grouped by cause (train split)
**Missed scams (455 of 513 missed):**
1. *Ordinary-looking admin ads.* "Administrative Assistant" ×13, "Customer Service Representative" ×9, "Payroll Clerk" ×5. The text has no scam words; the scam is in the hiring process, not the ad.
2. *Too-good salaries in the title.* "Account Sales Managers $80-$130,000/yr" ×8, "Agency Sales Managers $150-$175,000/yr" ×7. There is no rule for salary bands vs role (a pay check exists only for Indian fresher roles).
3. *Urgency campaigns.* "Cruise Staff Wanted \*URGENT\*" ×15, one campaign copied 15 times.
4. *Oil & gas / engineering bait.* About 60 missed scams mention oil/gas. These are classic overseas-job scams, and the text reads like a real job.
5. *Money-mule ads (hard set `s13`, "Payment Processing Agent").* `money_transfer_rules` caught none on EMSCAD and blocked 0.8 % real finance jobs, so it was rejected.

**Wrong blocks (16 of 10,289):**
6. *"100% placement" boilerplate from a real staffing agency* (×7, e.g. "Net/C# Web Developer"). The agency's own text matches "guaranteed job".
7. *"Earn from home" wording in real remote jobs* (×7), the cost of the accepted `wfh_money_rules`.
8. *"We'll cover the application fee of $75"* (Crane Operator). The negation was missed; `negation_guard` would fix it but loses a real scam.
9. *India hard set `l04`:* "No registration fee" on a real Data Scientist job is still blocked (same cause). Daksh can press **Not a scam**.

**Fresher filter:**
10. *"Team Lead" in entry-level ads* ("Customer Service Team Lead" ×26). EMSCAD labels these Entry level; the filter hides them. A labelling question as much as a rule bug.
11. *"Manager" titles labelled entry* ("Office Manager", "Account Manager", "Community Manager"). `assistant_not_senior` / `staff_needs_role` helped entry loss but raised senior leak, and were rejected.
12. *Senior jobs with no level words* ("Web Developer" ×11, "Software Engineer" ×9). 668 of 692 leaks are "not stated", shown with a "check level" tag.

## 7. Red team (details: `eval/REDTEAM.md`)
I wrote 53 attack tests; 24 failed before the fixes (commit `7dfff07`), and all pass after them (`0446442`).
- **Critical (both fixed):** cross-site requests could change the tracker and the shield's lessons. Deploy would also upload to a Space that had been made public.
- **High (all fixed):**
  - forged alert senders
  - look-alike and spaced-letter evasion
  - Actions referenced by tag, with a write token next to the API keys
  - a silent all-rules-off fallback
  - test-split access by convention only
  - copied-campaign leakage in the evaluation

## 8. Feedback learning
Daksh has four buttons: **Report scam**, **Not a scam**, **It's senior** and **It's entry**.
- The server looks the post up in its own data, so a forged site can't be reported.
- A single report hides only that one post.
- A whole site is blocked only when all of these hold: 2 or more of its posts were reported, none was marked safe, it isn't a protected platform, and blocking it would not hide a verified job or more than 30 % of the feed.
- Every change is a new version with a snapshot, and there is a rollback command.
- Rules are never edited automatically. The "rules that blocked posts you said were fine" counts are input for a person before the next loop run.
- The evaluation never loads lessons (tested).

## 9. Limitations and next steps
- EMSCAD is US ads from 2012–14, and Indian 2026 scams differ (Telegram task scams, fee-first, UPI mules). The India hard set is small (43) and was written by the builder. **Next:** grow a real India set from Daksh's own reports. The `level_cases` view already scores his "wrong level" reports.
- The text rules catch about 5 % of unseen scam campaigns. **Next:** a salary-vs-role check, and a company-age check on the company's domain.
- Entry loss is about 16 % on test. **Next:** treat "Team Lead" and "Manager" with the description's years, as a new loop candidate measured on train.
- The repo isn't connected to GitHub yet, so nothing is live. Daksh needs to grant access (README step 4 onward).

## 9b. Big companies (added 2026-11-14)
- **Sources.** 8 connectors read companies' own careers systems: amazon.jobs JSON, Google's careers page data, Microsoft's Eightfold search, Workday (11 tenants), and Greenhouse, Lever, Ashby and SmartRecruiters. All 30 were verified from GitHub's servers by `careers/probe.py`. Sites that disallow robots or need a login (Apple, Meta, Netflix…) get links only.
- **Gold sets.** These are frozen and hash-locked:
  - train: 200 random + 60 FAANG+ + 6 audit hard cases
  - test: 100 random, labelled blind
  - The first freeze cut descriptions at 3,000 characters, which a gate-like check caught. It was fixed in its own commit before any tuning.
- **Loop.** 4 runs, all archived:
  - Run 1 was on 200 jobs.
  - Run 2 added the dry-run ideas.
  - Run 3 had train +60 FAANG+, after the dry run showed Amazon was under-covered.
  - Run 4 added a retry pass and the audit hard cases.
  - Test results: family 0.61 → 0.93, level 0.93 → 0.94, ML flag 0.92 → 0.98, non-tech 0.88 → 0.96. Test was scored 3 times (one was the baseline comparison), all logged.
- **Rejected on purpose.**
  - `cv_strict`: it fixes the Prime Video cases but gained only 0.8 points on train.
  - `student_titles` and `genai_ext`: they also fell just under the 1-point bar.
  - These are limits to revisit when more labelled data exists.
- **Legit score.** Its main parts:
  - source and official-host checks
  - text scam signs
  - last-seen
  - Jobs under 55 % are hidden, and the gate refuses to save if any such job would be shown.
- **Resume match.** It is rule-based and grounded:
  - Tests prove that the advice names only skills in the job, quotes only real resume lines, and ignores instructions planted in a job post.
- **Not measured yet.** Match % has no human-judged benchmark, because there are no real resumes yet. **Next:** once Daksh uploads resumes, label 50 job–resume pairs as good, okay or poor fit, and calibrate.

## 9c. Big companies, round 2 (2026-11-18): coverage, robots, eligibility, learning
- **Why only Amazon + Google showed up.** The scheduled runs posted their summaries as GitHub notices, and these showed the cause:
  - Workday answered **429 Too Many Requests** to 9–14 of 30 companies every run, even for robots.txt and even with requests 1.5 s apart.
  - Microsoft failed with 429 once.
  - Meta, Apple and Netflix were links only.
- **Fixes for the blocks.**
  - Requests are paced per site.
  - On 429, a company rests for 6 → 12 → 24 h. Workday is never retried in the same run.
  - At most 6 Workday sites per run, refreshed oldest-first.
  - Search words rotate.
  - Jobs from a company that couldn't be re-checked are kept up to 14 days, marked "not re-checked".
- **Robots audit.** Python's built-in robots reader takes the *first* matching line, but the standard (RFC 9309) says the *longest* match wins. That changed real verdicts:
  - Microsoft allows `/api/pcsx`, so it stays.
  - Google forbids its search-results pages, so it is now a link. It had been read before without any robots check. That was a mistake, now fixed.
  - SmartRecruiters' API forbids all bots except LinkedIn's, so Bosch, ServiceNow, Freshworks and Visa are links.
  - Every run now checks each company's robots.txt with a standard reader (`careers/robots.py`), so a rule change is obeyed at once.
- **Added.**
  - Apple (its search page carries the data; there is no robots.txt).
  - JPMorgan and Oracle (Oracle Recruiting Cloud).
  - Mastercard, Citi, Morgan Stanley, Deutsche Bank, PayPal and Fidelity (Workday).
  - A "Finance & payments" group.
  - Meta needs written permission and Goldman / Netflix disallow bots, so they stay links.
- **Your own companies.** You add a name or a careers link. Links are matched only against known job-system patterns, and the collector builds the API address itself, so a pasted link can't make it fetch arbitrary servers. This was tested with 6 tricky links. A board found by name only gets a lower "real" score and a "check it's the right company" warning (red-team finding).
- **Eligibility.** 50 / 50 on a frozen hand-labelled set. Writing it found a bug that affected every section-based feature: "qualifications" inside "Preferred qualifications" was treated as a required heading. It was fixed at the source, which also corrects resume-match weights.
- **Learning.** The simulated test and the break test are in the README. The break test is why the default order only switches to "For you" after 10 reactions.
- **Process notes.** `tests/test_deploy.py` now compiles every file on the CI Python, after a 3.12-only f-string broke one probe run. Commits are authored as GeekDaksh only.

## 10. AI tool use
Claude drafted all code, tests and documents. Every number in this report comes from a script in `eval/` and was re-run before writing. The bugs found by gates, the loop and the red team were fixed in separate commits, each with its reason.
