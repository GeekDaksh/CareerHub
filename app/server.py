"""Career Hub web server (runs in the private Hugging Face Space).
Serves the single-page app and a small JSON API over the private dataset."""
import csv
import hashlib
import hmac
import io
import json
import math
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

import config as C
from common import apply as AP
from common import feedback as FB
from common import settings as SETTINGS
from common import trust

HF_TOKEN = os.environ.get("HF_TOKEN")
DATA_REPO = os.environ.get("DATA_REPO")
if HF_TOKEN and not DATA_REPO:          # same default as common/hfstore.py: <your-hf-username>/career-hub-data
    try:
        from huggingface_hub import HfApi
        DATA_REPO = f"{HfApi(token=HF_TOKEN).whoami()['name']}/career-hub-data"
    except Exception as e:
        print("server: could not find the data store name:", e)
APP_PASSWORD = os.environ.get("APP_PASSWORD") or ""
SESSION_SECRET = (os.environ.get("SESSION_SECRET") or "").encode()
ON_PUBLIC_HOST = bool(os.environ.get("RENDER"))      # Render sets RENDER=true; its links are public
SESSION_DAYS = 30
MAX_FAILS_PER_IP, MAX_FAILS_TOTAL, FAIL_WINDOW = 5, 30, 15 * 60
LOCAL = os.environ.get("DATA_DIR", "data")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
HERE = os.path.dirname(os.path.abspath(__file__))
IST = timezone(timedelta(hours=5, minutes=30))
LOCK = threading.Lock()
_cache = {"at": 0, "data": None}

app = FastAPI(docs_url=None, redoc_url=None)
MAX_BODY = 64 * 1024           # no request needs more than this
MAX_TRACKED = 5000             # tracker items
FRESH_EVERY = 60               # a forced reload rebuilds the data at most once a minute


# ------------------------------------------------------------------ login (the app holds contacts + your tracker)
OPEN_PATHS = {"/login", "/healthz"}
_fails = []                     # (time, ip) of wrong passwords


def _auth_ready():
    return len(APP_PASSWORD) >= 10 and len(SESSION_SECRET) >= 16


def _sign(exp):
    return hmac.new(SESSION_SECRET, f"career-hub:{exp}".encode(), hashlib.sha256).hexdigest()


def _session_ok(cookie):
    try:
        exp, sig = str(cookie or "").split(".", 1)
        return int(exp) > time.time() and hmac.compare_digest(sig, _sign(int(exp)))
    except (ValueError, TypeError):
        return False


def _client_ip(request):
    return (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()


def login_required(request):
    """Return a response that blocks the request, or None to let it through."""
    if request.url.path in OPEN_PATHS:
        return None
    if not APP_PASSWORD and not ON_PUBLIC_HOST:
        return None             # local run / tests: no password set and not on a public host
    if not _auth_ready():       # fail closed: never serve the data on a public link without a strong password
        return JSONResponse({"detail": "Set APP_PASSWORD (10+ characters) and SESSION_SECRET in the host's settings"},
                            status_code=503)
    if _session_ok(request.cookies.get("ch_session")):
        return None
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "login required"}, status_code=401)
    return RedirectResponse("/login", status_code=303)


LOGIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Career Hub · sign in</title><style>
:root{--bg:#1e1e1e;--fg:#f3efe6;--dim:#a8a296;--line:#3a3833;--acc:#f6c89f;--bad:#f49f92}
@media (prefers-color-scheme: light){:root{--bg:#f6f3ec;--fg:#1e1e1e;--dim:#6b665c;--line:#d9d3c7;--acc:#b5651d;--bad:#b3261e}}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
form{width:min(340px,calc(100vw - 32px));border:1px solid var(--line);border-radius:18px;padding:28px}
h1{font-size:24px;margin:0 0 4px}p{color:var(--dim);margin:0 0 18px;font-size:14px}
input{width:100%;box-sizing:border-box;padding:12px 14px;border-radius:12px;border:1px solid var(--line);background:transparent;color:var(--fg);font-size:16px}
button{margin-top:14px;width:100%;padding:12px;border:0;border-radius:999px;background:var(--acc);color:#1e1e1e;font-weight:600;font-size:15px}
.err{color:var(--bad);font-size:14px;margin-top:10px}</style></head><body>
<form method="post" action="/login"><h1>Career Hub</h1><p>Private. Enter your password.</p>
<input type="password" name="password" autocomplete="current-password" autofocus required aria-label="Password">
<button type="submit">Open</button>{err}</form></body></html>"""


@app.get("/login")
def login_page():
    return HTMLResponse(LOGIN_PAGE.replace("{err}", ""), headers={"Cache-Control": "no-store"})


@app.post("/login")
async def login(request: Request):
    if not _auth_ready():
        return JSONResponse({"detail": "login is not set up"}, status_code=503)
    now, ip = time.time(), _client_ip(request)
    with LOCK:
        _fails[:] = [f for f in _fails if now - f[0] < FAIL_WINDOW]
        if len(_fails) >= MAX_FAILS_TOTAL or sum(1 for f in _fails if f[1] == ip) >= MAX_FAILS_PER_IP:
            return HTMLResponse(LOGIN_PAGE.replace("{err}", '<p class="err">Too many tries. Wait 15 minutes.</p>'),
                                status_code=429)
    from urllib.parse import parse_qs
    pw = (parse_qs((await request.body()).decode("utf-8", "replace")).get("password") or [""])[0]
    if not hmac.compare_digest(hashlib.sha256(pw.encode()).digest(), hashlib.sha256(APP_PASSWORD.encode()).digest()):
        with LOCK:
            _fails.append((now, ip))
        return HTMLResponse(LOGIN_PAGE.replace("{err}", '<p class="err">Wrong password.</p>'), status_code=401)
    exp = int(now + SESSION_DAYS * 86400)
    r = RedirectResponse("/", status_code=303)
    r.set_cookie("ch_session", f"{exp}.{_sign(exp)}", max_age=SESSION_DAYS * 86400, httponly=True,
                 secure=ON_PUBLIC_HOST, samesite="strict", path="/")
    return r


@app.get("/logout")
def logout():
    r = RedirectResponse("/login", status_code=303)
    r.delete_cookie("ch_session", path="/")
    return r


@app.middleware("http")
async def guard(request: Request, call_next):
    """Defence for every POST: (1) only JSON, (2) only from this app's own page (custom header + same origin),
    so another website open in the same browser can't send requests with Daksh's login; (3) size limit."""
    blocked = login_required(request)
    if blocked is not None:
        return blocked
    if request.method == "POST" and request.url.path == "/login":
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host", ""):
            return JSONResponse({"detail": "cross-site request"}, status_code=403)
        try:
            if int(request.headers.get("content-length") or 0) > 4096:
                return JSONResponse({"detail": "request too large"}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "bad length"}, status_code=400)
    elif request.method == "POST":
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            return JSONResponse({"detail": "JSON only"}, status_code=415)
        if request.headers.get("x-career-hub") != "1":
            return JSONResponse({"detail": "missing app header"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host", ""):
            return JSONResponse({"detail": "cross-site request"}, status_code=403)
        try:
            if int(request.headers.get("content-length") or 0) > MAX_BODY:
                return JSONResponse({"detail": "request too large"}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "bad length"}, status_code=400)
        body = b""
        async for chunk in request.stream():
            body += chunk
            if len(body) > MAX_BODY:
                return JSONResponse({"detail": "request too large"}, status_code=413)
        request._body = body
    return await call_next(request)


# ------------------------------------------------------------------ storage
def read_bytes(path):
    if HF_TOKEN and DATA_REPO:
        from huggingface_hub import hf_hub_download
        try:
            p = hf_hub_download(DATA_REPO, path, repo_type="dataset", token=HF_TOKEN)
        except Exception:
            return None
        with open(p, "rb") as f:
            return f.read()
    p = os.path.join(LOCAL, path)
    if os.path.exists(p):
        with open(p, "rb") as f:
            return f.read()
    return None


def write_bytes(path, data, msg):
    if HF_TOKEN and DATA_REPO:
        from huggingface_hub import HfApi
        HfApi(token=HF_TOKEN).upload_file(path_or_fileobj=data, path_in_repo=path, repo_id=DATA_REPO,
                                          repo_type="dataset", commit_message=msg)
    else:
        full = os.path.join(LOCAL, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)


READ_ERRORS = {}


def jread(path, default):
    b = read_bytes(path)
    try:
        v = json.loads(b) if b else default
        READ_ERRORS.pop(path, None)
        return v
    except Exception as e:      # a broken file must not take the app down — but it must be visible
        READ_ERRORS[path] = f"unreadable: {type(e).__name__}"
        return default


def cread(path):
    b = read_bytes(path)
    if not b:
        return []
    try:
        return list(csv.DictReader(io.StringIO(b.decode("utf-8"))))
    except Exception:
        return []


# ------------------------------------------------------------------ payload
GIG_FIELDS = ["id", "source", "title", "url", "company", "posted", "first_seen", "pay_type", "pay_inr", "currency",
              "budget_min", "budget_max", "bids", "work_type", "category", "eligibility", "score", "why", "ai", "trust",
              "level", "project_match", "intl", "pay_text", "pays_foreign"]


def build():
    s = SETTINGS.load_from(jread("settings/settings.json", None))
    gigs_all = jread("gigs/gigs.json", {}).get("gigs", [])
    gigs = [{k: g.get(k) for k in GIG_FIELDS} | {"desc": (g.get("desc") or "")[:400]} for g in gigs_all if g.get("visible")]
    gig_blocked = [{"title": g["title"], "url": g["url"], "platform": g["source"], "why": g.get("scam")}
                   for g in gigs_all if g.get("scam")][:40]
    roles_doc = jread("roles/roles.json", {})
    ranked = {r.get("_key") or r.get("company"): r for r in cread("jobs/ranked.csv")}
    contacts = cread("jobs/contacts.csv")
    by_co = {}
    for c in contacts:
        if str(c.get("key_contact")) == "True":
            by_co.setdefault(c["company"], []).append(
                {k: c.get(k) for k in ("name", "role", "category", "email", "email_grade", "email_source",
                                       "verification", "linkedin", "person_confidence")})
    companies = []
    for p in cread("jobs/outreach_plan.csv"):
        key = p.get("_key") or p.get("company")
        rk = ranked.get(key, {})
        companies.append({
            "key": key, "rank": p.get("rank"), "tier": p.get("tier"), "company": p.get("company"),
            "fields": p.get("fields"), "fit": p.get("fit_score"), "channel": p.get("channel"),
            "city": rk.get("city"), "founded": (rk.get("founded") or "").replace(".0", ""), "stage": rk.get("stage"),
            "what": rk.get("what_they_do") or rk.get("one_liner"), "products": rk.get("products"),
            "research": rk.get("research_and_discoveries"), "funding": rk.get("total_funding"),
            "last_round": rk.get("last_round"), "last_round_date": rk.get("last_round_date"),
            "investors": rk.get("investors"), "website": rk.get("website"), "why": rk.get("why_it_fits"),
            "careers_email": p.get("careers_email"), "general_email": p.get("general_email"), "phone": p.get("phone"),
            "talking_point": p.get("talking_point"), "linkedin_note": p.get("linkedin_note"),
            "email_subject": p.get("email_subject"), "email_draft": p.get("email_draft"),
            "contacts": by_co.get(key, [])[:8],
        })
    links = [{"role": r, "location": loc, "links": AP.search_links(C.ROLE_QUERY[r], loc)}
             for r in s["roles"] for loc in s["locations"]]
    pb = [{"platform": k, "apply": v["apply"], "alerts": v["alerts"]} for k, v in AP.PLAYBOOK.items()]
    return {
        "now": time.time(),
        "profile": {"first_name": C.PROFILE["first_name"], "name": C.PROFILE["name"], "headline": C.PROFILE["headline"],
                    "intro": C.PROFILE["intro"], "skills": C.PROFILE["skills"],
                    "projects": [{"name": p["name"], "short": p["short"]} for p in C.PROFILE["projects"]]},
        "settings": s,
        "catalog": {"sectors": list(C.SECTOR_CATALOG), "cities": C.CITY_OPTIONS, "remote": C.REMOTE_OPTIONS,
                    "roles": list(C.ROLE_CATALOG), "gig_types": {k: v["label"] for k, v in C.GIG_CATEGORIES.items()},
                    "experience": C.EXPERIENCE},
        "goal": list(C.MONTHLY_GOAL_INR), "hours": C.HOURS_PER_WEEK,
        "gigs": gigs, "gigs_updated": jread("gigs/gigs.json", {}).get("updated"),
        "roles": roles_doc.get("roles", []), "roles_updated": roles_doc.get("updated"),
        "senior_hidden": roles_doc.get("senior_hidden", 0),
        "blocked": (roles_doc.get("blocked") or [])[:60] + gig_blocked,
        "companies": companies, "platforms": C.AI_PLATFORMS, "playbook": pb, "links": links,
        "safety": [{"title": t, "text": x} for t, x in trust.SAFETY_RULES],
        "health": {"gigs": jread("gigs/health.json", {}), "roles": jread("roles/health.json", {}),
                   "runs": jread("gigs/state.json", {}).get("runs", [])[-12:], "jobs": jread("jobs/run_status.json", {}),
                   "files": dict(READ_ERRORS)},
        "tracker": jread("tracker/tracker.json", {"items": {}, "earnings": []}),
        "lessons": lessons_view(),
        "github": GITHUB_REPO,
    }


def lessons_view():
    L = jread(FB.LESSONS_PATH, None) or FB.empty()
    reps = jread(FB.REPORTS_PATH, {"reports": []}).get("reports", [])
    return {"version": L.get("version", 0), "updated": L.get("updated"), "block_domains": L.get("block_domains", {}),
            "pending": L.get("pending", []), "rule_feedback": L.get("rule_feedback", {}),
            "allowed": len(L.get("allow_urls", [])), "hidden": len(L.get("hide_urls", [])),
            "level_cases": len(L.get("level_cases", [])), "reports": len(reps),
            "history": [{"version": h["version"], "at": h["at"], "changes": h["changes"][:6]} for h in L.get("history", [])][-8:]}


def payload(fresh=False, force=False):
    with LOCK:
        age = time.time() - _cache["at"]
        if force or not _cache["data"] or age > 300 or (fresh and age > FRESH_EVERY):
            _cache["data"], _cache["at"] = build(), time.time()
        return _cache["data"]


# ------------------------------------------------------------------ routes
@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"), headers={"Cache-Control": "no-cache"})


@app.get("/api/data")
def data(fresh: int = 0):
    return JSONResponse(payload(bool(fresh)))


ALLOWED = {"role": {"saved", "applied", "interview", "offer", "rejected", "hidden", ""},
           "gig": {"saved", "bid", "won", "done", "paid", "lost", "hidden", ""},
           "company": {"to contact", "contacted", "replied", "interview", "no reply", ""},
           "platform": {"not applied", "applied", "onboarding", "active", "rejected", ""}}


def save_tracker(t, msg):
    write_bytes("tracker/tracker.json", json.dumps(t, ensure_ascii=False, indent=1).encode(), msg)
    with LOCK:
        if _cache["data"]:
            _cache["data"]["tracker"] = t


@app.post("/api/track")
async def track(req: Request):
    b = await req.json()
    key, status = str(b.get("key", "")), str(b.get("status", ""))
    kind = key.split(":", 1)[0]
    if kind not in ALLOWED or status not in ALLOWED[kind] or len(key) > 300:
        raise HTTPException(400, "bad status")
    t = jread("tracker/tracker.json", {"items": {}, "earnings": []})
    if not status and key in t["items"] and not t["items"][key].get("note"):
        del t["items"][key]                       # clearing a status frees its slot
        save_tracker(t, f"track {kind}")
        return {"ok": True, "item": {}}
    if key not in t["items"] and len(t["items"]) >= MAX_TRACKED:
        raise HTTPException(400, "tracker full")
    item = t["items"].get(key, {})
    item.update({"status": status, "updated": datetime.now(IST).isoformat(timespec="minutes")})
    if isinstance(b.get("meta"), dict):
        item["meta"] = {k: str(v)[:300] for k, v in b["meta"].items() if k in ("title", "company", "url", "platform", "location")}
    if "note" in b:
        item["note"] = str(b["note"])[:1000]
    t["items"][key] = item
    save_tracker(t, f"track {kind}")
    return {"ok": True, "item": item}


@app.post("/api/earning")
async def earning(req: Request):
    b = await req.json()
    try:
        amt = float(b.get("amount_inr"))
        if not math.isfinite(amt):
            raise ValueError
        datetime.strptime(str(b.get("date")), "%Y-%m-%d")
    except Exception:
        raise HTTPException(400, "bad earning")
    if not 0 < amt < 10_000_000:
        raise HTTPException(400, "bad amount")
    t = jread("tracker/tracker.json", {"items": {}, "earnings": []})
    t.setdefault("earnings", []).append({"date": b["date"], "amount_inr": amt,
                                         "source": str(b.get("source", ""))[:120], "note": str(b.get("note", ""))[:300]})
    save_tracker(t, "earning")
    return {"ok": True, "earnings": t["earnings"]}


@app.post("/api/settings")
async def save_settings(req: Request):
    s = SETTINGS.clean(await req.json())
    write_bytes(SETTINGS.SETTINGS_PATH, json.dumps(s, indent=1).encode(), "settings")
    payload(force=True)
    return {"ok": True, "settings": s}


FEEDBACK_OK = {"gig": {"scam"}, "role": {"scam", "senior", "entry"}, "blocked": {"not_scam"}}


@app.post("/api/feedback")
async def feedback(req: Request):
    """Report scam / not a scam / wrong level. The post is looked up in the server's own data, so a report can
    only be about something the radars really found (a forged URL or domain is refused)."""
    b = await req.json()
    kind, verdict = str(b.get("kind", "")), str(b.get("verdict", ""))
    if verdict not in FEEDBACK_OK.get(kind, set()):
        raise HTTPException(400, "bad feedback")
    item = None
    if kind == "gig":
        item = next((g for g in jread("gigs/gigs.json", {}).get("gigs", []) if g.get("id") == b.get("id")), None)
    elif kind == "role":
        item = next((r for r in jread("roles/roles.json", {}).get("roles", []) if r.get("id") == b.get("id")), None)
    else:
        item = next((x for x in payload()["blocked"] if x.get("url") == b.get("url")), None)
    if not item:
        raise HTTPException(404, "post not found")
    try:
        rep = FB.make_report(verdict, item if kind == "blocked" else {**item, "why": []}, kind)
    except ValueError as e:
        raise HTTPException(400, str(e))
    with LOCK:
        doc = jread(FB.REPORTS_PATH, {"reports": []})
        doc["reports"] = FB.add_report(doc.get("reports", []), rep)
        write_bytes(FB.REPORTS_PATH, json.dumps(doc, ensure_ascii=False, indent=1).encode(), f"feedback {verdict}")
    if verdict == "scam":   # hide it right away; the learner makes it permanent on the next run
        t = jread("tracker/tracker.json", {"items": {}, "earnings": []})
        key = f"{kind}:{item['id']}"
        t["items"][key] = {**t["items"].get(key, {}), "status": "hidden",
                           "updated": datetime.now(IST).isoformat(timespec="minutes"), "note": "reported as scam"}
        save_tracker(t, "hide reported scam")
    with LOCK:
        if _cache["data"]:
            _cache["data"]["lessons"]["reports"] += 1
    return {"ok": True, "message": {"scam": "Reported — hidden now. The shield learns from it on the next run.",
                                    "not_scam": "Thanks — it will show again on the next run, with a warning tag.",
                                    "senior": "Noted — added to your level test set.",
                                    "entry": "Noted — added to your level test set."}[verdict]}


@app.get("/api/export.xlsx")
def export():
    b = read_bytes("jobs/job_finder_results.xlsx")
    if not b:
        raise HTTPException(404, "not ready yet")
    return Response(b, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=career_hub_companies.xlsx"})


@app.get("/healthz")
def healthz():
    return {"ok": True}
