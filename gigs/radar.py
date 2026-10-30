"""Gig radar: collect paid work from free sources, drop what you can't take (location, scams, low pay),
score the rest for YOU, and write an AI summary + proposal draft for the best new ones.

  python -m gigs.radar          (reads/writes $DATA_DIR/gigs)
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C  # noqa: E402
from common import llm  # noqa: E402
from gigs import sources as S  # noqa: E402
from common import feedback as FB, gates, levels, settings as SETTINGS, trust  # noqa: E402

DATA_DIR = os.environ.get("DATA_DIR", "data")
GDIR = os.path.join(DATA_DIR, "gigs")
NOW = time.time()


# ---------------------------------------------------------------- files
def load(name, default):
    try:
        with open(os.path.join(GDIR, name)) as f:
            return json.load(f)
    except Exception:
        return default


def save(name, obj):
    os.makedirs(GDIR, exist_ok=True)
    p = os.path.join(GDIR, name)
    with open(p + ".tmp", "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)


# ---------------------------------------------------------------- rules
BLOCK_LOC = re.compile(
    r"\b(us only|usa only|u\.s\. only|united states only|us[- ]based|based in the us|must (?:be|reside|live) in (?:the )?"
    r"(?:us|usa|u\.s\.|united states|uk|eu|europe|canada|australia|germany)|uk only|eu only|europe only|canada only|"
    r"north america only|americas only|latam only|emea only|us citizens?|green card|us work authori[sz]ation|"
    r"security clearance|on-?site only|onsite|in-office|hybrid)\b", re.I)
OK_LOC = re.compile(r"worldwide|anywhere|global|india|asia|apac|any location|no location|international", re.I)
SCAM = [
    (r"telegram|whats\s?app", "asks to move to Telegram/WhatsApp"),
    (r"(registration|joining|security|training|onboarding|application)\s+(fee|charge|deposit)", "asks you to pay a fee"),
    (r"pay\s+to\s+(apply|join|start)|upfront (fee|payment) from you|refundable deposit", "asks you to pay first"),
    (r"crypto(currency)?\s+(wallet|transfer)|usdt|gift ?cards?|western union", "crypto / gift-card payments"),
    (r"like (?:our )?(?:posts|videos)|rate products|review products for (?:cash|money)|subscribe to channels",
     "click / like tasks (classic scam)"),
    (r"earn\s+(?:rs\.?|₹|\$)\s?\d[\d,]*\s*(?:per|a|/)\s*day|daily (?:payment|income) guaranteed",
     "promises a fixed daily income"),
    (r"send (?:me |us )?your (?:bank|card|otp|password|aadhaar|pan)", "asks for bank / ID details"),
    (r"free (?:sample|test) (?:work|project) (?:of|for) (?:the )?(?:full|whole|entire)", "wants the full job free as a 'test'"),
]
GIG_TYPES = {"freelance", "contract", "part-time"}   # internships / full-time roles live on the Career side
MY_WORDS = sorted({w.lower() for w in C.PROFILE["skills"]} |
                  {w for w in C.GIG_CATEGORIES["tech"]["words"]} |
                  {w for w in C.GIG_CATEGORIES["ai_tasks"]["words"]})


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def eligibility(g):
    """ok = you can take it from India, check = unclear, blocked = not open to India."""
    if g["source"] == "Freelancer.com":
        return "ok"
    r = [str(x).lower() for x in g.get("restrictions") or []]
    if r:
        return "ok" if any(x in ("india", "asia", "apac", "worldwide", "anywhere") for x in r) else "blocked"
    loc = f"{g.get('location') or ''}"
    text = f"{loc} {g.get('title', '')} {g.get('desc', '')[:600]}"
    if OK_LOC.search(loc):
        return "ok"
    if BLOCK_LOC.search(text):
        return "blocked"
    if re.search(r"\b(usa|united states|canada|europe|uk|united kingdom|germany|australia|latam|emea|north america|"
                 r"brazil|mexico|philippines|poland|spain|france|netherlands)\b", loc, re.I):
        return "blocked"
    return "check"


def category(g):
    title = norm(g["title"])
    body = norm(f"{g.get('desc', '')[:800]} {' '.join(map(str, g.get('tags') or []))}")
    best, best_score = "other", 0
    for cat, spec in C.GIG_CATEGORIES.items():
        s = sum(3 for w in spec["words"] if norm(w) and norm(w) in title) + \
            sum(1 for w in spec["words"] if norm(w) and norm(w) in body)
        if s > best_score:
            best, best_score = cat, s
    return best


def scam_flags(g):
    """Shared scam shield (common/trust.py) + gig-specific rules."""
    text = f"{g['title']} {g.get('desc', '')}"
    out = trust.scam_reasons(text)
    d = trust.domain(g.get("url"))
    if trust.in_set(d, trust.SHORTENERS) or d.endswith(trust.BAD_TLDS):
        out.append("suspicious link")
    return list(dict.fromkeys(out))


def inr(v, cur):
    """Convert to ₹. An unknown currency gives None (pay unknown) — never a silent guess."""
    rate = C.FX_TO_INR.get(str(cur or "").upper())
    return None if v is None or rate is None else v * rate


def pay_text(g):
    """Pay in the client's own currency, e.g. 'USD 15–25/hr'. Empty when no amount is given."""
    lo, hi, cur = g.get("budget_min"), g.get("budget_max"), str(g.get("currency") or "").upper()
    if not (lo or hi) or not cur:
        return ""
    rng = "–".join(f"{x:,.0f}" for x in dict.fromkeys(x for x in (lo, hi) if x))
    per = {"hourly": "/hr", "fixed": " fixed", "salary": "/yr"}.get(g.get("pay_type"), "")
    return f"{cur} {rng}{per}"


def is_intl(g):
    """International client / employer. Freelancer.com shows the client's currency; the remote boards are global."""
    if g["source"] == "Freelancer.com":
        return str(g.get("currency") or "").upper() not in ("", "INR")
    return True


def pay_inr(g):
    vals = [x for x in (inr(g.get("budget_min"), g.get("currency")), inr(g.get("budget_max"), g.get("currency")))
            if x is not None]
    return sum(vals) / len(vals) if vals else None


def match_project(text):
    t = text.lower()
    best = None
    for pj in C.PROFILE["projects"]:
        hits = [k for k in pj["keywords"] if k in t]
        if hits and (best is None or len(hits) > len(best[1])):
            best = (pj, hits)
    return best


def score(g):
    """0–100: how good this gig is for you right now. Also returns plain-language reasons."""
    why, s = [], 0.0
    cat = g["category"]
    weight = C.GIG_CATEGORIES.get(cat, {}).get("weight", 0.3)
    s += 30 * weight
    why.append(C.GIG_CATEGORIES.get(cat, {}).get("label", "other"))

    text = f"{g['title']} {g.get('desc', '')} {' '.join(map(str, g.get('tags') or []))}".lower()
    hits = [w for w in MY_WORDS if re.search(r"(?<![a-z])" + re.escape(w), text)]
    if hits:
        s += min(25, 6 * len(hits))
        why.append("matches " + ", ".join(hits[:4]))

    v = pay_inr(g)
    pt = g.get("pay_type")
    if pt == "hourly" and v:
        if v >= 1500:
            s += 15; why.append(f"~₹{v:,.0f}/hr")
        elif v >= 800:
            s += 10; why.append(f"~₹{v:,.0f}/hr")
        elif v >= C.MIN_HOURLY_INR:
            s += 5; why.append(f"~₹{v:,.0f}/hr")
        else:
            s -= 15; why.append(f"low pay ~₹{v:,.0f}/hr")
    elif pt == "fixed" and v:
        lo, hi = C.FIXED_SWEET_SPOT_INR
        if lo <= v <= hi:
            s += 12; why.append(f"~₹{v:,.0f} fixed, right size for your hours")
        elif v > hi:
            s += 5; why.append(f"~₹{v:,.0f} fixed (big project)")
        else:
            s -= 5; why.append(f"small budget ~₹{v:,.0f}")

    b = g.get("bids")
    if isinstance(b, (int, float)):
        if b <= 5:
            s += 10; why.append(f"only {int(b)} bids")
        elif b <= 15:
            s += 6; why.append(f"{int(b)} bids")
        elif b <= 40:
            s += 2
        elif b > 80:
            s -= 8; why.append(f"{int(b)} bids (crowded)")

    age_h = (NOW - g["posted"]) / 3600 if g.get("posted") else None
    if age_h is not None:
        if age_h <= 24:
            s += 10; why.append("posted today")
        elif age_h <= 72:
            s += 5
        elif age_h > 7 * 24:
            s -= 5

    wt = g.get("work_type")
    if wt in GIG_TYPES:
        s += 5
    elif wt == "full-time":
        s -= 10

    el = g["eligibility"]
    if el == "ok":
        s += 5
    elif el == "blocked":
        s -= 100

    m = match_project(text)
    if m:
        s += 5
        g["project_match"] = m[0]["name"]
    if g["scam"]:
        s -= 40 * len(g["scam"])
    return max(0, min(100, round(s))), why


# ---------------------------------------------------------------- AI notes + proposal draft
NOTE_PROMPT = """You help a student freelancer decide fast whether to bid on a gig, and draft the bid.
Freelancer: {name}, {intro}. Skills: {skills}.
Real projects (only claim these): {projects}.
He has under {hours} hours per week. Never invent experience, clients, years or numbers.

Gig ({source}): {title}
Budget: {budget}
Details: {desc}

Return JSON:
{{"summary": "what they want, max 25 words, plain English",
  "est_hours": integer hours of work for him,
  "fit_1_10": integer,
  "why_fit": "max 20 words",
  "red_flags": ["short items, empty if none"],
  "proposal": "70-110 words. Start with their problem, not 'I'. One proof from his real projects or skills that fits. A concrete first step. End with one question. No price unless the gig asks. Plain, friendly."}}"""


def budget_text(g):
    if g.get("budget_min") or g.get("budget_max"):
        cur = g.get("currency") or ""
        rng = "–".join(f"{x:,.0f}" for x in [g.get("budget_min"), g.get("budget_max")] if x)
        return f"{cur} {rng} ({g.get('pay_type')})"
    return g.get("salary_text") or "not stated"


def ai_note(g):
    proj = "; ".join(p["name"] for p in C.PROFILE["projects"])
    out = llm.ask_json(NOTE_PROMPT.format(
        name=C.PROFILE["first_name"], intro=C.PROFILE["intro"], skills=", ".join(C.PROFILE["skills"]),
        projects=proj, hours=C.HOURS_PER_WEEK, source=g["source"], title=g["title"], budget=budget_text(g),
        desc=(g.get("desc") or "")[:1800]))
    if isinstance(out, list):
        out = next((x for x in out if isinstance(x, dict)), None)
    if not isinstance(out, dict) or not out.get("proposal"):
        return None
    out["date"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
    return out


# ---------------------------------------------------------------- main
def collect(state, health):
    chosen = SETTINGS.load(DATA_DIR)["gig_types"]   # your gig types from Settings
    words = [w for t in chosen for w in C.GIG_QUERIES.get(t, [])]
    jobs = [
        ("Freelancer.com", lambda: S.freelancer(words)),
        ("RemoteOK", S.remoteok),
        ("Himalayas", S.himalayas),
        ("Jobicy", S.jobicy),
        ("We Work Remotely", S.weworkremotely),
        ("Hacker News", S.hn_freelancer),
        ("Working Nomads", S.working_nomads),
        ("HN Who is hiring", S.hn_hiring),
        ("Remote-first companies", lambda: S.remote_companies(C.REMOTE_COMPANIES)),
    ]
    if NOW - state.get("remotive_last", 0) >= 11 * 3600:   # Remotive asks for a few calls per day at most
        jobs.append(("Remotive", S.remotive))
    out = []
    previous = load("gigs.json", {}).get("gigs", [])
    carry = lambda src: [g for g in previous if g["source"] == src]   # keep last good gigs if a source is down
    for name, fn in jobs:
        t0 = time.time()
        try:
            got = fn()
            out += got
            health[name] = {"ok": True, "count": len(got), "at": NOW, "secs": round(time.time() - t0, 1)}
            if name == "Remotive":
                state["remotive_last"] = NOW
        except Exception as e:
            prev = health.get(name, {})
            health[name] = {"ok": False, "count": 0, "at": NOW, "error": str(e)[:200],
                            "last_ok": prev.get("at") if prev.get("ok") else prev.get("last_ok")}
            out += carry(name)
        print(f"  {name}: {health[name].get('count')} {'ok' if health[name]['ok'] else 'FAILED ' + health[name].get('error', '')}")
    if "Remotive" not in dict(jobs):
        out += carry("Remotive")
    return out


def run():
    state = load("state.json", {})
    health = load("health.json", {})
    seen = load("seen.json", {})
    notes = load("ai_notes.json", {})
    old = {g["id"]: g for g in load("gigs.json", {}).get("gigs", [])}
    prev_visible = sum(1 for g in old.values() if g.get("visible"))
    lessons = FB.load_local(DATA_DIR)          # what Daksh taught the shield (common/feedback.py)

    raw = collect(state, health)
    max_age = C.MAX_GIG_AGE_DAYS * 86400
    gigs, keys = {}, set()
    for g in raw:
        if not g.get("id") or not g.get("title") or not g.get("url"):
            continue
        if g.get("posted") and NOW - g["posted"] > max_age:
            continue
        k = norm(g["title"]) + "|" + norm(g.get("company"))
        if k in keys and g["id"] not in gigs:
            continue
        keys.add(k)
        g["first_seen"] = seen.get(g["id"]) or old.get(g["id"], {}).get("first_seen") or NOW
        seen[g["id"]] = g["first_seen"]
        g["eligibility"] = eligibility(g)
        g["category"] = category(g)
        g["scam"], allowed_note = FB.apply(g, scam_flags(g), lessons)
        g["pay_inr"] = pay_inr(g)
        g["pay_text"] = pay_text(g)
        g["intl"] = is_intl(g)
        cur = str(g.get("currency") or "").upper()
        g["pays_foreign"] = bool(g["pay_text"]) and cur != "INR" and cur in C.FX_TO_INR   # a known foreign currency
        g["score"], g["why"] = score(g)
        g["level"] = levels.level(g["title"], g.get("desc"))
        board = g["source"] not in ("Freelancer.com", "Hacker News")
        g["trust"] = trust.check({**g, "source_kind": "freelance" if not board else "board"})
        if allowed_note:
            g["trust"] = {**g["trust"], "verdict": "unverified", "warn": allowed_note}
        elif g["scam"] and g["trust"]["verdict"] != "risky":
            g["trust"] = {**g["trust"], "verdict": "risky", "score": -5, "warn": g["scam"] + g["trust"]["warn"]}
        g["visible"] = (g["eligibility"] != "blocked" and not g["scam"] and g["category"] != "other"
                        # job boards: only contract / part-time / freelance here; full-time roles go to Career
                        and (not board or g["work_type"] in GIG_TYPES)
                        and not (board and g["level"] == "senior")
                        and not (g["pay_type"] == "hourly" and g["pay_inr"] and g["pay_inr"] < C.MIN_HOURLY_INR))
        gigs[g["id"]] = g

    # AI notes for the best new visible gigs
    todo = sorted((g for g in gigs.values() if g["visible"] and g["id"] not in notes and g["score"] >= 45),
                  key=lambda g: -g["score"])[:C.GIG_AI_NOTES_PER_RUN]
    for g in todo:
        n = ai_note(g)
        if n:
            notes[g["id"]] = n
        elif llm.exhausted():
            break
    for g in gigs.values():
        g["ai"] = notes.get(g["id"])
        if g["ai"] and g["ai"].get("red_flags"):
            g["score"] = max(0, g["score"] - 5 * len(g["ai"]["red_flags"]))

    keep_ids = set(gigs)
    notes = {k: v for k, v in notes.items() if k in keep_ids}
    seen = {k: v for k, v in seen.items() if NOW - v < 60 * 86400}
    ordered = sorted(gigs.values(), key=lambda g: (-g["visible"], -g["score"], -(g.get("posted") or 0)))
    saved = gates.guard("gigs", ordered, prev_visible, health, NOW)
    if saved:
        save("gigs.json", {"updated": NOW, "gigs": ordered})
        save("seen.json", seen)
        save("ai_notes.json", notes)
    save("health.json", health)
    runs = state.get("runs", [])[-29:] + [{"at": NOW, "total": len(gigs), "visible": sum(g["visible"] for g in gigs.values()),
                                           "new": sum(1 for g in gigs.values() if g["first_seen"] == NOW)}]
    state["runs"] = runs
    save("state.json", state)
    vis = [g for g in ordered if g["visible"]]
    print(f"gigs: {len(gigs)} collected · {len(vis)} shown · {runs[-1]['new']} new · AI notes: {len(todo)} tried"
          + ("" if saved else " · NOT SAVED (output check failed, last good list kept)"))
    return ordered


if __name__ == "__main__":
    run()
