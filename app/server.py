"""Career Hub web server (runs in the private Hugging Face Space).
Serves the single-page app and a small JSON API over the private dataset."""
import csv
import io
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

import config as C
from common import apply as AP
from common import settings as SETTINGS
from common import trust

HF_TOKEN = os.environ.get("HF_TOKEN")
DATA_REPO = os.environ.get("DATA_REPO")
LOCAL = os.environ.get("DATA_DIR", "data")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
HERE = os.path.dirname(os.path.abspath(__file__))
IST = timezone(timedelta(hours=5, minutes=30))
LOCK = threading.Lock()
_cache = {"at": 0, "data": None}

app = FastAPI(docs_url=None, redoc_url=None)


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


def jread(path, default):
    b = read_bytes(path)
    try:
        return json.loads(b) if b else default
    except Exception:
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
              "level", "project_match"]


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
                   "runs": jread("gigs/state.json", {}).get("runs", [])[-12:], "jobs": jread("jobs/run_status.json", {})},
        "tracker": jread("tracker/tracker.json", {"items": {}, "earnings": []}),
        "github": GITHUB_REPO,
    }


def payload(fresh=False):
    with LOCK:
        if fresh or not _cache["data"] or time.time() - _cache["at"] > 300:
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
    payload(fresh=True)
    return {"ok": True, "settings": s}


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
