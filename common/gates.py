"""Output gates for the radars. They run just before gigs.json / roles.json are written.

If a check fails, the new file is NOT written: the app keeps showing the last good file, and the failure is
recorded in health.json (the Status tab shows it). Nothing crashes, so the rest of the scheduled run continues.

Checks (each one returns plain-language problems, up to 5 examples):
  schema       every item has the fields the app needs, with the right types
  links        every link is a normal http(s) web address (no javascript:, data:, file: links)
  unique       no two items share an id
  safety       nothing the scam shield blocked is marked as visible
  collapse     the number of visible items did not fall off a cliff (usually means every source broke at once)
"""
from urllib.parse import urlparse

MAX_EXAMPLES = 5


class GateFailed(Exception):
    def __init__(self, gate, problems):
        self.gate, self.problems = gate, problems
        super().__init__(f"{gate}: " + "; ".join(problems[:MAX_EXAMPLES]))


def _url_ok(u):
    try:
        p = urlparse(str(u or "").strip())
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc) and " " not in p.netloc


SCHEMAS = {
    "gigs": {"id": str, "title": str, "url": str, "source": str, "visible": bool, "score": (int, float),
             "scam": list, "category": str},
    "roles": {"id": str, "title": str, "url": str, "source_kind": str, "score": (int, float), "trust": dict,
              "level": str},
    "careers": {"id": str, "title": str, "url": str, "company": str, "company_tier": str, "family": str,
                "level": str, "legit": dict, "visible": bool, "last_seen": (int, float)},
}


def check_items(kind, items, prev_visible=None, min_keep=0.2, min_prev=10):
    """Run every gate on a list of gigs or roles. Raises GateFailed on the first gate that fails.
    prev_visible = how many items were visible in the last good file (for the collapse check)."""
    if not isinstance(items, list):
        raise GateFailed("schema", [f"{kind} must be a list, got {type(items).__name__}"])
    schema = SCHEMAS[kind]
    bad = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            bad.append(f"item {i} is {type(it).__name__}, not an object")
            continue
        for k, t in schema.items():
            if k not in it:
                bad.append(f"item {i} ({str(it.get('title'))[:40]!r}) missing '{k}'")
            elif not isinstance(it[k], t) or (isinstance(it[k], bool) and t is not bool):   # True is not a score
                bad.append(f"item {i} field '{k}' is {type(it[k]).__name__}")
    if bad:
        raise GateFailed("schema", bad)

    bad = [f"{it['title'][:40]!r}: {str(it['url'])[:60]}" for it in items if not _url_ok(it["url"])]
    if bad:
        raise GateFailed("links", bad)

    seen, dup = set(), []
    for it in items:
        if it["id"] in seen:
            dup.append(it["id"])
        seen.add(it["id"])
    if dup:
        raise GateFailed("unique", [f"id {d} appears more than once" for d in dup])

    if kind == "gigs":
        bad = [it["title"][:50] for it in items if it["visible"] and it["scam"]]
    elif kind == "careers":
        bad = [it["title"][:50] for it in items if it["visible"] and it["legit"].get("pct", 0) < 55]
    else:
        bad = [it["title"][:50] for it in items if it["trust"].get("verdict") == "risky"]
    if bad:
        raise GateFailed("safety", [f"blocked item would be shown: {t!r}" for t in bad])

    vis = sum(1 for it in items if it.get("visible", True))
    if prev_visible is not None and prev_visible >= min_prev and vis < min_keep * prev_visible:
        raise GateFailed("collapse", [f"visible items fell from {prev_visible} to {vis} in one run "
                                      f"(below {int(min_keep * 100)}%) — most likely the sources broke, not the market"])
    return {"checked": len(items), "visible": vis, "gates": ["schema", "links", "unique", "safety", "collapse"]}


def guard(kind, items, prev_visible, health, now):
    """Run the gates; on failure record it in health and return False (caller must keep the old file)."""
    try:
        info = check_items(kind, items, prev_visible)
    except GateFailed as e:
        health["Output check"] = {"ok": False, "count": 0, "at": now, "error":
                                  f"{e.gate} check failed — kept the last good list. " + "; ".join(e.problems[:MAX_EXAMPLES])}
        print(f"GATE FAILED ({kind}/{e.gate}): kept last good file. {e}")
        return False
    health["Output check"] = {"ok": True, "count": info["checked"], "at": now}
    return True
