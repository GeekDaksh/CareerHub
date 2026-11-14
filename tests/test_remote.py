"""International remote jobs + dollar-paying gigs: new sources, India eligibility, foreign pay.
Fake network only.   Run: python tests/test_remote.py"""
import copy
import json
import os
import shutil
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "tests", ".work", "remote")
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
os.environ.update(DATA_DIR=WORK, GEMINI_PAUSE="0")
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GROQ_API_KEY", None)
sys.path.insert(0, ROOT)
import config as C  # noqa: E402
from common.config_check import ConfigError, validate  # noqa: E402
from gigs import sources as S  # noqa: E402

FAILS = []
NOW = time.time()
# sample data is dated relative to NOW (fixed dates turned this test into a time bomb once they aged past 10 days)
_d = lambda days, fmt="%Y-%m-%dT%H:%M:%SZ": time.strftime(fmt, time.gmtime(NOW - days * 86400))


def chk(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        FAILS.append(m)


GH = {"jobs": [
    {"id": 1, "title": "Machine Learning Engineer, Intern", "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/1",
     "location": {"name": "Bangalore, India"}, "updated_at": _d(2)},
    {"id": 2, "title": "Backend Engineer", "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/2",
     "location": {"name": "Remote, United States"}, "updated_at": _d(2)},
    {"id": 3, "title": "Associate Support Engineer", "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/3",
     "location": {"name": "Home Based - APAC"}, "updated_at": _d(2)},
    {"id": 4, "title": "Junior Data Analyst", "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/4",
     "location": {"name": "Remote Ireland; Remote, India; Remote, Mexico"}, "updated_at": _d(2)},
    {"id": 5, "title": "", "absolute_url": "https://x/5", "location": {"name": "India"}},
]}
ASHBY = {"jobs": [
    {"id": "a1", "title": "AI Platform Engineer", "jobUrl": "https://jobs.ashbyhq.com/supabase/a1", "location": "Remote, Global",
     "publishedAt": _d(2), "employmentType": "FullTime"},
    {"id": "a2", "title": "Support Engineer (AMER)", "jobUrl": "https://jobs.ashbyhq.com/supabase/a2", "location": "Remote, AMER",
     "secondaryLocations": [], "employmentType": "FullTime"},
    {"id": "a3", "title": "Contract Technical Writer", "jobUrl": "https://jobs.ashbyhq.com/supabase/a3", "location": "Remote, EMEA",
     "secondaryLocations": [{"location": "India"}], "employmentType": "Contract"},
]}
WN = [
    {"url": "https://www.workingnomads.com/jobs/py-1", "title": "Python Automation Developer (Contract)", "description": "<p>Build scripts</p>",
     "company_name": "Lemon.io", "category_name": "Development", "tags": "python,automation", "location": "Worldwide",
     "pub_date": _d(2)},
    {"url": "https://www.workingnomads.com/jobs/us-2", "title": "Data Engineer (Contract)", "description": "Must reside in the US.",
     "company_name": "X", "category_name": "Development", "tags": "data", "location": "USA", "pub_date": _d(2)},
    {"title": "no url"},
]
HN_SEARCH = {"hits": [{"title": "Ask HN: Who is hiring? (October 2026)", "objectID": "900"},
                      {"title": "Ask HN: Freelancer? Seeking freelancer? (October 2026)", "objectID": "901"}]}
HN_ITEM = {"children": [
    {"id": 11, "created_at_i": NOW - 3600, "text": "Acme AI | Junior ML Engineer | REMOTE (Worldwide) | Full-time<p>We use PyTorch."},
    {"id": 12, "created_at_i": NOW - 3600, "text": "Foo | Backend Engineer | REMOTE (US only) | $150k<p>US citizens only."},
    {"id": 13, "created_at_i": NOW - 3600, "text": "Bar | Data Scientist | Onsite NYC<p>Worldwide customers."},
    {"id": 14, "created_at_i": NOW - 3600, "text": "Just a comment about the thread, remote is great, anywhere."},
    {"id": 15, "created_at_i": NOW - 3600, "text": "Qux | AI Research Intern | REMOTE (APAC timezones) | Internship"},
]}
FL = {"result": {"projects": [
    {"id": 71, "title": "Python chatbot with RAG", "seo_url": "py/71", "type": "hourly", "budget": {"minimum": 15, "maximum": 25},
     "currency": {"code": "USD"}, "bid_stats": {"bid_count": 6}, "time_submitted": NOW - 3600,
     "preview_description": "LangChain chatbot over PDFs in Python.", "jobs": [{"name": "Python"}], "language": "en"},
    {"id": 72, "title": "Python scraping script", "seo_url": "py/72", "type": "fixed", "budget": {"minimum": 3000, "maximum": 6000},
     "currency": {"code": "INR"}, "bid_stats": {"bid_count": 3}, "time_submitted": NOW - 3600,
     "preview_description": "Scrape product prices with Python.", "jobs": [{"name": "Python"}], "language": "en"},
    {"id": 73, "title": "Python data cleaning", "seo_url": "py/73", "type": "fixed", "budget": {"minimum": 50000, "maximum": 90000},
     "currency": {"code": "XYZ"}, "bid_stats": {"bid_count": 1}, "time_submitted": NOW - 3600,
     "preview_description": "Clean CSV files in Python pandas.", "jobs": [], "language": "en"},
]}}
DOWN = set()


def fake_get(url, params=None, timeout=30, as_json=True):
    for k in DOWN:
        if k in url:
            raise RuntimeError("503 Service Unavailable")
    if "greenhouse.io" in url:
        return copy.deepcopy(GH)
    if "ashbyhq.com" in url:
        return copy.deepcopy(ASHBY)
    if "workingnomads" in url:
        return copy.deepcopy(WN)
    if "search_by_date" in url:
        return copy.deepcopy(HN_SEARCH)
    if "items/900" in url:
        return copy.deepcopy(HN_ITEM)
    if "items/901" in url:
        return {"children": []}
    if "freelancer.com" in url:
        return copy.deepcopy(FL)
    if "weworkremotely" in url:
        return "<rss><channel></channel></rss>"
    return {"jobs": []} if "remoteok" not in url else []


S.get = fake_get
S.time.sleep = lambda s: None

# ---------------------------------------------------------------- sources on their own
rc = S.remote_companies([{"name": "GitLab", "ats": "greenhouse", "slug": "gitlab"},
                         {"name": "Supabase", "ats": "ashby", "slug": "supabase"}])
titles = {g["title"] for g in rc}
chk({"Machine Learning Engineer, Intern", "Associate Support Engineer", "Junior Data Analyst"} <= titles,
    "company boards: India office, APAC-remote and 'Remote, India' jobs kept")
chk("Backend Engineer" not in titles and "Support Engineer (AMER)" not in titles, "company boards: US-only / AMER-only jobs dropped")
chk("Contract Technical Writer" in titles, "company boards: a secondary India location counts")
chk(all(g["official"] and g["url"].startswith("https://") for g in rc), "company boards: every job marked official with a real link")
chk(next(g for g in rc if g["title"] == "Contract Technical Writer")["work_type"] == "contract", "company boards: contract roles typed as contract")
DOWN.add("ashbyhq.com")
chk(len(S.remote_companies([{"name": "GitLab", "ats": "greenhouse", "slug": "gitlab"},
                            {"name": "Supabase", "ats": "ashby", "slug": "supabase"}])) == 3,
    "company boards: one board down → the others still come through")
DOWN.add("greenhouse.io")
try:
    S.remote_companies([{"name": "GitLab", "ats": "greenhouse", "slug": "gitlab"}, {"name": "Supabase", "ats": "ashby", "slug": "supabase"}])
    chk(False, "company boards: all boards down → the source reports down (Status tab)")
except RuntimeError:
    chk(True, "company boards: all boards down → the source reports down (Status tab)")
DOWN.clear()

wn = S.working_nomads()
chk(len(wn) == 2 and wn[0]["tags"][:2] == ["python", "automation"], "Working Nomads: parsed, broken item skipped, tags split")

hn = S.hn_hiring()
got = {g["company"]: g for g in hn}
chk(set(got) == {"Acme AI", "Qux"}, f"HN Who is hiring: only REMOTE posts open to worldwide/APAC kept ({sorted(got)})")
chk(got["Acme AI"]["title"] == "Junior ML Engineer" and got["Qux"]["work_type"] == "internship",
    "HN Who is hiring: role picked from the 'Company | Role | Location' line")

# ---------------------------------------------------------------- full gig radar run
from gigs import radar  # noqa: E402
radar.ai_note = lambda g: None
gigs = {g["id"]: g for g in radar.run()}
h = json.load(open(os.path.join(WORK, "gigs", "health.json")))
chk(all(h.get(n, {}).get("ok") for n in ("Working Nomads", "HN Who is hiring", "Remote-first companies")),
    "radar: the 3 new sources run and show as working in Status")
usd, inr_, odd = gigs["freelancer:71"], gigs["freelancer:72"], gigs["freelancer:73"]
chk(usd["pay_text"] == "USD 15–25/hr" and usd["pays_foreign"] and usd["intl"], "pay: USD hourly gig shows 'USD 15–25/hr', tagged foreign pay")
chk(round(usd["pay_inr"]) == round(20 * C.FX_TO_INR["USD"]), "pay: rupee estimate uses the configured rate")
chk(inr_["pay_text"] == "INR 3,000–6,000 fixed" and not inr_["pays_foreign"] and not inr_["intl"],
    "pay: an INR client is not marked international")
chk(odd["pay_inr"] is None and not odd["pays_foreign"],
    "pay: an unknown currency is NOT guessed as dollars, and gets no 'Pays in' tag (found in the UI check)")
chk(gigs["wn:https://www.workingnomads.com/jobs/py-1"]["visible"] and gigs["wn:https://www.workingnomads.com/jobs/py-1"]["eligibility"] == "ok",
    "radar: worldwide contract gig from Working Nomads is shown")
chk(not gigs["wn:https://www.workingnomads.com/jobs/us-2"]["visible"], "radar: 'must reside in the US' gig is hidden")
chk(not any(g["visible"] for g in gigs.values() if g["source"] == "Remote-first companies" and g["work_type"] == "full-time"),
    "radar: full-time company jobs are not in Gigs (they go to Career)")

# ---------------------------------------------------------------- role radar picks them up as Career jobs
for d in ("jobs", "roles"):
    os.makedirs(os.path.join(WORK, d), exist_ok=True)
from roles import radar as R  # noqa: E402
boards = {r["url"]: r for r in R.from_boards()}
ml = boards.get("https://job-boards.greenhouse.io/gitlab/jobs/1")
chk(ml is not None and ml["source_kind"] == "ats" and ml["intl"], "career: company-board job arrives as an official (ATS) international job")
chk("https://job-boards.greenhouse.io/gitlab/jobs/2" not in boards, "career: US-only company job never arrives")
chk(any("news.ycombinator.com/item?id=11" in u for u in boards), "career: HN remote-worldwide job arrives")
from common import trust  # noqa: E402
chk(trust.check(ml)["verdict"] == "verified", "career: official company-board job gets the 'Verified source' tag")

# ---------------------------------------------------------------- config gate for the new list
cfg = types.SimpleNamespace(**{k: copy.deepcopy(getattr(C, k)) for k in dir(C) if k.isupper()})
validate(cfg)
for bad, what in [({"name": "X", "ats": "workday", "slug": "x"}, "unknown ATS"),
                  ({"name": "X", "ats": "greenhouse", "slug": "../../admin"}, "path tricks in the slug"),
                  ({"name": "X", "ats": "greenhouse"}, "missing slug")]:
    cfg.REMOTE_COMPANIES = C.REMOTE_COMPANIES + [bad]
    try:
        validate(cfg)
        chk(False, f"config: REMOTE_COMPANIES refuses {what}")
    except ConfigError:
        chk(True, f"config: REMOTE_COMPANIES refuses {what}")

# ---------------------------------------------------------------- job-site links for worldwide remote
from common import apply as AP  # noqa: E402
ww = dict(AP.search_links("Machine Learning Engineer", "Remote (worldwide)"))
inr_links = dict(AP.search_links("Machine Learning Engineer", "Remote (India)"))
chk("location=Worldwide" in ww["LinkedIn"] and "f_WT=2" in ww["LinkedIn"] and "f_E=1%2C2" in ww["LinkedIn"],
    "links: LinkedIn worldwide search is remote + intern/entry only")
chk("Remotive" in ww and "Remotive" not in inr_links, "links: global remote boards appear only for 'Remote (worldwide)'")

print("\nFAILURES:", FAILS)
sys.exit(1 if FAILS else 0)
