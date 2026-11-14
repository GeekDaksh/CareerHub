"""Gig radar + digest tests with fake sources, fake AI and fake SMTP.  Run: python tests/test_gigs.py"""
import os as _os, sys as _sys
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORKROOT = _os.path.join(ROOT, "tests", ".work")
import json, os, sys, time, shutil
REPO = ROOT; WORK = os.path.join(WORKROOT, "gigs")
shutil.rmtree(WORK, ignore_errors=True); os.makedirs(WORK)
os.environ.update(DATA_DIR=os.path.join(WORK, "data"), GEMINI_PAUSE="0")
sys.path.insert(0, REPO)
NOW = time.time()
# sample data is dated relative to NOW (fixed dates turned this test into a time bomb once they aged past 10 days)
_d = lambda days, fmt="%Y-%m-%dT%H:%M:%SZ": time.strftime(fmt, time.gmtime(NOW - days * 86400))
FAILS = []
def chk(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c: FAILS.append(m)

from gigs import sources as S
FIX = {
 "freelancer": {"result": {"projects": [
   {"id": 1, "title": "Python web scraping script for e-commerce prices", "seo_url": "python/scraper-1", "type": "fixed",
    "budget": {"minimum": 5000, "maximum": 12000}, "currency": {"code": "INR"}, "bid_stats": {"bid_count": 4},
    "time_submitted": NOW - 3600, "preview_description": "Need a scraper with requests/BeautifulSoup, export CSV.",
    "jobs": [{"name": "Python"}, {"name": "Web Scraping"}], "language": "en"},
   {"id": 2, "title": "Build RAG chatbot with LangChain and FAISS", "seo_url": "ai/rag-2", "type": "hourly",
    "budget": {"minimum": 15, "maximum": 25}, "currency": {"code": "USD"}, "bid_stats": {"bid_count": 12},
    "time_submitted": NOW - 7200, "preview_description": "LLM chatbot over PDFs, Python, FAISS vector store.", "jobs": [], "language": "en"},
   {"id": 3, "title": "Data entry job earn Rs 2000 per day", "seo_url": "x/3", "type": "fixed",
    "budget": {"minimum": 100, "maximum": 200}, "currency": {"code": "USD"}, "bid_stats": {"bid_count": 3},
    "time_submitted": NOW - 3600, "preview_description": "Pay registration fee then contact on telegram. python automation", "jobs": [], "language": "en"},
   {"id": 4, "title": "Machine learning model tuning", "seo_url": "ml/4", "type": "hourly",
    "budget": {"minimum": 2, "maximum": 4}, "currency": {"code": "USD"}, "bid_stats": {"bid_count": 50},
    "time_submitted": NOW - 3600, "preview_description": "Tune a scikit-learn model", "jobs": [], "language": "en"},
 ]}},
 "remoteok": [{"legal": "notice"},
   {"id": 11, "position": "AI Trainer – Python coding expert (contract)", "company": "EvalCo", "tags": ["contract", "python"],
    "description": "Evaluate LLM code answers. RLHF.", "epoch": NOW - 5000, "location": "Worldwide", "url": "https://remoteok.com/11",
    "salary_min": 0, "salary_max": 0},
   {"id": 12, "position": "Senior ML Engineer", "company": "BigCo", "tags": ["full-time"], "description": "US only. Must be located in the US.",
    "epoch": NOW - 5000, "location": "United States", "url": "https://remoteok.com/12"}],
 "himalayas": {"jobs": [
   {"title": "Technical Writer (Freelance) – ML tutorials", "companyName": "DocsLab", "employmentType": "Freelance",
    "locationRestrictions": ["India", "Philippines"], "minSalary": 20, "maxSalary": 30, "currency": "USD", "salaryPeriod": "hourly",
    "description": "<p>Write machine learning tutorials in Python.</p>", "pubDate": NOW - 10000, "applicationLink": "https://him/1", "guid": "https://him/1", "categories": ["Writing"]},
   {"title": "Social Media Manager (Part-time)", "companyName": "Brandy", "employmentType": "Part Time",
    "locationRestrictions": ["United States"], "description": "Instagram growth", "pubDate": NOW - 10000, "applicationLink": "https://him/2", "guid": "https://him/2"}],
   "nextCursor": None},
 "jobicy": {"jobs": [{"id": 21, "url": "https://jobicy/21", "jobTitle": "LLM Evaluation Specialist (Contract)", "companyName": "EvalCo",
    "jobIndustry": ["AI"], "jobType": ["contract"], "jobGeo": "Anywhere", "jobDescription": "Evaluate model outputs, python", "pubDate": _d(1, "%Y-%m-%d %H:%M:%S")},
    {"id": 22, "url": "https://jobicy/22", "jobTitle": "Old gig", "companyName": "X", "jobType": ["contract"], "jobGeo": "Anywhere",
     "jobDescription": "python", "pubDate": "2026-01-01 08:00:00"}]},
 "remotive": {"jobs": [{"id": 31, "url": "https://remotive/31", "title": "Python automation freelancer (n8n, APIs)", "company_name": "AutoCo",
    "job_type": "freelance", "publication_date": _d(1, "%Y-%m-%dT%H:%M:%S"), "candidate_required_location": "Worldwide", "description": "automation with python and n8n"}]},
 "wwr": """<?xml version="1.0"?><rss><channel><item><title>Acme: Computer Vision Contractor</title><link>https://wwr/1</link>
   <guid>https://wwr/1</guid><pubDate>""" + _d(1, "%a, %d %b %Y %H:%M:%S +0000") + """</pubDate><region>Anywhere in the World</region><type>Contract</type>
   <description>&lt;p&gt;OpenCV, PyTorch, YOLO&lt;/p&gt;</description></item></channel></rss>""",
 "hn_search": {"hits": [{"objectID": "999", "title": "Ask HN: Freelancer? Seeking freelancer? (October 2026)"}]},
 "hn_item": {"children": [{"id": 1001, "created_at_i": NOW - 20000, "text": "SEEKING FREELANCER | Remote | Need a PyTorch dev to fine-tune a vision model. Budget $2k."},
                          {"id": 1002, "created_at_i": NOW - 20000, "text": "SEEKING WORK | me"}]},
}
CALLS = {"remotive": 0}
def fake_get(url, params=None, timeout=30, as_json=True):
    if "freelancer.com" in url: return FIX["freelancer"]
    if "remoteok" in url: return FIX["remoteok"]
    if "himalayas" in url: return FIX["himalayas"]
    if "jobicy" in url: return FIX["jobicy"]
    if "remotive" in url: CALLS["remotive"] += 1; return FIX["remotive"]
    if "weworkremotely" in url: return FIX["wwr"]
    if "search_by_date" in url: return FIX["hn_search"]
    if "algolia.com/api/v1/items" in url: return FIX["hn_item"]
    raise RuntimeError("unexpected " + url)
S.get = fake_get
S.time.sleep = lambda s: None

from common import llm
AI = {"n": 0}
def fake_ai(prompt, temperature=0.3):
    AI["n"] += 1
    return {"summary": "They want X.", "est_hours": 6, "fit_1_10": 8, "why_fit": "matches", "red_flags": [],
            "proposal": "Your scraper needs... I built ... First I'd ... Which sites first?"}
llm.ask_json = fake_ai

from gigs import radar
g1 = radar.run()
by = {g["title"]: g for g in g1}
vis = [g for g in g1 if g["visible"]]
chk(len(g1) >= 9, f"collected from all sources ({len(g1)})")
chk(by["Python web scraping script for e-commerce prices"]["visible"] and by["Python web scraping script for e-commerce prices"]["category"] == "tech", "Freelancer scraping gig shown, tech")
chk(not by["Data entry job earn Rs 2000 per day"]["visible"] and by["Data entry job earn Rs 2000 per day"]["scam"], "scam gig hidden with reasons: " + str(by["Data entry job earn Rs 2000 per day"]["scam"]))
chk(not by["Machine learning model tuning"]["visible"], "hourly under ₹500 hidden")
chk(by["Senior ML Engineer"]["eligibility"] == "blocked" and not by["Senior ML Engineer"]["visible"], "US-only job blocked")
chk(by["Social Media Manager (Part-time)"]["eligibility"] == "blocked", "Himalayas US restriction blocked")
chk(by["Technical Writer (Freelance) – ML tutorials"]["eligibility"] == "ok" and by["Technical Writer (Freelance) – ML tutorials"]["visible"], "India-allowed writing gig shown")
chk(by["AI Trainer – Python coding expert (contract)"]["category"] == "ai_tasks", "AI trainer -> ai_tasks")
chk("Old gig" not in by, "gigs older than 10 days dropped")
chk(any(g["source"] == "Hacker News" and "PyTorch" in g["title"] for g in g1) and not any("SEEKING WORK" in g["desc"] for g in g1), "HN: only SEEKING FREELANCER posts")
chk(any(g["source"] == "We Work Remotely" and g["company"] == "Acme" and g["eligibility"] == "ok" for g in g1), "WWR parsed, anywhere = ok")
chk(all(g.get("ai") for g in vis if g["score"] >= 45)[:1] if False else sum(1 for g in vis if g.get("ai")) == AI["n"] and AI["n"] > 0, f"AI notes for top gigs ({AI['n']})")
chk(abs(by["Build RAG chatbot with LangChain and FAISS"]["pay_inr"] - 20 * 88) < 1, "USD hourly converted to INR")
top = vis[0]; print("   top gig:", top["title"], top["score"], top["why"])
# run 2: no new AI calls, first_seen kept, Remotive throttled
first = {g["id"]: g["first_seen"] for g in g1}
AI["n"] = 0; radar.NOW = NOW + 3600
g2 = radar.run()
chk(AI["n"] == 0, "rerun: no repeat AI calls")
chk(all(first.get(g["id"]) == g["first_seen"] for g in g2 if g["id"] in first), "rerun keeps first_seen")
chk(CALLS["remotive"] == 1 and any(g["source"] == "Remotive" for g in g2), "Remotive called once in 11 h, its gigs kept")
# a broken source doesn't break the run
orig = S.remoteok; S.remoteok = lambda: (_ for _ in ()).throw(RuntimeError("503"))
g3 = radar.run(); S.remoteok = orig
h = json.load(open(os.path.join(WORK, "data/gigs/health.json")))
chk(not h["RemoteOK"]["ok"] and h["Freelancer.com"]["ok"] and any(g["source"] == "RemoteOK" for g in g3), "failing source: others work, its last gigs kept, health shows it")

# ---------------- digest
from notify import digest
sent = {}
class FakeSMTP:
    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def login(self, u, p): sent["login"] = u
    def sendmail(self, f, to, msg): sent["to"] = to; sent["msg"] = msg
digest.smtplib.SMTP_SSL = FakeSMTP
os.environ.update(GMAIL_ADDRESS="me@gmail.com", GMAIL_APP_PASSWORD="x", APP_URL="https://career-hub.onrender.com")
os.makedirs(os.path.join(WORK, "data/tracker"), exist_ok=True)
json.dump({"items": {f"gig:{top['id']}": {"status": "applied"}}, "earnings": [{"date": digest.datetime.now(digest.IST).strftime("%Y-%m-%d"), "amount_inr": 3000}]},
          open(os.path.join(WORK, "data/tracker/tracker.json"), "w"))
digest.main(force=True)
import email, quopri
raw = sent.get("msg", "")
m = email.message_from_string(raw)
body = next((p.get_payload(decode=True).decode() for p in m.walk() if p.get_content_type() == "text/html"), "")
chk(sent.get("to") == ["me@gmail.com"] and "Open Career Hub" in body and "career-hub.onrender.com" in body, "digest sent with the Render app link")
chk(top["title"] not in body, "applied gig not repeated in digest")
chk("₹3,000" in body, "earnings shown in digest")
st = json.load(open(os.path.join(WORK, "data/gigs/state.json")))
sent.clear(); digest.main()
chk(not sent and st.get("digest_last_day"), "digest only once a day")
print("\nFAILURES:", FAILS)

sys.exit(1 if FAILS else 0)
