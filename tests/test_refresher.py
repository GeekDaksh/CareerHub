"""Backup timer: the app starts overdue updates itself if GitHub's schedule skips them.  python tests/test_refresher.py"""
import importlib
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "app"))
FAILS = []


def chk(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        FAILS.append(m)


import refresher as R  # noqa: E402

calls = []


def fake_post(url, token):
    calls.append((url, token))
    return 204


def reset(**env):
    for k in ("GH_DISPATCH_TOKEN", "GITHUB_REPO"):
        os.environ.pop(k, None)
    os.environ.update(env)
    R._last.clear()
    calls.clear()


NOW = 1_800_000_000
reset()
chk(R.check_stale(NOW - 10 * 3600, None, None, NOW, fake_post)["radar"]["ok"] is False and not calls,
    "no token set: nothing is sent, the app works as before")

reset(GH_DISPATCH_TOKEN="github_pat_test", GITHUB_REPO="GeekDaksh/careerhub")
chk(R.check_stale(NOW - 3 * 3600, NOW - 2 * 3600, NOW - 86400, NOW, fake_post) == {} and not calls,
    "fresh data (2 h old): no update started")
out = R.check_stale(NOW - 9 * 3600, NOW - 8 * 3600, None, NOW, fake_post)
chk(out["radar"]["ok"] and calls == [("https://api.github.com/repos/GeekDaksh/careerhub/actions/workflows/gigs.yml/dispatches",
                                      "github_pat_test")], "data 8 h old (a skipped schedule): gig + job radar started")
R.check_stale(NOW - 9 * 3600, None, None, NOW + 60, fake_post)
R.check_stale(NOW - 9 * 3600, None, None, NOW + 600, fake_post)
chk(len(calls) == 1, "opening the app again and again doesn't start it again within 30 minutes")
R.check_stale(NOW - 9 * 3600, None, None, NOW + 31 * 60, fake_post)
chk(len(calls) == 2, "still stale after 30 minutes (e.g. GitHub down): it tries once more")

reset(GH_DISPATCH_TOKEN="t", GITHUB_REPO="GeekDaksh/careerhub")
out = R.check_stale(NOW - 3600, None, NOW - 6 * 86400, NOW, fake_post)
chk(out.get("companies", {}).get("ok") and calls[0][0].endswith("/jobs.yml/dispatches"),
    "company list 6 days old: company finder started")
chk("radar" not in out, "...and the fresh gigs are left alone")

reset(GH_DISPATCH_TOKEN="t", GITHUB_REPO="GeekDaksh/careerhub")
chk(R.dispatch("deploy", "x", NOW, fake_post)["ok"] is False and not calls, "only the two collector workflows can be started")


def boom(url, token):
    raise OSError("401 Bad credentials")


r = R.dispatch("radar", "x", NOW, boom)
chk(r["ok"] is False and "refused" in r["why"], "a bad or expired token is reported, not crashed on")

# ---------------------------------------------------------------- through the server
work = os.path.join(ROOT, "tests", ".work", "refresher")
shutil.rmtree(work, ignore_errors=True)
for d in ("gigs", "roles", "jobs"):
    os.makedirs(os.path.join(work, d))
json.dump({"updated": time.time() - 10 * 3600, "gigs": []}, open(os.path.join(work, "gigs", "gigs.json"), "w"))
json.dump({"updated": time.time() - 10 * 3600, "roles": []}, open(os.path.join(work, "roles", "roles.json"), "w"))
json.dump({"finished_at": time.time() - 86400}, open(os.path.join(work, "jobs", "run_status.json"), "w"))
for k in ("APP_PASSWORD", "RENDER", "HF_TOKEN"):
    os.environ.pop(k, None)
os.environ.update(DATA_DIR=work, GH_DISPATCH_TOKEN="github_pat_SECRET123", GITHUB_REPO="GeekDaksh/careerhub")
import server  # noqa: E402
importlib.reload(server)
R._last.clear()
calls.clear()
R._post = fake_post
from fastapi.testclient import TestClient  # noqa: E402
c = TestClient(server.app)
d = c.get("/api/data").json()
chk(d["refresh"]["enabled"] and d["refresh"]["started"].get("radar", {}).get("ok") and len(calls) == 1,
    "server: opening the app with 10-hour-old data starts the radar once")
chk("SECRET123" not in json.dumps(d) and "SECRET123" not in c.get("/").text, "server: the token never reaches the page")
H = {"X-Career-Hub": "1"}
r = c.post("/api/refresh", json={"what": "radar"}, headers=H).json()
chk(r["ok"] is False and "recently" in r["message"], "Update now right after an automatic start: told it's already running")
r = c.post("/api/refresh", json={"what": "companies"}, headers=H).json()
chk(r["ok"] and calls[-1][0].endswith("/jobs.yml/dispatches"), "Update now (companies): company finder started")
chk(c.post("/api/refresh", json={"what": "deploy"}, headers=H).status_code == 400, "Update now can't start anything else")
chk(c.post("/api/refresh", json={"what": "radar"}).status_code == 403, "Update now needs the app's own header (no cross-site trigger)")

print("\nFAILURES:", FAILS)
sys.exit(1 if FAILS else 0)
