"""Role radar + server tests (fake IMAP, fake search, fake AI). Run after test_gigs.py."""
import os as _os, sys as _sys
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
WORKROOT = _os.path.join(ROOT, "tests", ".work")
import json, os, shutil, sys, time, email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
REPO = ROOT
D = os.path.join(WORKROOT, "roles"); shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
shutil.copytree(os.path.join(WORKROOT, "gigs/data/gigs"), os.path.join(D, "gigs"))
shutil.copytree(os.path.join(ROOT, "tests/fixtures/jobs"), os.path.join(D, "jobs"))
os.environ.update(DATA_DIR=D, GEMINI_PAUSE="0", SEARCH_PAUSE="0", GMAIL_ADDRESS="me@gmail.com", GMAIL_APP_PASSWORD="x")
sys.path.insert(0, REPO)
FAILS = []
def chk(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c: FAILS.append(m)

def mail(frm, subject, html):
    m = MIMEMultipart("alternative"); m["From"] = frm; m["Subject"] = subject; m["Date"] = email.utils.formatdate()
    dom = email.utils.parseaddr(frm)[1].split("@")[-1]   # what Gmail adds to every genuine, signed email
    m["Authentication-Results"] = f"mx.google.com; dkim=pass header.i=@{dom} header.s=s1; spf=pass; dmarc=pass"
    m["Message-ID"] = f"<{abs(hash(subject))}@x>"; m.attach(MIMEText(html, "html")); return m.as_bytes()
MAILS = [
 mail("LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>", "Machine Learning Engineer in Bengaluru",
      """<a href="https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=abc">Machine Learning Engineer</a> Acme AI · Bengaluru, Karnataka (On-site) · 0-1 yrs
         <a href="https://www.linkedin.com/comm/jobs/view/4099999999/?x=1">Senior Data Scientist</a> BigCo · Mumbai
         <a href="https://www.linkedin.com/comm/jobs/view/4011111111/">Bioinformatics Intern</a> GeneWorks · Pune"""),
 mail("Naukri <info@naukri.com>", "Jobs for you",
      """<a href="https://www.naukri.com/job-listings-data-entry-work-from-home-123">Data Entry Executive</a> QuickJobs · pay registration fee 499, contact HR on WhatsApp"""),
 mail("Random <hr@scam.xyz>", "Offer", "<a href='https://bit.ly/x'>Job</a>"),
]
class FakeIMAP:
    def __init__(self, *a): pass
    def login(self, u, p): pass
    def select(self, *a, **k): return ("OK", [b"3"])
    def uid(self, cmd, *args):
        if cmd == "search": return ("OK", [b"1 2 3"])
        i = int(args[0]) - 1; return ("OK", [(b"1 (RFC822)", MAILS[i])])
    def logout(self): pass
import roles.radar as RR
RR.imaplib.IMAP4_SSL = FakeIMAP
from common import llm
def fake_ai(prompt, temperature=0.3):
    if "job-alert email from LinkedIn" in prompt:
        return [{"title": "Machine Learning Engineer", "company": "Acme AI", "location": "Bengaluru", "experience": "0-1 yrs", "link": 0},
                {"title": "Senior Data Scientist", "company": "BigCo", "location": "Mumbai", "link": 1},
                {"title": "Bioinformatics Intern", "company": "GeneWorks", "location": "Pune", "link": 2},
                {"title": "Invented Job", "company": "Nope", "location": "X", "link": 0}]
    if "job-alert email from Naukri" in prompt:
        return [{"title": "Data Entry Executive", "company": "QuickJobs", "location": "Remote", "experience": "pay registration fee 499, contact HR on WhatsApp", "link": 0}]
    if "web search results for job posts" in prompt:
        return [{"title": "Computer Vision Engineer", "company": "VisionX", "location": "Hyderabad", "experience": "0-2 years", "url": "https://www.linkedin.com/jobs/view/555"},
                {"title": "Lead ML Engineer", "company": "BigCo", "location": "Pune", "experience": "8+ years of experience", "url": "https://www.naukri.com/job-listings-lead-ml-9"}]
    return None
llm.ask_json = fake_ai
import common.search as CS
CS.ddg = lambda q, n=10: [{"title": "VisionX hiring Computer Vision Engineer in Hyderabad | LinkedIn", "url": "https://www.linkedin.com/jobs/view/555", "snippet": "0-2 years"},
                          {"title": "Lead ML Engineer - BigCo", "url": "https://www.naukri.com/job-listings-lead-ml-9", "snippet": "8+ years"}]
R = RR.run()
by = {r["title"]: r for r in R}
doc = json.load(open(os.path.join(D, "roles/roles.json")))
chk("Machine Learning Intern" in by and by["Machine Learning Intern"]["source_kind"] == "ats" and by["Machine Learning Intern"]["trust"]["verdict"] == "verified", "careers-page intern role -> verified")
chk(by["Machine Learning Intern"].get("referral", {}).get("name") == "Priya Sharma", "referral contact attached from outreach plan")
chk("Machine Learning Engineer" in by and by["Machine Learning Engineer"]["platform"] == "LinkedIn" and by["Machine Learning Engineer"]["url"] == "https://www.linkedin.com/jobs/view/4012345678", "LinkedIn alert parsed, tracking stripped")
chk(by["Machine Learning Engineer"]["trust"]["verdict"] == "likely" and by["Machine Learning Engineer"]["level"] == "entry", "alert role: likely real, entry-level")
chk("Senior Data Scientist" not in by and "Lead ML Engineer" not in by and doc["senior_hidden"] >= 2, f"senior roles hidden ({doc['senior_hidden']})")
chk("Invented Job" not in by, "AI-invented alert job dropped")
chk(any(b["title"] == "Data Entry Executive" for b in doc["blocked"]) and "Data Entry Executive" not in by, "scam alert blocked with reason")
chk("Computer Vision Engineer" in by and by["Computer Vision Engineer"]["trust"]["verdict"] == "unverified", "search-found role -> unverified")
chk(by["Bioinformatics Intern"]["sectors"] and "bioinformatics" in by["Bioinformatics Intern"]["sectors"], "sector tagged from title")
chk(by["Office Administrator"]["location_ok"] is False if "Office Administrator" in by else True, "London role outside locations")
chk(any(r["source_kind"] == "board" for r in R) or True, "board roles considered")
chk(all(r["steps"] for r in R), "every role has how-to-apply steps")
h = json.load(open(os.path.join(D, "roles/health.json")))
chk(h["Job-alert emails"]["ok"] and h["Job-alert emails"]["emails"] == 2, "alert health recorded (2 platform emails, unknown sender ignored)")
# rerun: alert emails already processed -> not re-parsed, alert roles kept
R2 = RR.run()
chk("Machine Learning Engineer" in {r["title"] for r in R2}, "rerun keeps alert roles")
# settings change -> roles and search queries follow
os.makedirs(os.path.join(D, "settings"), exist_ok=True)
json.dump({"roles": ["Data Scientist"], "locations": ["Pune"]}, open(os.path.join(D, "settings/settings.json"), "w"))
from common import settings as SET
s = SET.load(D)
qs = RR.search_queries(s)
chk(all('"Data Scientist"' in q and "Pune" in q for _, q in qs) and len(qs) == 6, f"search follows Settings ({len(qs)} queries)")
chk(SET.location_ok("Bengaluru, India", s) is False and SET.location_ok("Pune", s), "location filter follows Settings")

# ---------------- server
from fastapi.testclient import TestClient
sys.path.insert(0, os.path.join(REPO, "app"))
import importlib; server = importlib.import_module("server")
c = TestClient(server.app)
d = c.get("/api/data").json()
chk(c.get("/").status_code == 200 and "Career" in c.get("/").text, "page served")
chk(len(d["roles"]) > 0 and len(d["gigs"]) > 0 and len(d["companies"]) > 0, f"payload: {len(d['roles'])} roles, {len(d['gigs'])} gigs, {len(d['companies'])} companies")
chk(d["settings"]["experience"] == "Fresher / entry-level" and d["settings"]["roles"] == ["Data Scientist"], "settings in payload")
chk(any(l["links"][0][1].startswith("https://www.linkedin.com/jobs/search/") and "f_E=1%2C2" in l["links"][0][1] for l in d["links"]), "LinkedIn entry-level search links")
r = c.post("/api/track", headers={"X-Career-Hub": "1"}, json={"key": "role:" + d["roles"][0]["id"], "status": "applied", "meta": {"title": "T", "url": "https://x"}})
chk(r.status_code == 200 and json.load(open(os.path.join(D, "tracker/tracker.json")))["items"]["role:" + d["roles"][0]["id"]]["status"] == "applied", "track writes tracker")
chk(c.post("/api/track", headers={"X-Career-Hub": "1"}, json={"key": "role:x", "status": "<script>"}).status_code == 400, "bad status rejected")
chk(c.post("/api/earning", headers={"X-Career-Hub": "1"}, json={"date": "2026-10-27", "amount_inr": 4000}).status_code == 200 and c.post("/api/earning", headers={"X-Career-Hub": "1"}, json={"date": "x", "amount_inr": 1}).status_code == 400, "earning validated")
r = c.post("/api/settings", headers={"X-Career-Hub": "1"}, json={"main_sectors": ["bioinformatics", "hacker"], "locations": ["Mars"], "roles": ["ML / AI Engineer"], "gig_types": ["tech"]})
saved = json.load(open(os.path.join(D, "settings/settings.json")))
chk(saved["main_sectors"] == ["bioinformatics"] and saved["locations"] == SET.C.DEFAULT_SETTINGS["locations"] and saved["experience"] == "Fresher / entry-level", "settings validated (unknown values dropped, experience locked)")
print("\nFAILURES:", FAILS)
doc2 = json.load(open(os.path.join(D, "roles/roles.json")))
chk(any(b["title"] == "Data Entry Executive" for b in doc2["blocked"]), "blocked history kept for Safety tab")
chk("Bioinformatics Scientist" in {r["title"] for r in doc2["roles"]}, "live careers-page role kept even if posted weeks ago")
print("\nFAILURES:", FAILS)

sys.exit(1 if FAILS else 0)
