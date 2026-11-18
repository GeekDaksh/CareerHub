"""Three profiles (Daksh, Aruja, Lubhana) on one app: each signs in with their own password and sees only their
own resumes, likes, applications, companies and profile. Public job lists are shared; Daksh's private things
(freelance, outreach contacts, scam reports, radar settings) are his alone.   python tests/test_profiles.py"""
import base64
import importlib
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "tests", ".work", "profiles")
shutil.rmtree(WORK, ignore_errors=True)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "app"))
FAILS = []
H = {"X-Career-Hub": "1"}
PW = {"daksh": "daksh-password-123", "aruja": "aruja-password-456", "lubhana": "lubhana-password-789"}


def chk(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        FAILS.append(m)


# shared public data: two official jobs (one ML, one needing a PhD) + a job only Aruja's company produces
os.makedirs(os.path.join(WORK, "careers"))
os.makedirs(os.path.join(WORK, "jobs"))
os.makedirs(os.path.join(WORK, "gigs"))
json.dump({"gigs": [{"id": "g1", "title": "Daksh's gig", "url": "https://x.com/g", "source": "x", "visible": True}]},
          open(os.path.join(WORK, "gigs", "gigs.json"), "w"))
open(os.path.join(WORK, "jobs", "contacts.csv"), "w").write("company,name,email,key_contact\nAcme,Secret Person,secret@acme.com,True\n")


def job(i, title, desc="Minimum qualifications: Bachelor's degree. Python, PyTorch, SQL.", owners=None, company="Amazon"):
    j = {"id": f"off:x:{i}", "company": company, "company_tier": "FAANG+", "company_rank": 1, "title": title,
         "url": f"https://www.amazon.jobs/{i}", "location": "Bengaluru", "posted": time.time(), "last_seen": time.time(),
         "desc": desc, "family": "ML Engineer / Applied Scientist", "fresher_fit": "fits", "level": "New grad / entry",
         "is_ml": True, "specialties": [], "skills": [{"skill": "Python", "weight": 2}, {"skill": "PyTorch", "weight": 2},
                                                      {"skill": "SQL", "weight": 1}],
         "legit": {"pct": 99, "band": "Very high", "checks": []}, "visible": True, "employment": "Full-time", "work_mode": "Not stated"}
    if owners:
        j["owners"] = owners
    return j


json.dump({"updated": time.time(), "jobs": [job(1, "ML Engineer"), job(2, "Research Scientist, PhD"),
                                            job(3, "ML Intern", owners=["aruja"], company="ArujaCo")],
           "companies": [{"name": "Amazon", "tier": "FAANG+", "auto": True},
                         {"name": "ArujaCo", "tier": "Startup", "auto": True, "custom": True, "owners": ["aruja"]}],
           "links": [{"name": "LubhanaLink", "tier": "Startup", "url": "https://l.example", "owners": ["lubhana"]}], "health": {}},
          open(os.path.join(WORK, "careers", "official.json"), "w"))

for k in ("APP_PASSWORD", "APP_PASSWORD_ARUJA", "APP_PASSWORD_LUBHANA", "SESSION_SECRET", "RENDER", "HF_TOKEN"):
    os.environ.pop(k, None)
os.environ.update(DATA_DIR=WORK, RENDER="true", SESSION_SECRET="s" * 40, APP_PASSWORD=PW["daksh"], APP_PASSWORD_ARUJA=PW["aruja"])
from fastapi.testclient import TestClient  # noqa: E402
import server  # noqa: E402
importlib.reload(server)
server.FLUSH_AFTER = 0.05


def client(u, pw=None):
    c = TestClient(server.app, base_url="https://testserver", follow_redirects=False)
    r = c.post("/login", data={"user": u, "password": pw or PW[u]})
    return c, r


# ---------------------------------------------------------------- signing in
d, r = client("daksh")
chk(r.status_code == 303, "Daksh signs in with his password")
a, r = client("aruja")
chk(r.status_code == 303, "Aruja signs in with hers")
_, r = client("aruja", PW["daksh"])
chk(r.status_code == 401, "Daksh's password does NOT open Aruja's profile")
_, r = client("daksh", PW["aruja"])
chk(r.status_code == 401, "Aruja's password does NOT open Daksh's profile")
_, r = client("lubhana", "anything-long-enough")
chk(r.status_code == 401 and "isn't set up yet" in r.text, "a profile with no password set can't be opened (fails closed)")
_, r = client("../daksh", PW["daksh"])
chk(r.status_code == 401, "an invented profile name is refused")
chk(client("daksh")[0].cookies.get("ch_session").startswith("daksh."), "the session records which profile signed in")
chk("Aruja" in d.get("/login").text and "Lubhana" in d.get("/login").text, "login page lets you pick the profile")

# ---------------------------------------------------------------- shared public jobs, private everything else
dd, ad = d.get("/api/data").json(), a.get("/api/data").json()
chk(dd["user"]["owner"] and not ad["user"]["owner"] and ad["user"]["name"] == "Aruja", "each page knows whose it is")
chk(ad["gigs"] == [] and ad["companies"] == [] and ad["blocked"] == [] and ad["health"]["files"] == {},
    "Aruja's page carries none of Daksh's gigs, outreach companies or contacts")
chk("secret@acme.com" not in json.dumps(ad), "Daksh's outreach contact emails never reach another profile")
chk("Daksh's gig" not in json.dumps(ad) and "Daksh Patil" not in json.dumps(ad), "…nor his gigs or his name / profile")
ids = lambda D: {x["id"] for x in D["careers"]["rows"]}
chk({"off:x:1", "off:x:2"} <= ids(dd) and {"off:x:1", "off:x:2"} <= ids(ad), "public big-company jobs are shared")
chk("off:x:3" in ids(ad) and "off:x:3" not in ids(dd), "a job from a company Aruja added is shown only to Aruja")
chk(d.get("/api/job", params={"id": "off:x:3"}).status_code == 404, "…and Daksh can't open it by guessing its id")
chk(all(c["name"] != "ArujaCo" for c in dd["careers"]["companies"]), "Aruja's companies aren't in Daksh's company list")
chk(all(l["name"] != "LubhanaLink" for l in ad["careers"]["links"]), "Lubhana's link isn't in Aruja's list")

# ---------------------------------------------------------------- resumes
txt = base64.b64encode(("Python PyTorch SQL project line\n" * 20).encode()).decode()
chk(a.post("/api/resume", json={"name": "Aruja CV", "filename": "cv.txt", "data": txt}, headers=H).status_code == 200,
    "Aruja uploads a resume")
dd, ad = d.get("/api/data?fresh=1").json(), a.get("/api/data?fresh=1").json()
chk([r["name"] for r in ad["resumes"]] == ["Aruja CV"] and dd["resumes"] == [], "her resume is hers only")
chk(os.path.exists(os.path.join(WORK, "users", "aruja", "resumes", "resumes.json"))
    and not os.path.exists(os.path.join(WORK, "resumes", "resumes.json")), "stored under her own folder")
chk(any(x["match"] is not None for x in ad["careers"]["rows"]) and all(x["match"] is None for x in dd["careers"]["rows"]),
    "match % uses each profile's own resumes")
chk(d.post("/api/resume/delete", json={"name": "Aruja CV"}, headers=H).status_code == 404, "Daksh can't delete her resume")

# ---------------------------------------------------------------- likes / learning
for i in (1, 2):
    a.post("/api/react", json={"id": f"off:x:{i}", "r": "like"}, headers=H)
time.sleep(0.3)
dd, ad = d.get("/api/data?fresh=1").json(), a.get("/api/data?fresh=1").json()
chk(all(x["r"] is None for x in dd["careers"]["rows"]) and any(x["r"] == "like" for x in ad["careers"]["rows"]),
    "Aruja's likes don't show on Daksh's page")
chk(dd["careers"]["learn"]["reactions"] == 0 and ad["careers"]["learn"]["reactions"] == 2, "each profile learns only from its own clicks")
chk(d.post("/api/learn/reset", json={"confirm": "reset"}, headers=H).status_code == 200
    and a.get("/api/data?fresh=1").json()["careers"]["learn"]["reactions"] == 2, "Daksh's reset doesn't touch Aruja's learning")

# ---------------------------------------------------------------- applications tracker
a.post("/api/track", json={"key": "role:off:x:1", "status": "applied"}, headers=H)
chk("role:off:x:1" not in d.get("/api/data?fresh=1").json()["tracker"]["items"], "Aruja's applications aren't in Daksh's tracker")
chk(a.post("/api/track", json={"key": "gig:g1", "status": "bid"}, headers=H).status_code == 400,
    "Aruja's profile has no freelance tracker")

# ---------------------------------------------------------------- owner-only things
for path, body in [("/api/settings", {}), ("/api/feedback", {"kind": "gig", "verdict": "scam", "id": "g1"}),
                   ("/api/earning", {"date": "2026-11-18", "amount_inr": 100}), ("/api/refresh", {"what": "radar"})]:
    chk(a.post(path, json=body, headers=H).status_code == 403, f"Aruja can't use {path} (Daksh-only: private or steers shared radars)")
chk(a.get("/api/export.xlsx").status_code == 403, "Aruja can't download Daksh's company / contact sheet")

# ---------------------------------------------------------------- each profile's own profile + eligibility
chk(a.post("/api/profile", json={"degree": "master", "grad_year": 2026}, headers=H).status_code == 200, "Aruja saves her profile")
ad = a.get("/api/data?fresh=1").json()
chk(ad["me"]["degree"] == "master" and ad["careers"]["profile"]["grad_year"] == 2026, "her degree / year are hers")
chk(d.post("/api/profile", json={"degree": "phd"}, headers=H).status_code == 400, "Daksh's profile comes from config.py, not this form")
chk(a.post("/api/profile", json={"degree": "wizard"}, headers=H).status_code == 400
    and a.post("/api/profile", json={"degree": "bachelor", "grad_year": "1999; drop"}, headers=H).status_code == 400,
    "bad profile values refused")
a.post("/api/profile", json={"degree": "phd", "grad_year": 2026}, headers=H)
ad, dd = a.get("/api/data?fresh=1").json(), d.get("/api/data?fresh=1").json()
el = lambda D, i: [x for x in D["careers"]["rows"] if x["id"] == i][0]["elig"]["ok"]
chk(el(ad, "off:x:2") and not el(dd, "off:x:2"), "a PhD role: eligible for a PhD profile, hidden for Daksh (B.Tech)")

a.post("/api/profile", json={"degree": "bachelor", "grad_year": 2027, "field": "Civil engineering <script>"}, headers=H)
ad = a.get("/api/data?fresh=1").json()
chk(ad["links"] and ad["links"][0]["role"] == "Civil engineering script" and "Civil+engineering" in json.dumps(ad["links"][0]["links"]),
    "her own field drives her job-site links (cleaned of odd characters)")

# ---------------------------------------------------------------- sessions
pw_before = os.environ["APP_PASSWORD_ARUJA"]
os.environ["APP_PASSWORD_ARUJA"] = "a-brand-new-password"
chk(a.get("/api/data").status_code == 401, "changing Aruja's password signs out her old sessions")
chk(d.get("/api/data").status_code == 200, "…without signing out Daksh")
os.environ["APP_PASSWORD_ARUJA"] = pw_before

print(f"\n{len(FAILS)} failed" if FAILS else "\nall profile checks passed")
sys.exit(1 if FAILS else 0)
