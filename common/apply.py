"""How to apply: per-platform steps, job-alert setup, and one-click filtered searches (incl. LinkedIn).
We never scrape LinkedIn (against its terms, and it gets accounts banned). Instead:
  1) your own job-alert emails are read from your inbox,  2) public job pages are found via web search,
  3) these links open LinkedIn / Naukri / etc. already filtered to entry-level, in your logged-in browser."""
from urllib.parse import quote_plus

import config as C

NAUKRI_CITY = {"Bengaluru": "bangalore", "Delhi NCR": "delhi-ncr", "Mumbai": "mumbai", "Pune": "pune",
               "Hyderabad": "hyderabad", "Chennai": "chennai", "Kolkata": "kolkata", "Ahmedabad": "ahmedabad",
               "Kochi": "kochi", "Jaipur": "jaipur", "Indore": "indore", "Chandigarh": "chandigarh"}

PLAYBOOK = {
    "LinkedIn": {
        "apply": ["Check the 'Seniority level' says Entry level or Internship.",
                  "Easy Apply: send your resume and answer the questions honestly. Otherwise it opens the company site; apply there.",
                  "Open 'Meet the hiring team' and send a connection note (the note on the card is ready, under 200 characters).",
                  "Save the job, then move it to Applied here."],
        "alerts": "Search the role and city. Set Experience to Internship and Entry level, and Date posted to Past 24 hours. "
                  "Then click 'Set alert' → Daily → Email. The alerts land in Gmail, and Career Hub reads them.",
    },
    "Naukri": {
        "apply": ["Keep your profile 100% complete. Put the target role and three key skills in the headline.",
                  "Apply, then update your profile once a week (recruiters filter by 'recently active').",
                  "Ignore any 'recruiter' who asks for money or to continue on WhatsApp."],
        "alerts": "Run a search with Experience 0 years. Click 'Create job alert' → Daily. Use the same Gmail as Career Hub.",
    },
    "Internshala": {
        "apply": ["Answer the assessment questions specifically. Name one project and what you built.",
                  "Add GitHub or project links in the cover letter field.",
                  "Prefer posts with a stated stipend or CTC and an active company profile."],
        "alerts": "Set your preferred roles and cities in Preferences, and turn on email notifications.",
    },
    "Wellfound": {
        "apply": ["Write a 3-line note to the founder: why this startup, one matching project, and when you can start.",
                  "Startups move fast. Follow up once after 4–5 days."],
        "alerts": "Profile → Job preferences: role, India / remote, entry level. Turn on email alerts.",
    },
    "Instahyre": {"apply": ["Complete your profile. Instahyre shows you to recruiters, so respond within a day."],
                  "alerts": "Turn on email notifications for matching roles."},
    "Cutshort": {"apply": ["Answer the screening questions. Short and specific beats long."],
                 "alerts": "Set role + location in your profile and enable email digests."},
    "Indeed": {"apply": ["Prefer 'Apply on company site'. Check the company on its own website."],
               "alerts": "After a search, click 'Get new jobs for this search by email'."},
    "Company careers (ATS)": {
        "apply": ["Apply on the official page. This is the safest kind of job post.",
                  "Mirror the job title's keywords in your resume summary (the card lists which ones).",
                  "Then message the contact from your Companies list to ask for a referral."],
        "alerts": "Career Hub already checks your target companies' careers pages twice a week.",
    },
    "Remote board": {
        "apply": ["Confirm the job is open to India (the card shows the location check).",
                  "Apply on the company's own site. Prepare for a take-home task."],
        "alerts": "Career Hub already checks the remote boards four times a day.",
    },
    "YC Work at a Startup": {"apply": ["One profile reaches all YC startups. Write a clear 'what I've built' section."],
                             "alerts": "Turn on weekly match emails."},
    "Unstop": {"apply": ["Hiring challenges and hackathons. Good for freshers to get noticed by real teams."],
               "alerts": "Follow the companies and categories you want; enable notifications."},
    "Web search": {"apply": ["Open the link and check the job is still open (look for 'no longer accepting applications').",
                             "Apply on the platform or company site. Never through a chat link."],
                   "alerts": ""},
}


def steps_for(platform, kind):
    if kind == "ats":
        return PLAYBOOK["Company careers (ATS)"]["apply"]
    if kind == "board":
        return PLAYBOOK["Remote board"]["apply"]
    if kind == "search":
        return PLAYBOOK["Web search"]["apply"] + PLAYBOOK.get(platform, {}).get("apply", [])[:1]
    return PLAYBOOK.get(platform, PLAYBOOK["Web search"])["apply"]


def keyword_tips(text):
    t = str(text or "").lower()
    return [s for s in C.PROFILE["skills"] if s.lower() in t][:5]


def search_links(role_query, location):
    """One-click searches, filtered to fresher / entry-level, newest first."""
    q = quote_plus(role_query)
    remote = location.startswith("Remote")
    worldwide = location == "Remote (worldwide)"
    loc = "Worldwide" if worldwide else "India" if remote else location
    li = (f"https://www.linkedin.com/jobs/search/?keywords={q}&location={quote_plus(loc)}"
          f"&f_E=1%2C2&f_TPR=r604800&sortBy=DD" + ("&f_WT=2" if remote else ""))
    slug = "-".join(role_query.lower().replace("/", " ").split())
    nk = (f"https://www.naukri.com/{slug}-jobs" + ("" if remote else f"-in-{NAUKRI_CITY.get(location, location.lower())}")
          + "?experience=0")
    g = lambda site: f"https://www.google.com/search?q=site%3A{site}+{q}+{quote_plus(loc)}+fresher&tbs=qdr%3Aw"
    return [
        ("LinkedIn", li),
        ("Naukri", nk),
        ("Google Jobs", f"https://www.google.com/search?q={q}+fresher+jobs+{quote_plus(loc)}&ibp=htl;jobs"),
        ("Indeed", f"https://in.indeed.com/jobs?q={q}+fresher{'+remote' if remote else ''}&l={quote_plus('' if remote else loc)}&fromage=7"),
        ("Internshala", g("internshala.com")),
        ("Wellfound", g("wellfound.com/jobs")),
        ("Instahyre", g("instahyre.com")),
        ("Cutshort", g("cutshort.io")),
        ("YC startups", g("workatastartup.com")),
    ] + ([   # international remote jobs open to India
        ("Himalayas (remote, global)", g("himalayas.app/companies")),
        ("Remotive", g("remotive.com/remote-jobs")),
        ("We Work Remotely", g("weworkremotely.com/remote-jobs")),
        ("Wellfound remote", f"https://www.google.com/search?q=site%3Awellfound.com%2Fjobs+{q}+remote+worldwide&tbs=qdr%3Aw"),
    ] if worldwide else [])
