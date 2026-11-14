# 🎯 Career Hub

One private web app with two separate sides, **Career** and **Freelance**. It runs on its own and needs no upkeep.

| Side | What you get | Refreshed |
|---|---|---|
| **Big companies** (Career side, first tab) | Vacancies read straight from **30 companies' own careers sites** — Google, Amazon, Microsoft (FAANG+), then NVIDIA, Salesforce, Adobe, Intel, Micron, HP, Applied Materials, Analog Devices, Cadence, Workday, Bosch, ServiceNow, Databricks, Rubrik, Airbnb, Zscaler, GitLab, Elastic, MongoDB, Datadog…, then Freshworks, Meesho, CRED, Sarvam AI. Apple, Meta, Netflix, Qualcomm, Dell, Atlassian, Flipkart and others forbid automated reading, so they get official search links instead. Each job gets: **role family** (GenAI / CV / ML / research / data / software / hardware…), **level and fresher fit**, a **"how sure it's real" %** with every check shown, your **match % per resume**, **which resume to send**, and **what to put in it** (only skills you really have, quoting your own resume lines). Compact rows; click **Details** for the full picture. | 4× a day (companies rotate) |
| **Career** | Fresher / entry-level jobs from your target companies' careers pages, your **LinkedIn, Naukri, Internshala, Wellfound, Indeed…** job-alert emails, remote boards, the monthly HN "Who is hiring?" thread (remote, open to India), the job boards of remote-first global companies (GitLab, Canonical, Elastic, MongoDB, Datadog, Supabase, Zapier; edit `REMOTE_COMPANIES` in `config.py`) and public job pages. An **International only** filter shows jobs at companies abroad. Every job has a scam check, a "how to apply" guide, resume keywords and a referral contact. Plus an applications board, a company outreach list (graded work emails) and one-click filtered searches on every job site. | 4× a day (companies Mon + Thu) |
| **Freelance** | Paid gigs (Freelancer.com, remote boards incl. Working Nomads, the HN freelancer thread). Gigs with a stated $/€/£ budget show the amount and a **Pays in USD** tag, with a filter with scams, non-India and low-pay removed, proposal drafts, AI-task platforms, a pipeline board, an earnings log against your goal, and a toolkit. | 4× a day |
| **Morning email** | 3 jobs to apply to, the best new gigs, 2 startups to email, 1 AI platform | daily ~08:15 IST |

**Settings** (in the app): main sectors, other sectors, locations, target roles and gig types. Experience is fixed to fresher / entry-level.
**Safety:** every post gets a verdict (verified source / likely real / unverified). Risky posts are blocked, and the Safety tab shows the reason.
**LinkedIn:** never scraped (that breaks LinkedIn's terms and gets accounts banned). Career Hub reads your own LinkedIn job-alert emails, finds public LinkedIn job pages via web search, and gives one-click entry-level LinkedIn searches.

Free tiers only: GitHub Actions (private repo, about 1,000–1,300 of 2,000 min/month), Render's free web plan for the app (password-protected), a private Hugging Face dataset for data, Gemini's free API, and optional free keys. Your data (contacts, tracker, settings) lives only in the **private** HF dataset.

---

## One-time setup (~15 minutes)

**1 · Hugging Face:** sign up at huggingface.co. Go to Settings → Access Tokens → **Create new token**, pick type **Write**, and copy it.

**2 · Gmail app password** (for the morning email *and* reading your job-alert emails): Google Account → Security → turn on 2-Step Verification → **App passwords** → create one. If Gmail asks, make sure IMAP is on: Gmail Settings → Forwarding and POP/IMAP.

**3 · Job alerts:** on LinkedIn, Naukri and Internshala (and Wellfound or Indeed if you use them), create job alerts for your roles and cities. Pick *Entry level / Internship* and *daily email*, sent to that same Gmail. The app's **Job sites** tab has the exact steps per site.

**4 · GitHub secrets:** in this repo, go to Settings → Secrets and variables → Actions → **New repository secret**.

| Secret | Needed? | Where |
|---|---|---|
| `HF_TOKEN` | **yes** | step 1 |
| `GEMINI_API_KEY` | **yes** | aistudio.google.com → Get API key |
| `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` | **yes** for alerts + email | step 2 |
| `GROQ_API_KEY` | recommended | console.groq.com (backup AI) |
| `TOMBA_KEY` + `TOMBA_SECRET`, `HUNTER_API_KEY`, `ZEROBOUNCE_API_KEY` | recommended | email finders / verifiers (free plans) |
| `SERPER_API_KEY`, `TAVILY_API_KEY`, `JINA_API_KEY` | optional | better search / backup search / JS sites |

**5 · Start the collectors:** in the **Actions** tab, click **Run workflow** on **Deploy app** (makes the private data store), then **Gig + job radar**, then **Job finder**.

**6 · The app on Render (free):** sign in at render.com with GitHub → **New → Blueprint** → pick this repo. Render reads `render.yaml` and asks for two values: `HF_TOKEN` (same as step 1) and `APP_PASSWORD` (your own login password, 10+ characters). Press **Apply**. Render gives you a link like `https://career-hub-xxxx.onrender.com`.

**7 · Link the morning email to it:** GitHub → Settings → Secrets and variables → Actions → **Variables** → New variable `APP_URL` = your Render link. Bookmark the link on your phone.

From then on it runs, refreshes and redeploys by itself.

## Good to know
- **Backup timer:** GitHub's own schedule sometimes skips runs when GitHub is busy. With `GH_DISPATCH_TOKEN` set in Render (a fine-grained GitHub token for this repo only, permission *Actions: read and write*), the app starts the update itself when you open it and the data is over 7 hours old, and the Status tab gets **Update now** buttons.
- **Sleep:** on Render's free plan the app sleeps after 15 minutes unused. Opening the link wakes it in about a minute. The collectors don't depend on it.
- **Why Render, not Hugging Face Spaces:** since July 2026, Hugging Face charges for Docker/Gradio Spaces on its free plan. The data store stays on Hugging Face (free, private).
- **Login:** the Render link is public, so the app asks for `APP_PASSWORD`. It refuses to show anything if no strong password is set, and slows down guessing (5 tries per 15 minutes).
- **Change sectors, roles, cities or gig types** in the app's ⚙ Settings. **Change your skills or projects** in `config.py`; saving it redeploys automatically.
- **A broken source** shows as down in the Status tab. The others keep working, and its last results are kept.
- **Teach the scam shield:** press **Report scam** on a post (it's hidden at once), **Not a scam** on a blocked post (it comes back with a warning), or **It's senior / It's entry** on a job. The Safety tab shows what it learned. Every change is versioned. To undo, run `DATA_DIR=data python -m common.feedback rollback <version>` after `python -m common.hfstore pull`.

---

## How good is the filtering? (measured, not guessed)

The two filters were tested on **EMSCAD**, a public set of 17,880 real job ads (866 confirmed scams). The ads were split 60 % train and 40 % test. Tuning used train only. The test split was opened **once**, at the end (`eval/test_runs.log` has 1 line).

| On the test split | Before | Final | Plain meaning |
|---|---|---|---|
| Scams blocked | 8.2 % | **12.2 %** | about 1 in 8 scams caught by the text rules alone |
| Real jobs wrongly blocked | 1.0 % | **0.24 %** | about 1 in 400 |
| Senior jobs that still reach you | 27.8 % | **25.1 %** | most are "level not stated" (shown with a "check level" tag) |
| Entry jobs wrongly hidden | 16.0 % | 16.0 % | no change |

**Honest catch:** EMSCAD repeats scam campaigns. Counting only test scams whose campaign never appears in train, the text rules catch **4.9 %**. The rules are a last line of defence. Most of the safety comes from *where* a post comes from: official careers pages, DKIM-checked alert emails, known platforms, and your own reports. Full details are in [`REPORT.md`](REPORT.md) and [`eval/REDTEAM.md`](eval/REDTEAM.md).

## Big companies: how good is the sorting? (measured)

260 real jobs from the 30 careers sites were labelled by hand **before** tuning (`eval/careers/`), and 100 more were
kept apart as a blind test. The classifier is plain rules you can read (`careers/classify.py`), tuned in a logged loop
(`eval/careers/LOOP.md`): 21 tries, 11 kept, 10 rejected by the declared rule.

| On the blind test (n=100) | Before | Final | 95 % range (final) |
|---|---|---|---|
| Role family right | 61 % | **93 %** | 88–98 % |
| Level right | 93 % | **94 %** | 89–98 % |
| "Is this an ML/AI role?" right | 92 % | **98 %** | 95–100 % |
| "Non-technical?" right | 88 % | **96 %** | 92–99 % |

- **Honest catches.**
  - Big-company sites list very few fresher jobs (about 4.5 % fit a fresher, 9 % counting 1–3-year stretch roles), so the fresher numbers rest on very few cases (n=2 in test). Don't trust them yet.
  - The test set was scored 3 times: the first final run, the untuned baseline for comparison, and a final run after adding training data. All are logged in `eval/careers/test_runs.log`.
  - Team names can fool it: "Prime Video" made about 7 of 2,002 jobs look like computer vision. The fix didn't pass the accept rule, so it stays off.
- **"How sure it's real".** This is a rule score, not a measured probability. A job that comes from the company's own careers system, at that company's own web address, gets 95–99 %. A look-alike address or scam words drop it below 55 %, and then it's hidden.
- **Resume match.** It is the share of the job's skills that your resume shows: title ×3, required ×2, other ×1. If the post names fewer than 3 skills, no % is shown. No AI writes the advice, so text inside a job post can't steer it. Resumes are kept as text only, in your private data store.

## For developers

| Command | What it does | Time |
|---|---|---|
| `bash tests/run_all.sh` | every test: gates, feedback learning, both radars, deploy, 53 attack tests | ~1 min |
| `bash eval/fetch_emscad.sh` | download EMSCAD (pinned SHA-256) to `eval/.data/` | ~10 s |
| `python -m eval.run_eval` | metrics on **train**, with 95 % ranges, change vs baseline and calibration | ~30 s |
| `python -m eval.loop` | the improvement loop (train only, resumable, logged in `eval/LOOP.md`) | ~6 min |
| `python -m eval.run_eval --final` | the **test** split, logged. Already run once; don't re-run to tune. | ~30 s |

Layout: `config.py` (every setting, checked at start: unknown keys are an error) · `common/` (scam shield `trust.py`, fresher filter `levels.py`, output gates `gates.py`, feedback learning `feedback.py`) · `gigs/`, `roles/`, `jobs/` (the three collectors) · `app/` (FastAPI + one-page UI) · `eval/` (harness, loop, objective, red-team report) · `tests/`.
