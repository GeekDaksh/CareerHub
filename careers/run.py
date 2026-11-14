"""Collect vacancies from big companies' OWN careers sites, classify them, score how sure we are they're real,
and save data/careers/official.json for the app.   python -m careers.run

Each run has a time budget (CAREERS_BUDGET_SECONDS, default 540). Companies refreshed longest ago go first, so
over a day every company gets refreshed even though one run can't do them all.
A job stays while it keeps being seen; not seen for legit.CLOSED_AFTER_D days → dropped as probably closed.
Gates (common/gates.py, kind "careers") run before saving; if they fail the last good file is kept.
"""
import json
import os
import time

from careers import classify as K, legit, match as M, registry, sources as S
from common import gates

DATA_DIR = os.environ.get("DATA_DIR", "data")
DIR = os.path.join(DATA_DIR, "careers")
BUDGET = float(os.environ.get("CAREERS_BUDGET_SECONDS", "540"))
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


def order(companies, health):
    """Automatic companies, longest-since-refresh first (never refreshed = first), then by tier."""
    auto = [c for c in companies if c.get("ats") in S.CONNECTORS]
    return sorted(auto, key=lambda c: ((health.get(c["name"]) or {}).get("ok_at", 0), registry.TIER_RANK[c["tier"]]))


def enrich(j, company, now):
    c = K.classify(j)
    j.update(c)
    j["skills"] = M.job_skills(j)            # what the job asks for (server compares it with your resumes)
    j["hard"] = M.hard_requirements(j)
    j["legit"] = legit.official(j, company, j.get("last_seen"), now)
    j["visible"] = j["legit"]["pct"] >= 55
    if c["family"] == "Non-technical":
        j["desc"] = (j.get("desc") or "")[:DESC_KEEP_NONTECH]
    else:
        j["desc"] = (j.get("desc") or "")[:DESC_KEEP]
    return j


def run(now=None, budget=BUDGET, collect=S.collect):
    now = now or time.time()
    path = os.path.join(DIR, "official.json")
    old = load(path, {})
    jobs = {j["id"]: j for j in old.get("jobs", [])}
    health = old.get("health", {})
    companies = {c["name"]: c for c in registry.CANDIDATES}
    known = {}
    for j in jobs.values():
        if len(j.get("desc") or "") > 200:
            known.setdefault(j["company"], set()).update({j["id"], j.get("src_key") or j["id"]})
    run_health = {}
    got = collect(order(registry.CANDIDATES, health), run_health, now, budget, known)
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
        if now - j.get("last_seen", 0) > legit.CLOSED_AFTER_D * 86400:
            continue
        kept.append(enrich(j, companies.get(j["company"], {"name": j["company"], "ats": j.get("ats")}), now))
    kept.sort(key=lambda j: (j.get("company_rank", 99), registry.TIER_RANK.get(j["company_tier"], 9), -(j.get("posted") or 0)))
    prev_visible = sum(1 for j in old.get("jobs", []) if j.get("visible"))
    ok = gates.guard("careers", kept, prev_visible, health, now)
    links = [{"name": c["name"], "tier": c["tier"], "url": c["search_url"]} for c in registry.CANDIDATES if c.get("ats") == "link"]
    if ok:
        save(path, {"updated": now, "jobs": kept, "health": health, "links": links})
    else:
        old["health"] = health
        save(path, {**old, "health": health})
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
