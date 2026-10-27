# 🎯 Career Hub

One private web app with two separate sides, **Career** and **Freelance**. It runs on its own and needs no upkeep.

| Side | What you get | Refreshed |
|---|---|---|
| **Career** | Fresher / entry-level jobs from your target companies' careers pages, your **LinkedIn, Naukri, Internshala, Wellfound, Indeed…** job-alert emails, remote boards and public job pages. Every job has a scam check, a "how to apply" guide, resume keywords and a referral contact. Plus an applications board, a company outreach list (graded work emails) and one-click filtered searches on every job site. | 4× a day (companies Mon + Thu) |
| **Freelance** | Paid gigs (Freelancer.com, remote boards, the HN freelancer thread) with scams, non-India and low-pay removed, proposal drafts, AI-task platforms, a pipeline board, an earnings log against your goal, and a toolkit. | 4× a day |
| **Morning email** | 3 jobs to apply to, the best new gigs, 2 startups to email, 1 AI platform | daily ~08:15 IST |

**Settings** (in the app): main sectors, other sectors, locations, target roles and gig types. Experience is fixed to fresher / entry-level.
**Safety:** every post gets a verdict (verified source / likely real / unverified). Risky posts are blocked, and the Safety tab shows the reason.
**LinkedIn:** never scraped (that breaks LinkedIn's terms and gets accounts banned). Career Hub reads your own LinkedIn job-alert emails, finds public LinkedIn job pages via web search, and gives one-click entry-level LinkedIn searches.

Free tiers only: GitHub Actions (private repo, about 1,000–1,300 of 2,000 min/month), a private Hugging Face Space + private dataset, Gemini's free API, and optional free keys. Your data (contacts, tracker, settings) lives only in the **private** HF dataset.

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

**5 · Start it:** in the **Actions** tab, click **Run workflow** on **Deploy app**, then **Gig + job radar**, then **Job finder**.

**6 · Open:** `https://huggingface.co/spaces/<your-hf-username>/career-hub` (log in to Hugging Face — it's private). Bookmark it on your phone.

From then on it runs, refreshes and redeploys by itself.

## Good to know
- **Sleep:** after 2 days with no visits, the app sleeps. Opening the link wakes it in about a minute.
- **Change sectors, roles, cities or gig types** in the app's ⚙ Settings. **Change your skills or projects** in `config.py`; saving it redeploys automatically.
- **A broken source** shows as down in the Status tab. The others keep working, and its last results are kept.
