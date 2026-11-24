"""Find startups' job boards with web searches like  site:jobs.lever.co "Machine Learning Engineer" remote
(also Ashby and Greenhouse), then read each company's WHOLE board through its public API.

Why both steps: a search result is one job page, maybe stale. The board's public API gives every current
opening at that company, with full descriptions, so the usual checks apply (role type, level, eligibility,
"is it real?", resume match, learning).

Per profile: each profile's own titles (their roles + field) make their own searches, and the boards those
searches find are shown only to that profile (owners). Nothing one profile finds changes another's list.

Safety / politeness:
  • a search result is only used if it matches the strict Lever / Ashby / Greenhouse link patterns
    (careers.custom.PATTERNS) → the collector reads only those three public APIs, never the pasted page itself
  • every board read passes the robots.txt gate in sources.collect
  • searches per run and boards per run are capped; search results are cached 3 days

Remote: postings marked remote-US / -Canada / -Europe etc. are dropped. Plain "Remote" is kept but marked
"remote — country not stated, check it's open to India" (careers.eligible does that).
"""
import os
import re
import time

from careers import custom as CU

BOARDS = [("lever", "jobs.lever.co"), ("ashby", "jobs.ashbyhq.com"), ("greenhouse", "boards.greenhouse.io"),
          ("greenhouse", "job-boards.greenhouse.io")]
WHERE = ["remote", "India"]
SEARCHES_PER_RUN = int(os.environ.get("BOARD_SEARCHES_PER_RUN", "16"))
BOARDS_PER_RUN = int(os.environ.get("BOARDS_PER_RUN", "25"))
SEARCH_SECONDS = float(os.environ.get("BOARD_SEARCH_SECONDS", "150"))
FORGET_AFTER_D = 30           # a board no search has found for this long is dropped


def queries(titles_by_owner):
    """[(owner, query)] — every owner's titles × the 3 job-board sites × remote / India, in a fair rotation."""
    out = []
    width = max((len(t) for t in titles_by_owner.values()), default=0)
    for i in range(width):                       # interleave owners, so one profile's list can't crowd out another
        for owner, titles in titles_by_owner.items():
            if i < len(titles):
                t = re.sub(r'["\\]', "", titles[i])[:60]
                for _, site in BOARDS:
                    for w in WHERE:
                        out.append((owner, f'site:{site} "{t}" {w}'))
    return out


def board_of(url):
    """A search result link → (ats, slug) only if it is a real Lever / Ashby / Greenhouse job link."""
    cfg = CU.from_url(str(url or "").split("?")[0])
    if cfg and cfg["ats"] in ("lever", "ashby", "greenhouse") and cfg["slug"].lower() not in ("embed", "jobs", "api"):
        return cfg["ats"], cfg["slug"]
    return None


def discover(titles_by_owner, store, searcher, now=None, budget_s=SEARCH_SECONDS, per_run=None):
    """Run this run's share of searches; remember every board found (with who found it). Returns stats."""
    now = now or time.time()
    qs = queries(titles_by_owner)
    if not qs:
        return {"queries": 0, "found": 0}
    start = store.get("cursor", 0) % len(qs)
    batch = (qs[start:] + qs[:start])[:SEARCHES_PER_RUN if per_run is None else per_run]
    boards = store.setdefault("boards", {})
    t0, done, found = time.time(), 0, 0
    for owner, q in batch:
        if time.time() - t0 > budget_s:
            break
        done += 1
        for r in searcher.search(q) or []:
            b = board_of(r.get("url"))
            if not b:
                continue
            key = f"{b[0]}:{b[1].lower()}"
            e = boards.get(key)
            if not e:
                e = boards[key] = {"ats": b[0], "slug": b[1], "first_seen": now, "owners": [], "hits": 0}
                found += 1
            e["last_hit"], e["hits"] = now, e.get("hits", 0) + 1
            if owner not in e["owners"]:
                e["owners"].append(owner)
    store["cursor"] = start + done
    for k in [k for k, e in boards.items() if now - e.get("last_hit", now) > FORGET_AFTER_D * 86400]:
        boards.pop(k)
    return {"queries": done, "found": found, "boards": len(boards)}


def companies(store, known_slugs, now=None, limit=BOARDS_PER_RUN):
    """Boards to read this run, as company entries for sources.collect (stale-first, capped). Boards that are
    already built-in companies (e.g. Databricks on Greenhouse) are skipped — they're read anyway."""
    now = now or time.time()
    out = []
    items = sorted(store.get("boards", {}).items(), key=lambda kv: kv[1].get("read_at", 0))
    for key, e in items:
        if key in known_slugs:
            continue
        name = e.get("name") or re.sub(r"[-_]+", " ", e["slug"]).strip().title()
        out.append({"name": name, "tier": "Startup", "ats": e["ats"], "slug": e["slug"], "discovered": True,
                    "owners": sorted(e["owners"]), "rank": 900, "board_key": key,
                    "found": f"found by web search on {e['ats'].title()}"})
    return out[:limit]


# "Remote" alone is kept (marked unclear); remote tied to another country / region is dropped
REMOTE_ELSEWHERE = re.compile(r"\b(us|usa|u\.s\.|united states|canada|uk|united kingdom|europe|eu|emea|latam|"
                              r"americas|north america|germany|france|spain|poland|brazil|mexico|australia|"
                              r"est|pst|cet|us[- ]only)\b", re.I)
REMOTE = re.compile(r"\b(remote|anywhere|worldwide|work from home|wfh|distributed)\b", re.I)


def reach(location):
    """→ 'india' | 'remote-open' | 'remote-unclear' | None (not reachable from India)."""
    from careers.sources import INDIA, REMOTE_OPEN
    loc = str(location or "")
    if INDIA.search(loc):
        return "india"
    if REMOTE.search(loc):
        if REMOTE_OPEN.search(loc) and not REMOTE_ELSEWHERE.search(loc):
            return "remote-open"
        if REMOTE_ELSEWHERE.search(loc):
            return None
        return "remote-unclear"
    return None
