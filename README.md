# 🎯 Career Hub

One private web app for **paid freelance gigs**, **AI-task platforms** and **startup outreach**. It runs on its own.

| Part | What it does | When it runs |
|---|---|---|
| **Gig radar** | Pulls paid work from Freelancer.com, RemoteOK, Himalayas, Jobicy, Remotive, We Work Remotely and the Hacker News freelancer thread. Hides anything not open to India, scams and low pay. Scores the rest for your skills, and writes a summary and a proposal draft for the best ones. | 4× a day |
| **Morning email** | The best new gigs, two startups to email, and one AI platform to apply to | Daily, ~08:15 IST |
| **Job finder** | Startups in your fields → profiles, funding, key people, graded work emails, outreach plan | Mon + Thu |
| **Web app** | Today · Gigs · AI-task platforms · Companies · Tracker (+ earnings) · Toolkit · Status | Always on (private) |

Everything runs on free tiers: GitHub Actions (private repos get 2,000 min/month; this uses about 1,000–1,300), a Hugging Face private Space + private dataset, Gemini's free API, plus optional free keys.
Your data (contacts, tracker) lives only in the **private** Hugging Face dataset, never in this repo.

---

## One-time setup (~15 minutes)

**1 · Hugging Face** (hosts the app and data, free)
- Sign up at huggingface.co.
- Go to Settings → Access Tokens → **Create new token**. Pick type **Write** and copy it.

**2 · GitHub secrets.** In this repo: Settings → Secrets and variables → Actions → **New repository secret**

| Secret | Needed? | Where to get it |
|---|---|---|
| `HF_TOKEN` | **yes** | step 1 |
| `GEMINI_API_KEY` | **yes** | aistudio.google.com → Get API key |
| `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` | for the morning email | Google Account → Security → 2-Step Verification on → **App passwords** |
| `GROQ_API_KEY` | recommended | console.groq.com (backup AI) |
| `TOMBA_KEY` + `TOMBA_SECRET`, `HUNTER_API_KEY`, `ZEROBOUNCE_API_KEY` | recommended | email finders / verifiers (free plans) |
| `SERPER_API_KEY`, `TAVILY_API_KEY`, `JINA_API_KEY` | optional | better people search / backup search / JS sites |

**3 · Start it.** Open the **Actions** tab and enable workflows if GitHub asks. Then click **Run workflow** on each of these, in order:
1. **Deploy app**: creates your private app. The run summary shows its link.
2. **Gig radar**: first gigs in about 5 minutes.
3. **Job finder**: first companies in about 1–2 hours.

**4 · Open your app:** `https://huggingface.co/spaces/<your-hf-username>/career-hub`. Log in to Hugging Face to see it, because it's private. Bookmark it on your phone.

That's it. From now on it runs, refreshes and redeploys itself.

---

## Good to know
- **Sleep:** after 2 days with no visits, the app sleeps. Opening the link wakes it in about a minute. No clicks needed.
- **Changing things:** edit `config.py` only (skills, projects, cities, gig words, goal). Saving it redeploys the app automatically.
- **If a source breaks:** the **Status** tab shows ❌ for that source and everything else keeps working.
- **Free limits reset:** Gemini daily at ~12:30 IST. Hunter, Tomba, ZeroBounce and Tavily monthly.
