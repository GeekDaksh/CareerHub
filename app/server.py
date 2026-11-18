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
import refresher
from common import apply as AP
from common import feedback as FB
from common import settings as SETTINGS
from common import trust
from careers import match as MATCH
from careers import learn as LEARN
from careers import custom as CUSTOM
from careers import resumes as RES

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
from starlette.middleware.gzip import GZipMiddleware   # noqa: E402
app.add_middleware(GZipMiddleware, minimum_size=2048)
MAX_BODY = 64 * 1024           # no request needs more than this …
BODY_LIMITS = {"/api/resume": 4_500_000}   # … except a resume upload (3 MB file, base64-encoded)
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
        limit = BODY_LIMITS.get(request.url.path, MAX_BODY)
        try:
            if int(request.headers.get("content-length") or 0) > limit:
                return JSONResponse({"detail": "request too large"}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "bad length"}, status_code=400)
        body = b""
        async for chunk in request.stream():
            body += chunk
            if len(body) > limit:
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


CAREERS = {"jobs": {}, "doc": {}}          # full official jobs (with descriptions) for the Details view
ROW_FIELDS = ["id", "company", "company_tier", "company_rank", "title", "location", "posted", "first_seen", "last_seen",
              "url", "family", "family_conf", "specialties", "is_ml", "level", "level_conf", "fresher_fit", "employment",
              "work_mode", "hard"]


def resumes_doc():
    return jread("resumes/resumes.json", {"resumes": []})


# ---------------------------------------------------------------- reactions (like / dislike / save / apply / hide)
REACT = {"loaded": False, "data": {}, "timer": None}
REACT_LOCK = threading.Lock()
FLUSH_AFTER = 15            # seconds: many clicks → one write to the data store (HF limits commits per hour)


def reactions():
    with REACT_LOCK:
        if not REACT["loaded"]:
            REACT["data"] = jread("careerprefs/reactions.json", {}).get("reactions", {})
            REACT["loaded"] = True
        return REACT["data"]


def _flush():
    with REACT_LOCK:
        data, REACT["timer"] = dict(REACT["data"]), None
    write_bytes("careerprefs/reactions.json", json.dumps({"reactions": data}, ensure_ascii=False).encode(), "reactions")


def _schedule_flush():
    with REACT_LOCK:
        if REACT["timer"] is None:
            REACT["timer"] = threading.Timer(FLUSH_AFTER, _flush)
            REACT["timer"].daemon = True
            REACT["timer"].start()


def model_for(jobs):
    rs = list(reactions().values())
    return LEARN.Model(rs, [LEARN.features(j) for j in jobs])


def careers_view(resumes):
    doc = jread("careers/official.json", {})
    jobs = [j for j in doc.get("jobs", []) if j.get("visible") and j.get("family") != "Non-technical"]
    CAREERS["jobs"] = {j["id"]: j for j in jobs}
    CAREERS["doc"] = doc
    have = [(r["name"], MATCH.skills_in(r.get("text", ""), implied=True)) for r in resumes]
    m = model_for(jobs)
    CAREERS["model"] = m
    react = reactions()
    rs = [v for v in react.values() if v.get("r") in LEARN.SIGNAL]
    key = (len(rs), max((v["at"] for v in rs), default=0), len(jobs))
    if CAREERS.get("check_key") != key:          # honest self-check, only recomputed when something changed
        CAREERS["check"] = LEARN.holdout_check(rs[-60:], [{"f": LEARN.features(x)} for x in jobs[:400]])
        CAREERS["check_key"] = key
    rows = []
    for j in jobs:
        row = {k: j.get(k) for k in ROW_FIELDS}
        row["legit"] = {"pct": j["legit"]["pct"], "band": j["legit"]["band"], "open": j["legit"].get("still_open")}
        row["match"], row["best"] = MATCH.best_for(j.get("skills") or [], have) if have else (None, None)
        row["n_skills"] = len(j.get("skills") or [])
        el = j.get("eligible") or {"ok": True}
        row["elig"] = {"ok": el.get("ok", True), "why": el.get("why", "")}
        row["fy"], why = m.score(LEARN.features(j))
        row["fy_why"] = [f"{x['sign']} {x['text']}" for x in why]
        row["r"] = (react.get(j["id"]) or {}).get("r")
        rows.append(row)
    hidden_nt = sum(1 for j in doc.get("jobs", []) if j.get("family") == "Non-technical")
    mine = jread("careerprefs/companies.json", {}).get("companies", [])
    roster = {c["name"]: c for c in doc.get("companies", [])}
    health = doc.get("health", {})
    companies = []
    for name, c in roster.items():
        h = health.get(name) or {}
        companies.append({**c, "count": sum(1 for j in jobs if j["company"] == name), "ok": h.get("ok"), "error": h.get("error", "")})
    for e in mine:                                   # added in the app, not collected yet
        if e["name"] not in roster:
            companies.append({"name": e["name"], "tier": e.get("tier"), "custom": True, "auto": None, "count": 0,
                              "why": "waiting for the next update (it looks for this company's job list then)"})
    learn = m.summary()
    learn["check"] = CAREERS.get("check")
    return {"rows": rows, "updated": doc.get("updated"), "links": doc.get("links", []), "health": health,
            "nontech_hidden": hidden_nt, "companies": companies, "mine": mine, "learn": learn}


def build():
    s = SETTINGS.load_from(jread("settings/settings.json", None))
    rdoc = resumes_doc()
    resumes = rdoc.get("resumes", [])
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
        "careers": careers_view(resumes),
        "resumes": [{"name": r["name"], "filename": r.get("filename"), "uploaded": r.get("uploaded"),
                     "chars": len(r.get("text", "")), "skills": sorted(MATCH.skills_in(r.get("text", ""), implied=True))}
                    for r in resumes],
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
    rebuilt = False
    with LOCK:
        age = time.time() - _cache["at"]
        if force or not _cache["data"] or age > 300 or (fresh and age > FRESH_EVERY):
            _cache["data"], _cache["at"] = build(), time.time()
            rebuilt = True
        d = _cache["data"]
    if rebuilt:   # backup timer: if GitHub's schedule skipped runs, start the overdue update now
        started = refresher.check_stale(d.get("gigs_updated"), d.get("roles_updated"),
                                        (d["health"].get("jobs") or {}).get("finished_at"))
        d["refresh"] = {**refresher.state(), "started": started}
    return d


@app.post("/api/refresh")
async def refresh(req: Request):
    b = await req.json()
    what = str(b.get("what", ""))
    if what not in refresher.WORKFLOWS:
        raise HTTPException(400, "unknown update")
    res = refresher.dispatch(what, "you pressed Update now")
    return {"ok": res["ok"], "message": "Started — new results in about 10 minutes (companies: up to 2 hours)."
            if res["ok"] else f"Not started: {res['why']}"}


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


@app.get("/api/job")
def job_detail(id: str):
    payload()
    j = CAREERS["jobs"].get(str(id)[:200])
    if not j:
        raise HTTPException(404, "job not found (it may have closed)")
    resumes = resumes_doc().get("resumes", [])
    adv = MATCH.advise(j, resumes)
    out = {k: j.get(k) for k in ROW_FIELDS + ["family_evidence", "level_evidence", "desc", "ats"]}
    m = CAREERS.get("model") or model_for(list(CAREERS["jobs"].values()))
    fy, why = m.score(LEARN.features(j))
    disliked = {k for k, v in reactions().items() if v.get("r") in ("dislike", "hidden")}
    senior_ok = j.get("fresher_fit") == "too senior"
    seen, cands = {(j["company"], j["title"].lower())}, []
    for x in CAREERS["jobs"].values():      # same rules as the list: eligible, your level, not disliked, no repeats
        k = (x["company"], x["title"].lower())
        if k in seen or x["id"] in disliked or not (x.get("eligible") or {}).get("ok", True) \
                or (x.get("fresher_fit") == "too senior" and not senior_ok):
            continue
        seen.add(k)
        cands.append((x["id"], LEARN.features(x)))
    sim = [CAREERS["jobs"][i] for i in m.similar(LEARN.features(j), cands)]
    return {**out, "legit": j["legit"], "advice": adv, "eligible": j.get("eligible") or {"ok": True},
            "fy": fy, "fy_why": why, "r": (reactions().get(j["id"]) or {}).get("r"),
            "similar": [{k: x.get(k) for k in ("id", "company", "title", "family", "fresher_fit", "location")} for x in sim]}


@app.post("/api/react")
async def react(req: Request):
    b = await req.json()
    jid, r, reason = str(b.get("id") or "")[:200], b.get("r"), b.get("reason")
    if r not in list(LEARN.SIGNAL) + ["none"] or (reason is not None and reason not in LEARN.REASONS):
        raise HTTPException(400, "unknown reaction")
    payload()
    j = CAREERS["jobs"].get(jid)
    data = reactions()
    with REACT_LOCK:
        if r == "none":
            data.pop(jid, None)
        else:
            if not j and jid not in data:
                raise HTTPException(404, "job not found")
            prev = data.get(jid) or {}
            data[jid] = {"r": r, "reason": reason, "at": time.time(),
                         "f": LEARN.features(j) if j else prev.get("f", []),
                         "title": (j or prev).get("title", "")[:120], "company": (j or prev).get("company", "")[:60]}
            if len(data) > LEARN.MAX_REACTIONS:              # keep the newest
                for k in sorted(data, key=lambda k: data[k]["at"])[:len(data) - LEARN.MAX_REACTIONS]:
                    data.pop(k)
    _schedule_flush()
    with LOCK:
        _cache["at"] = 0
    return {"ok": True}


@app.post("/api/learn/reset")
async def learn_reset(req: Request):
    b = await req.json()
    if b.get("confirm") != "reset":
        raise HTTPException(400, "send confirm=reset")
    with REACT_LOCK:
        REACT["data"] = {}
    _flush()
    with LOCK:
        _cache["at"] = 0
    return {"ok": True}


def _save_companies(lst):
    write_bytes("careerprefs/companies.json", json.dumps({"companies": lst}, ensure_ascii=False).encode(), "companies")
    with LOCK:
        _cache["at"] = 0


@app.post("/api/company")
async def company_add(req: Request):
    b = await req.json()
    try:
        e = CUSTOM.clean(b.get("name"), b.get("url"), b.get("tier") or "Big tech")
    except CUSTOM.Bad as ex:
        raise HTTPException(400, str(ex))
    from careers import registry as REG
    if any(c["name"].lower() == e["name"].lower() for c in REG.CANDIDATES):
        raise HTTPException(400, f"{e['name']} is already in the list — search for it under Companies")
    lst = [c for c in jread("careerprefs/companies.json", {}).get("companies", []) if c["name"].lower() != e["name"].lower()]
    if len(lst) >= CUSTOM.MAX_COMPANIES:
        raise HTTPException(400, f"up to {CUSTOM.MAX_COMPANIES} companies — remove one first")
    lst.append({**e, "added": time.time()})
    _save_companies(lst)
    return {"ok": True, "name": e["name"]}


@app.post("/api/company/delete")
async def company_delete(req: Request):
    b = await req.json()
    lst = jread("careerprefs/companies.json", {}).get("companies", [])
    keep = [c for c in lst if c["name"] != str(b.get("name") or "")]
    if len(keep) == len(lst):
        raise HTTPException(404, "not one of your companies")
    _save_companies(keep)
    return {"ok": True}


def _save_resumes(lst, msg):
    write_bytes("resumes/resumes.json", json.dumps({"resumes": lst}, ensure_ascii=False).encode(), msg)
    with LOCK:
        _cache["at"] = 0          # rebuild on next load


@app.post("/api/resume")
async def resume_upload(req: Request):
    b = await req.json()
    try:
        name = RES.clean_name(b.get("name"))
        text = RES.read(b.get("filename"), b.get("data"))
    except RES.Bad as e:
        raise HTTPException(400, str(e))
    lst = [r for r in resumes_doc().get("resumes", []) if r["name"] != name]
    if len(lst) >= RES.MAX_RESUMES:
        raise HTTPException(400, f"up to {RES.MAX_RESUMES} resumes — delete one first")
    lst.append({"name": name, "filename": str(b.get("filename") or "")[:80], "uploaded": time.time(), "text": text})
    _save_resumes(lst, "resume uploaded")
    return {"ok": True, "name": name, "chars": len(text), "skills": sorted(MATCH.skills_in(text, implied=True))}


@app.post("/api/resume/delete")
async def resume_delete(req: Request):
    b = await req.json()
    name = str(b.get("name") or "")
    lst = resumes_doc().get("resumes", [])
    if not any(r["name"] == name for r in lst):
        raise HTTPException(404, "no resume with that name")
    _save_resumes([r for r in lst if r["name"] != name], "resume deleted")
    return {"ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True}
