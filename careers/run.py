"""Collect vacancies from big companies' OWN careers sites, classify them, score how sure we are they're real,
and save data/careers/official.json for the app.   python -m careers.run

Each run has a time budget (CAREERS_BUDGET_SECONDS, default 540). Companies refreshed longest ago go first, so
over a day every company gets refreshed even though one run can't do them all.
A job stays while it keeps being seen. Not seen for legit.CLOSED_AFTER_D days:
  • company re-read OK since, whole board read (Greenhouse/Lever/Ashby) → closed, dropped
  • company re-read OK since, search-based site (Workday, Amazon, Google, Apple, Oracle) → kept up to 7 days (it may
    just not match this run's search words)
  • company NOT re-read since (blocked / resting / over budget) → kept up to 14 days, marked "not re-checked"
A company that becomes link-only (e.g. its robots.txt changes) has its jobs removed at once.
Gates (common/gates.py, kind "careers") run before saving; if they fail the last good file is kept.
"""
import json
import os
import time

import config as CFG
from careers import classify as K, custom as CU, eligible as EL, legit, match as M, registry, sources as S
from common import gates

DATA_DIR = os.environ.get("DATA_DIR", "data")
DIR = os.path.join(DATA_DIR, "careers")
BUDGET = float(os.environ.get("CAREERS_BUDGET_SECONDS", "840"))   # 14 min: requests are now paced (see sources.PACE)
DESC_KEEP = 6000
DESC_KEEP_NONTECH = 300


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


WORKDAY_PER_RUN = int(os.environ.get("CAREERS_WORKDAY_PER_RUN", "6"))   # 4 runs/day x 6 = every Workday site ~daily


def order(companies, health):
    """Automatic companies, longest-since-refresh first (never refreshed = first), then by tier. At most
    WORKDAY_PER_RUN Workday sites per run (Workday blocks bursts of requests)."""
    auto = [c for c in companies if c.get("ats") in S.CONNECTORS]
    auto.sort(key=lambda c: ((health.get(c["name"]) or {}).get("ok_at", 0), registry.TIER_RANK.get(c["tier"], 9)))
    out, wd = [], 0
    for c in auto:
        if c["ats"] == "workday":
            if (health.get(c["name"]) or {}).get("backoff_until", 0) > time.time():
                continue
            wd += 1
            if wd > WORKDAY_PER_RUN:
                continue
        out.append(c)
    return out


def enrich(j, company, now):
    c = K.classify(j)
    j.update(c)
    j["skills"] = M.job_skills(j)            # what the job asks for (server compares it with your resumes)
    j["hard"] = M.hard_requirements(j)
    j["eligible"] = EL.check(j, CFG.PROFILE.get("degree", "bachelor"), CFG.PROFILE.get("grad_year"))
    j["legit"] = legit.official(j, company, j.get("last_seen"), now)
    j["visible"] = j["legit"]["pct"] >= 55
    if c["family"] == "Non-technical":
        j["desc"] = (j.get("desc") or "")[:DESC_KEEP_NONTECH]
    else:
        j["desc"] = (j.get("desc") or "")[:DESC_KEEP]
    return j


FULL_BOARD = {"greenhouse", "lever", "ashby", "smartrecruiters"}   # we read the whole board, not search results
KEEP_UNCHECKED_D = 14       # company couldn't be re-checked (blocked / resting): keep its jobs this long
DISCOVER_PER_RUN = 5


def _board_size(ats, slug):
    """How many jobs a Greenhouse / Lever / Ashby board has (used to find a company's board from its name)."""
    url = S.api_url({"ats": ats, "slug": slug})
    if not S.robots_allowed(url)[0]:
        raise RuntimeError("robots.txt disallows")
    d = S.cget(url)
    return len(d.get("jobs") or []) if isinstance(d, dict) else len(d or [])


PROFILES = ["daksh", "aruja", "lubhana"]       # same ids as app/server.py USERS


def profile_entries():
    """Every profile's own added companies, tagged with who added them (Daksh's file stays where it always was)."""
    out = []
    for u in PROFILES:
        rel = os.path.join("careerprefs", "companies.json") if u == "daksh" else os.path.join("users", u, "careerprefs", "companies.json")
        for e in load(os.path.join(DATA_DIR, rel), {}).get("companies", [])[:CU.MAX_COMPANIES]:
            out.append({**e, "owner": u})
    return out


def custom_companies(old, now, board_size=_board_size):
    """Companies people added in the app, each resolved to a connector once and cached in official.json.
    The same company added by two people is collected once; its jobs are shown only to the people who added it."""
    merged = {}
    for e in profile_entries():
        key = f"{e.get('name')}|{e.get('url', '')}"
        m = merged.setdefault(key, {**e, "owners": []})
        m["owners"].append(e["owner"])
    cache, out, tried = dict(old.get("custom") or {}), [], 0
    for i, (key, e) in enumerate(merged.items()):
        if key not in cache and tried < DISCOVER_PER_RUN:
            tried += 1
            cache[key] = {**CU.discover(e, board_size), "at": now}
        cfg = cache.get(key)
        if not cfg:
            continue
        c = {k: v for k, v in cfg.items() if k not in ("found", "at")}
        out.append({**c, "name": e["name"], "tier": e.get("tier", "Big tech"), "custom": True, "rank": 500 + i,
                    "found": cfg.get("found", ""), "owners": sorted(set(e["owners"]))})
    return out, {k: v for k, v in cache.items() if k in merged}


def keep(j, company, health, now):
    """Is this job still worth showing? (see the rules in the module docstring)"""
    age = now - j.get("last_seen", 0)
    if age <= legit.CLOSED_AFTER_D * 86400:
        return True
    ok_at = (health.get(j["company"]) or {}).get("ok_at", 0)
    if ok_at <= j.get("last_seen", 0):                 # not re-checked since → can't tell it closed
        return age <= KEEP_UNCHECKED_D * 86400
    if company.get("ats") in FULL_BOARD:               # re-read the whole board and it wasn't there → closed
        return False
    return age <= 7 * 86400                            # search-based sites: it may just not match this run's words


def run(now=None, budget=BUDGET, collect=S.collect):
    now = now or time.time()
    path = os.path.join(DIR, "official.json")
    old = load(path, {})
    jobs = {j["id"]: j for j in old.get("jobs", [])}
    health = old.get("health", {})
    mine, custom_cache = custom_companies(old, now)
    reg_names = {c["name"].lower() for c in registry.CANDIDATES}
    mine = [c for c in mine if c["name"].lower() not in reg_names]      # already built in
    companies_all = registry.CANDIDATES + mine
    companies = {c["name"]: c for c in companies_all}
    known = {}
    for j in jobs.values():
        if len(j.get("desc") or "") > 200:
            known.setdefault(j["company"], set()).update({j["id"], j.get("src_key") or j["id"]})
    work = {n: dict(h) for n, h in health.items()}          # collect() reads rest periods / strikes from here
    got = collect(order(companies_all, health), work, now, budget, known)
    run_health = {n: h for n, h in work.items() if h.get("at") == now}      # companies visited this run
    for name, h in run_health.items():
        prev = health.get(name, {})
        health[name] = {**h, "ok_at": now if h.get("ok") else prev.get("ok_at", 0),
                        "last_count": h["count"] if h.get("ok") else prev.get("last_count", 0)}
    new, dropped = 0, 0
    for j in got:
        if not str(j.get("url") or "").startswith("https://") or not legit.host(j.get("url")):
            dropped += 1          # a job whose link isn't a normal https address is never stored or shown
            continue
        o = jobs.get(j["id"])
        if o:
            if len(j.get("desc") or "") < len(o.get("desc") or ""):
                j["desc"] = o["desc"]
            j["posted"] = j.get("posted") or o.get("posted")
            j["first_seen"] = o.get("first_seen") or now
        else:
            j["first_seen"] = now
            new += 1
        j["last_seen"] = now
        jobs[j["id"]] = j
    kept = []
    for j in jobs.values():
        co = companies.get(j["company"])
        if not co or co.get("ats") == "link" or not keep(j, co, health, now):
            continue                       # company removed / now link-only (e.g. robots.txt changed) / closed
        j = enrich(j, co, now)
        if co.get("owners"):
            j["owners"] = co["owners"]          # added by someone in the app → shown only to them
        else:
            j.pop("owners", None)
        kept.append(j)
    kept.sort(key=lambda j: (registry.TIER_RANK.get(j["company_tier"], 9), j.get("company_rank", 99), -(j.get("posted") or 0)))
    prev_visible = sum(1 for j in old.get("jobs", []) if j.get("visible"))
    ok = gates.guard("careers", kept, prev_visible, health, now)
    links = [{"name": c["name"], "tier": c["tier"], "url": c["search_url"], "why": c.get("why", ""), "custom": c.get("custom", False),
              **({"owners": c["owners"]} if c.get("owners") else {})}
             for c in companies_all if c.get("ats") == "link" and c.get("search_url")]
    roster = [{"name": c["name"], "tier": c["tier"], "auto": c.get("ats") != "link", "custom": c.get("custom", False),
               "why": c.get("why") or c.get("found", ""), "ats": c.get("ats"), **({"owners": c["owners"]} if c.get("owners") else {})}
              for c in companies_all]
    if ok:
        save(path, {"updated": now, "jobs": kept, "health": health, "links": links, "custom": custom_cache, "companies": roster})
    else:
        save(path, {**old, "health": health, "custom": custom_cache, "companies": roster})
    vis = sum(1 for j in kept if j["visible"])
    ml = sum(1 for j in kept if j["visible"] and j.get("is_ml"))
    fresh = sum(1 for j in kept if j["visible"] and j.get("fresher_fit") in ("fits", "stretch"))
    print(f"careers: {len(got)} fetched this run ({new} new) from {sum(1 for h in run_health.values() if h.get('ok'))} "
          f"companies · {len(kept)} stored · {vis} shown · {ml} ML/AI · {fresh} fresher-fit"
          + (f" · {dropped} dropped (unsafe link)" if dropped else "")
          + ("" if ok else " · NOT SAVED (output check failed, last good list kept)"))
    if os.environ.get("GITHUB_ACTIONS"):      # one-line summary readable through GitHub's API (logs aren't)
        bad = [f"{n}: {h.get('error', '')[:60]}" for n, h in sorted(run_health.items()) if not h.get("ok")]
        print(f"::notice title=Big companies::{len(got)} fetched ({new} new) · {len(kept)} stored · {vis} shown · "
              f"{ml} ML/AI · {fresh} fresher-fit · {sum(1 for h in run_health.values() if h.get('ok'))}/{len(run_health)} "
              f"companies ok" + (" · saved" if ok else " · NOT SAVED (gate)"))
        if bad:
            print("::warning title=Big companies down::" + " | ".join(bad)[:900])
    for n, h in sorted(run_health.items()):
        print(f"  {n}: {'ok ' + str(h['count']) if h.get('ok') else 'FAILED ' + h.get('error', '')} {h.get('secs', '')}s")
    return kept


if __name__ == "__main__":
    run()
