"""Learning from Daksh's feedback — done safely.

The app has three buttons: "Report scam" (on a shown job or gig), "Not a scam" (on a blocked post) and
"Wrong level" (on a job). Each press is a REPORT. The learner turns reports into LESSONS:

  allow_urls     "Not a scam" on one blocked post → that one post is shown again, with a warning tag.
                 It's Daksh's own decision about one post, so it applies on the next run (no vote needed).
  hide_urls      "Report scam" on one post → that post is hidden (also immediately, in the app).
  block_domains  a whole website is blocked only when ALL of these hold:
                   • at least MIN_VOTES different posts from that site were reported as scams
                   • no post from that site was marked "Not a scam"
                   • the site is not protected (job platforms, ATS careers sites, big sites)
                   • blocking it would not hide any post from a verified source,
                     nor more than MAX_HIDE_SHARE of what is shown now (stops one bad vote wiping a feed)
                 Otherwise the lesson stays in `pending` with the reason.
  rule_feedback  "Not a scam" counts per shield rule → shown in the app, and read by a person before the next
                 improvement-loop run. Rules are never edited automatically.
  level_cases    "Wrong level" reports → a small personal test set, scored by `python -m eval.run_eval`
                 as a separate view. Never used on the EMSCAD test split.

Every accepted change makes a new version with a snapshot, so any version can be restored:
  python -m common.feedback learn          # run by the scheduled workflow
  python -m common.feedback rollback 3     # go back to version 3
No AI reads the reports (so a post's text can't instruct the learner). The evaluation never loads lessons.
"""
import copy
import json
import os
import sys
import time
from urllib.parse import urlparse

from common import trust

REPORTS_PATH = "feedback/reports.json"
LESSONS_PATH = "lessons/lessons.json"
VERDICTS = {"scam", "not_scam", "senior", "entry"}
MIN_VOTES = 2
MAX_HIDE_SHARE = 0.3
MAX_REPORTS = 2000
PROTECTED = (set(trust.ATS_DOMAINS) | set(trust.PLATFORM_DOMAINS) |
             {"google.com", "github.com", "gmail.com", "medium.com", "notion.site", "notion.so", "docs.google.com",
              "forms.gle", "microsoft.com", "amazon.com", "huggingface.co", "kaggle.com"})


def empty():
    return {"version": 0, "updated": None, "allow_urls": [], "hide_urls": [], "block_domains": {},
            "pending": [], "rule_feedback": {}, "level_cases": [], "history": []}


def protected(d):
    return trust.in_set(d, PROTECTED)


def _url_ok(u):
    p = urlparse(str(u or ""))
    return p.scheme in ("http", "https") and bool(p.netloc)


def make_report(verdict, item, kind):
    """Build a report from an item the SERVER found in its own data (never from what the browser claims)."""
    if verdict not in VERDICTS:
        raise ValueError("unknown verdict")
    if kind not in ("gig", "role", "blocked"):
        raise ValueError("unknown kind")
    url = str(item.get("url") or "")
    if not _url_ok(url):
        raise ValueError("item has no web link")
    return {"at": time.time(), "verdict": verdict, "kind": kind, "url": url[:500], "domain": trust.domain(url),
            "title": str(item.get("title") or "")[:200], "reasons": [str(x)[:120] for x in (item.get("why") or [])][:8],
            "level": str(item.get("level") or "")[:20]}


def add_report(reports, rep):
    reports = [r for r in reports if not (r["url"] == rep["url"] and r["verdict"] == rep["verdict"])]  # one vote per post
    return (reports + [rep])[-MAX_REPORTS:]


def learn(reports, lessons, shown_items, now=None):
    """Return (new_lessons, changes). shown_items = what the feed shows now, each with url and trust verdict."""
    now = now or time.time()
    L = copy.deepcopy(lessons or empty())
    before = json.dumps({k: L[k] for k in ("allow_urls", "hide_urls", "block_domains")}, sort_keys=True)
    changes = []
    latest = {}
    for r in sorted(reports, key=lambda r: r["at"]):
        if r["verdict"] in ("scam", "not_scam"):
            latest[r["url"]] = r                         # the newest scam/not-scam vote on a post wins
    allow = sorted(u for u, r in latest.items() if r["verdict"] == "not_scam")
    hide = sorted(u for u, r in latest.items() if r["verdict"] == "scam")
    for u in set(allow) - set(L["allow_urls"]):
        changes.append(f"show again (you marked it not a scam): {u}")
    for u in set(hide) - set(L["hide_urls"]):
        changes.append(f"hide (you reported it): {u}")
    L["allow_urls"], L["hide_urls"] = allow, hide

    # rule feedback: which shield rules blocked posts you said were fine
    rf = {}
    for r in latest.values():
        if r["verdict"] == "not_scam":
            for why in r.get("reasons") or ["(no reason recorded)"]:
                rf[why] = rf.get(why, 0) + 1
    L["rule_feedback"] = dict(sorted(rf.items(), key=lambda x: -x[1]))

    # level cases: a personal test set
    L["level_cases"] = [{"title": r["title"], "truth": r["verdict"], "app_said": r.get("level"), "url": r["url"]}
                        for r in reports if r["verdict"] in ("senior", "entry")][-300:]

    # whole-site blocks: voted, tested, versioned
    by_dom = {}
    for r in latest.values():
        e = by_dom.setdefault(r["domain"], {"scam": set(), "not_scam": set(), "last": 0})
        e[r["verdict"]].add(r["url"])
        e["last"] = max(e["last"], r["at"])
    pending = []
    for d, v in sorted(by_dom.items()):
        if not v["scam"] or d in L["block_domains"]:
            continue
        why = None
        if protected(d):
            why = "protected site (a job platform or big site) — only the reported posts are hidden"
        elif v["not_scam"]:
            why = f"you also marked {len(v['not_scam'])} post(s) from this site as not a scam"
        elif len(v["scam"]) < MIN_VOTES:
            why = f"needs {MIN_VOTES} reported posts from this site, has {len(v['scam'])}"
        else:
            hit = [it for it in shown_items if trust.in_set(trust.domain(it.get("url")), {d})]
            ver = [it for it in hit if (it.get("trust") or {}).get("verdict") == "verified"]
            if ver:
                why = f"would hide {len(ver)} post(s) from a verified source — not blocked"
            elif shown_items and len(hit) > max(3, MAX_HIDE_SHARE * len(shown_items)):
                why = f"would hide {len(hit)} of {len(shown_items)} shown posts — too many, not blocked"
        if why:
            pending.append({"domain": d, "votes": len(v["scam"]), "why": why})
        else:
            L["block_domains"][d] = {"votes": len(v["scam"]), "since": v["last"]}   # report time, so re-runs match
            changes.append(f"block site {d} ({len(v['scam'])} posts reported, test passed)")
    # a site you later marked safe is unblocked
    for d in list(L["block_domains"]):
        if by_dom.get(d, {}).get("not_scam"):
            del L["block_domains"][d]
            changes.append(f"unblock site {d} (you marked a post from it not a scam)")
    L["pending"] = pending

    after = json.dumps({k: L[k] for k in ("allow_urls", "hide_urls", "block_domains")}, sort_keys=True)
    if after != before:
        L["version"] += 1
        L["updated"] = now
        snap = {k: copy.deepcopy(L[k]) for k in ("allow_urls", "hide_urls", "block_domains")}
        L["history"] = (L["history"] + [{"version": L["version"], "at": now, "changes": changes, "snapshot": snap}])[-50:]
    return L, changes


def rollback(lessons, version):
    for h in lessons.get("history", []):
        if h["version"] == version:
            L = copy.deepcopy(lessons)
            L.update(copy.deepcopy(h["snapshot"]))
            L["version"] += 1
            L["history"].append({"version": L["version"], "at": time.time(), "changes": [f"rolled back to v{version}"],
                                 "snapshot": copy.deepcopy(h["snapshot"])})
            return L
    raise ValueError(f"no version {version} in history")


# ---------------------------------------------------------------- used by the radars
def apply(item, reasons, lessons):
    """Return (reasons, extra_warn) after lessons: blocked sites add a reason; a post you marked safe is let
    through with a warning that still names what the shield found."""
    if not lessons:
        return reasons, []
    url, d = str(item.get("url") or ""), trust.domain(item.get("url"))
    reasons = list(reasons)
    if url in lessons.get("hide_urls", []):
        reasons.append("you reported this post as a scam")
    if any(trust.in_set(d, {x}) for x in lessons.get("block_domains", {})):
        reasons.append("you reported scams from this website before")
    if url in lessons.get("allow_urls", []) and reasons:
        return [], ["you marked this as not a scam — the shield had found: " + "; ".join(reasons)]
    return reasons, []


def load_local(data_dir):
    try:
        with open(os.path.join(data_dir, LESSONS_PATH)) as f:
            return json.load(f)
    except Exception:
        return None


def _main():
    data_dir = os.environ.get("DATA_DIR", "data")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    lp = os.path.join(data_dir, LESSONS_PATH)

    def read(p, d):
        try:
            with open(os.path.join(data_dir, p)) as f:
                return json.load(f)
        except Exception:
            return d
    lessons = read(LESSONS_PATH, empty())
    if cmd == "learn":
        reports = read(REPORTS_PATH, {"reports": []}).get("reports", [])
        shown = [g for g in read("gigs/gigs.json", {}).get("gigs", []) if g.get("visible")] + \
                read("roles/roles.json", {}).get("roles", [])
        new, changes = learn(reports, lessons, shown)
    elif cmd == "rollback":
        new, changes = rollback(lessons, int(sys.argv[2])), [f"rolled back to v{sys.argv[2]}"]
    else:
        print(__doc__)
        return
    os.makedirs(os.path.dirname(lp), exist_ok=True)
    with open(lp + ".tmp", "w") as f:
        json.dump(new, f, indent=1)
    os.replace(lp + ".tmp", lp)
    print(f"lessons v{new['version']}: {len(changes)} change(s)" + "".join(f"\n  - {c}" for c in changes)
          + "".join(f"\n  pending {p['domain']}: {p['why']}" for p in new["pending"]))


if __name__ == "__main__":
    _main()
