"""Feedback learning: voted, tested, versioned, reversible, and never used by the evaluation.
Run: python tests/test_feedback.py"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from common import feedback as FB  # noqa: E402

FAILS = []


def chk(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        FAILS.append(m)


def rep(verdict, url, at, title="Data entry from home", reasons=None, kind="gig"):
    item = {"url": url, "title": title, "why": reasons or []}
    r = FB.make_report(verdict, item, kind)
    r["at"] = at
    return r


shown = [{"url": f"https://www.freelancer.com/projects/{i}", "trust": {"verdict": "likely"}} for i in range(20)]

# one report: that post hidden, site not blocked yet
L, ch = FB.learn([rep("scam", "https://easyjobs-hub.in/job/1", 1)], FB.empty(), shown)
chk(L["hide_urls"] == ["https://easyjobs-hub.in/job/1"] and not L["block_domains"], "1 report hides the post, not the site")
chk(L["pending"] and "needs 2" in L["pending"][0]["why"], "the site waits in pending with the reason")
chk(L["version"] == 1 and L["history"][-1]["snapshot"]["hide_urls"], "the change is a new version with a snapshot")

# second post from the same site: blocked
R = [rep("scam", "https://easyjobs-hub.in/job/1", 1), rep("scam", "https://easyjobs-hub.in/job/2", 2)]
L2, ch = FB.learn(R, L, shown)
chk("easyjobs-hub.in" in L2["block_domains"] and L2["version"] == 2, "2 reported posts from one site block the site (v2)")
chk(FB.learn(R, L2, shown)[0]["version"] == 2, "re-running with no new reports changes nothing (no new version)")
chk(FB.learn(list(reversed(R)), L, shown)[0]["block_domains"] == L2["block_domains"], "same reports in another order → same lessons")

# a duplicate vote on the same post does not count twice
D = FB.add_report(FB.add_report([], rep("scam", "https://x-jobs.in/1", 1)), rep("scam", "https://x-jobs.in/1", 2))
chk(len(D) == 1, "pressing Report twice on one post is one vote")
chk(not FB.learn(D, FB.empty(), shown)[0]["block_domains"], "so one post can't block a site by itself")

# protected sites are never blocked as a whole
P = [rep("scam", f"https://www.linkedin.com/jobs/view/{i}", i) for i in range(6)]
L3, _ = FB.learn(P, FB.empty(), shown)
chk(not L3["block_domains"] and len(L3["hide_urls"]) == 6 and "protected" in L3["pending"][0]["why"],
    "6 reports on LinkedIn hide those 6 posts but never block linkedin.com")

# a site you also marked safe is not blocked, and an earlier block is undone
M = R + [rep("not_scam", "https://easyjobs-hub.in/job/3", 3, reasons=["asks you to pay a fee or deposit"], kind="blocked")]
L4, ch = FB.learn(M, L2, shown)
chk("easyjobs-hub.in" not in L4["block_domains"] and any("unblock" in c for c in ch),
    "marking one post from a blocked site 'not a scam' unblocks the site")
chk(L4["rule_feedback"] == {"asks you to pay a fee or deposit": 1}, "rule feedback counts which rule blocked a post you said was fine")
chk("https://easyjobs-hub.in/job/3" in L4["allow_urls"], "that post is let through")

# the newest vote on a post wins
F = [rep("not_scam", "https://y.in/1", 1, kind="blocked"), rep("scam", "https://y.in/1", 5)]
chk(FB.learn(F, FB.empty(), shown)[0]["hide_urls"] == ["https://y.in/1"], "changing your mind: the newest vote wins")

# test before accepting: verified posts and feed share
V = [rep("scam", "https://acme-ai.com/careers/1", 1), rep("scam", "https://acme-ai.com/careers/2", 2)]
shown_v = shown + [{"url": "https://acme-ai.com/careers/ml-intern", "trust": {"verdict": "verified"}}]
L5, _ = FB.learn(V, FB.empty(), shown_v)
chk(not L5["block_domains"] and "verified" in L5["pending"][0]["why"], "a block that would hide a verified job is not accepted")
big = [{"url": f"https://bulkjobs.in/{i}", "trust": {"verdict": "likely"}} for i in range(12)]
B = [rep("scam", "https://bulkjobs.in/a", 1), rep("scam", "https://bulkjobs.in/b", 2)]
L6, _ = FB.learn(B, FB.empty(), shown[:10] + big)
chk(not L6["block_domains"] and "too many" in L6["pending"][0]["why"], "a block that would wipe >30% of the feed is not accepted")

# rollback
L7 = FB.rollback(L2, 1)
chk(not L7["block_domains"] and L7["hide_urls"] == ["https://easyjobs-hub.in/job/1"] and L7["version"] == 3,
    "rollback to v1 restores v1's lessons as a new version (v3)")
try:
    FB.rollback(L2, 99)
    chk(False, "rollback to a missing version is refused")
except ValueError:
    chk(True, "rollback to a missing version is refused")

# apply(): what the radars do with lessons
r, note = FB.apply({"url": "https://easyjobs-hub.in/job/9"}, [], L2)
chk(r == ["you reported scams from this website before"], "radar: a new post from a blocked site is blocked")
r, note = FB.apply({"url": "https://easyjobs-hub.in/job/3"}, ["asks you to pay a fee or deposit"], L4)
chk(r == [] and "shield had found" in note[0], "radar: a post you allowed shows, with the shield's finding as a warning")
chk(FB.apply({"url": "https://q.in/1"}, ["x"], None) == (["x"], []), "no lessons file → shield works as before")

# bad reports are refused
for bad, what in [(("maybe", {"url": "https://a.in/1"}, "gig"), "unknown verdict"),
                  (("scam", {"url": "javascript:alert(1)"}, "gig"), "non-web link"),
                  (("scam", {"url": "https://a.in/1"}, "admin"), "unknown kind")]:
    try:
        FB.make_report(*bad)
        chk(False, f"report refused: {what}")
    except ValueError:
        chk(True, f"report refused: {what}")

# the evaluation never loads lessons
src = open(os.path.join(ROOT, "eval", "harness.py")).read() + open(os.path.join(ROOT, "eval", "run_eval.py")).read() \
    + open(os.path.join(ROOT, "eval", "loop.py")).read()
chk("feedback" not in src.replace("--feedback", "").replace("a.feedback", "").replace("'wrong level' reports", "")
    .replace("common/feedback.py is not imported", ""), "eval/ never imports the feedback module")
from common import trust  # noqa: E402
chk("lessons" not in trust.scam_reasons.__code__.co_varnames, "scam_reasons (used by the evaluation) takes no lessons")

# ---------------------------------------------------------------- server endpoint
work = os.path.join(ROOT, "tests", ".work", "feedback")
shutil.rmtree(work, ignore_errors=True)
for d in ("gigs", "roles"):
    os.makedirs(os.path.join(work, d))
json.dump({"gigs": [{"id": "g1", "title": "Python scraper", "url": "https://www.freelancer.com/projects/1",
                     "source": "Freelancer.com", "visible": True, "score": 60, "scam": [], "category": "tech"},
                    {"id": "g2", "title": "Typing job", "url": "https://typing-cash.xyz/2", "source": "X",
                     "visible": False, "score": 0, "scam": ["typing / data-entry-from-home pattern"], "category": "other"}]},
          open(os.path.join(work, "gigs", "gigs.json"), "w"))
json.dump({"roles": [{"id": "r1", "title": "ML Intern", "url": "https://boards.greenhouse.io/a/1", "level": "entry",
                      "trust": {"verdict": "verified"}, "source_kind": "ats", "score": 70}], "blocked": []},
          open(os.path.join(work, "roles", "roles.json"), "w"))
os.environ["DATA_DIR"] = work
os.environ.pop("HF_TOKEN", None)
sys.path.insert(0, os.path.join(ROOT, "app"))
import importlib  # noqa: E402
import server  # noqa: E402
importlib.reload(server)
from fastapi.testclient import TestClient  # noqa: E402
c = TestClient(server.app)
H = {"X-Career-Hub": "1"}
x = c.post("/api/feedback", json={"kind": "gig", "id": "g1", "verdict": "scam"}, headers=H)
reps = json.load(open(os.path.join(work, "feedback", "reports.json")))["reports"]
tr = json.load(open(os.path.join(work, "tracker", "tracker.json")))["items"]
chk(x.status_code == 200 and reps[0]["url"] == "https://www.freelancer.com/projects/1" and tr["gig:g1"]["status"] == "hidden",
    "server: Report scam stores the report with the server's own URL and hides the gig now")
x = c.post("/api/feedback", json={"kind": "gig", "id": "nope", "verdict": "scam", "url": "https://rival.com"}, headers=H)
chk(x.status_code == 404, "server: a report about a post that doesn't exist is refused (no forged sites)")
x = c.post("/api/feedback", json={"kind": "gig", "id": "g1", "verdict": "not_scam"}, headers=H)
chk(x.status_code == 400, "server: 'not a scam' is only accepted on blocked posts")
x = c.post("/api/feedback", json={"kind": "blocked", "url": "https://typing-cash.xyz/2", "verdict": "not_scam"}, headers=H)
reps = json.load(open(os.path.join(work, "feedback", "reports.json")))["reports"]
chk(x.status_code == 200 and reps[-1]["reasons"] == ["typing / data-entry-from-home pattern"],
    "server: 'not a scam' on a blocked post records which rule blocked it")
x = c.post("/api/feedback", json={"kind": "role", "id": "r1", "verdict": "senior"}, headers=H)
chk(x.status_code == 200 and c.get("/api/data?fresh=1").json()["lessons"]["reports"] == 3, "server: level report stored; app shows the count")

# ---------------------------------------------------------------- radar uses the lessons
os.makedirs(os.path.join(work, "lessons"), exist_ok=True)
json.dump({**FB.empty(), "version": 4, "block_domains": {"easyjobs-hub.in": {"votes": 2, "since": 1}},
           "allow_urls": ["https://www.freelancer.com/projects/7"]}, open(os.path.join(work, "lessons", "lessons.json"), "w"))
from gigs import radar  # noqa: E402
importlib.reload(radar)
mk = lambda i, url, desc: {"id": f"t{i}", "title": f"Python automation script {i}", "url": url, "source": "Freelancer.com",
                           "posted": None, "desc": desc, "company": "", "work_type": "freelance", "pay_type": "fixed",
                           "budget_min": 8000, "budget_max": 12000, "currency": "INR", "skills": ["Python"]}
radar.collect = lambda state, health: [mk(1, "https://easyjobs-hub.in/p/1", "Build a Python scraper."),
                                       mk(7, "https://www.freelancer.com/projects/7", "Python bot. Contact on telegram."),
                                       mk(8, "https://www.freelancer.com/projects/8", "Python bot. Contact on telegram.")]
radar.ai_note = lambda g: None
out = {g["id"]: g for g in radar.run()}
chk(not out["t1"]["visible"] and "you reported scams from this website before" in out["t1"]["scam"],
    "radar: a gig from a site you blocked is hidden, with the reason")
chk(out["t7"]["scam"] == [] and "you marked this" in out["t7"]["trust"]["warn"][0],
    "radar: the post you allowed is not blocked and carries the warning")
chk(out["t8"]["scam"], "radar: the same text on a post you did NOT allow is still blocked")

print("\nFAILURES:", FAILS)
sys.exit(1 if FAILS else 0)
