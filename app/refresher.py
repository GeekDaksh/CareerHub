"""Backup timer for the collectors.

GitHub's own schedule (cron) can skip or delay runs for hours when GitHub is busy (it skipped one on day 1).
So the app also starts the update itself, through GitHub's API:
  • when you open the app and the gigs/jobs are older than STALE_HOURS (one request, then it waits)
  • when the company list is older than COMPANY_STALE_DAYS
  • when you press "Update now" on the Status tab (at most once per COOLDOWN_MIN)

It needs GH_DISPATCH_TOKEN in Render's settings: a fine-grained GitHub token for this one repository with
only "Actions: read and write". Without it nothing happens and the app works as before.
The token stays on the server; the page never sees it.
"""
import json
import os
import threading
import time
import urllib.request

STALE_HOURS = 7            # gigs/jobs normally refresh every 6 h
COMPANY_STALE_DAYS = 5     # company finder normally runs Mon + Thu
COOLDOWN_MIN = 30          # never start the same update twice within this time
WORKFLOWS = {"radar": "gigs.yml", "companies": "jobs.yml"}

_last = {}                 # workflow key -> time we last asked GitHub
_lock = threading.Lock()


def _token():
    return os.environ.get("GH_DISPATCH_TOKEN") or ""


def _repo():
    return os.environ.get("GITHUB_REPO") or ""


def _post(url, token):
    req = urllib.request.Request(url, data=json.dumps({"ref": "main"}).encode(), method="POST", headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "career-hub"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status


def dispatch(key, reason, now=None, post=None):
    """Ask GitHub to run one workflow now. Returns a status dict; never raises."""
    now = now or time.time()
    token, repo = _token(), _repo()
    if key not in WORKFLOWS:
        return {"ok": False, "why": "unknown update"}
    if not token or not repo:
        return {"ok": False, "why": "not set up (GH_DISPATCH_TOKEN missing)"}
    with _lock:
        if now - _last.get(key, 0) < COOLDOWN_MIN * 60:
            return {"ok": False, "why": "already started recently", "at": _last[key]}
        _last[key] = now
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOWS[key]}/dispatches"
    try:
        code = (post or _post)(url, token)
    except Exception as e:             # network or token problem: allow a retry after the cooldown
        return {"ok": False, "why": f"GitHub refused: {str(e)[:120]}", "at": now}
    ok = code in (200, 201, 204)
    print(f"refresher: {key} ({reason}) -> HTTP {code}")
    return {"ok": ok, "why": reason if ok else f"GitHub answered {code}", "at": now}


def check_stale(gigs_updated, roles_updated, companies_finished, now=None, post=None):
    """Called when the app builds its data. Starts whatever is overdue, in the background-safe way above."""
    now = now or time.time()
    out = {}
    newest = max([t for t in (gigs_updated, roles_updated) if t] or [0])
    if newest and now - newest > STALE_HOURS * 3600:
        out["radar"] = dispatch("radar", f"gigs/jobs {int((now - newest) / 3600)} h old", now, post)
    if companies_finished is not None and now - companies_finished > COMPANY_STALE_DAYS * 86400:
        out["companies"] = dispatch("companies", "company list overdue", now, post)
    return out


def state():
    return {"enabled": bool(_token() and _repo()), "last": dict(_last)}
