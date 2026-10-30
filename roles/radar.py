"""Role radar — real, entry-level jobs from every safe source, checked for scams, with how-to-apply steps.

Sources
  1. Your target companies' official careers pages (from the job finder)        → most trusted
  2. Your own job-alert emails: LinkedIn, Naukri, Internshala, Wellfound, Indeed, Instahyre, Cutshort, ...
     (read from Gmail with the app password; nothing is scraped from LinkedIn)
  3. Remote job boards (RemoteOK, Himalayas, Jobicy, Remotive, We Work Remotely) — collected by the gig radar
  4. Public job pages on LinkedIn / Naukri / Internshala / Wellfound / Instahyre / Cutshort found via web search

  python -m roles.radar
"""
import csv
import email
import hashlib
import imaplib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C  # noqa: E402
from common import apply as AP  # noqa: E402
from common import feedback as FB, gates, levels, llm, settings as SETTINGS, trust  # noqa: E402
from common.search import Searcher  # noqa: E402

DATA_DIR = os.environ.get("DATA_DIR", "data")
RDIR = os.path.join(DATA_DIR, "roles")
NOW = time.time()

ALERT_SENDERS = {"linkedin.com": "LinkedIn", "naukri.com": "Naukri", "internshala.com": "Internshala",
                 "wellfound.com": "Wellfound", "angel.co": "Wellfound", "indeed.com": "Indeed",
                 "instahyre.com": "Instahyre", "cutshort.io": "Cutshort", "foundit.in": "Foundit",
                 "hirist.tech": "Hirist", "glassdoor.com": "Glassdoor", "glassdoor.co.in": "Glassdoor",
                 "unstop.com": "Unstop", "workatastartup.com": "YC Work at a Startup"}
JOB_LINK = {
    "LinkedIn": re.compile(r"linkedin\.com/(?:comm/)?jobs/view/(\d+)"),
    "Naukri": re.compile(r"naukri\.com/job-listings-[^?\s\"']+"),
    "Internshala": re.compile(r"internshala\.com/(?:internship|job)/detail/[^?\s\"']+"),
    "Wellfound": re.compile(r"(?:wellfound\.com|angel\.co)/(?:jobs|company/[^/]+/jobs)/[^?\s\"']+"),
    "Indeed": re.compile(r"indeed\.com/(?:viewjob|rc/clk|pagead/clk|m/basecamp/viewjob)[^\s\"']*"),
    "Instahyre": re.compile(r"instahyre\.com/job-[^?\s\"']+"),
    "Cutshort": re.compile(r"cutshort\.io/job/[^?\s\"']+"),
    "Foundit": re.compile(r"foundit\.in/job/[^?\s\"']+"),
    "Hirist": re.compile(r"hirist\.(?:tech|com)/j/[^?\s\"']+"),
    "Glassdoor": re.compile(r"glassdoor\.(?:co\.in|com)/(?:job-listing|partner/jobListing)[^\s\"']*"),
    "Unstop": re.compile(r"unstop\.com/(?:jobs|internships)/[^?\s\"']+"),
    "YC Work at a Startup": re.compile(r"workatastartup\.com/jobs/\d+"),
}
SEARCH_SITES = [("LinkedIn", "linkedin.com/jobs/view"), ("Naukri", "naukri.com/job-listings"),
                ("Internshala", "internshala.com"), ("Wellfound", "wellfound.com/jobs"),
                ("Instahyre", "instahyre.com"), ("Cutshort", "cutshort.io/job")]
BOARD_SOURCES = {"RemoteOK", "Himalayas", "Jobicy", "Remotive", "We Work Remotely", "Working Nomads",
                 "HN Who is hiring", "Remote-first companies"}


# ---------------------------------------------------------------- helpers
def load(name, default, folder=RDIR):
    try:
        with open(os.path.join(folder, name)) as f:
            return json.load(f)
    except Exception:
        return default


def save(name, obj):
    os.makedirs(RDIR, exist_ok=True)
    p = os.path.join(RDIR, name)
    with open(p + ".tmp", "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)


def rows(path):
    try:
        with open(os.path.join(DATA_DIR, path), newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def rid(*parts):
    return hashlib.sha1("|".join(norm(p) for p in parts).encode()).hexdigest()[:16]


def epoch(v):
    from gigs.sources import to_epoch
    return to_epoch(v)


def sectors_of(text, known=None):
    if known:
        return [s.strip() for s in str(known).split(",") if s.strip()]
    t = " " + norm(text) + " "
    out = []
    for sec, terms in C.SECTOR_CATALOG.items():
        words = list(terms) + C.INTEREST_WORDS.get(sec, []) if hasattr(C, "INTEREST_WORDS") else list(terms)
        core = [norm(w.replace(" AI", "")) for w in words]
        if any(c and f" {c}" in t for c in core):
            out.append(sec)
    return out


# ---------------------------------------------------------------- 1. target companies (job finder output)
def from_companies():
    ranked = {r["_key"]: r for r in rows("jobs/ranked.csv") if r.get("_key")}
    mail = {r["company"]: r for r in rows("jobs/company_mail.csv")}
    plan = {r.get("_key") or r["company"]: r for r in rows("jobs/outreach_plan.csv")}
    out = []
    for j in rows("jobs/jobs.csv"):
        c = j.get("company")
        rk = ranked.get(c, {})
        src = j.get("source", "")
        kind = "ats" if "job board" in src else "careers"
        out.append({
            "title": j.get("title"), "company": rk.get("company") or c, "company_key": c,
            "location": j.get("location") or rk.get("city") or "", "url": j.get("url"),
            "platform": "Company careers (ATS)" if kind == "ats" else "Company careers page",
            "source_kind": "ats", "posted": epoch(j.get("posted")), "desc": j.get("desc") or "",
            "known_sectors": rk.get("fields"), "tier": rk.get("tier"),
            "company_verified": str(mail.get(c, {}).get("receives_mail")) == "True" and bool(rk.get("website")),
            "company_domain": trust.domain(rk.get("website") or ""), "plan": plan.get(c),
        })
    return out


# ---------------------------------------------------------------- 2. job-alert emails (IMAP)
def _html_of(msg):
    html, text = None, None
    for part in msg.walk():
        ct = part.get_content_type()
        if ct == "text/html" and html is None:
            html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        elif ct == "text/plain" and text is None:
            text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
    return html, text


def _unwrap(url):
    """Alert emails wrap links in trackers; pull the real destination out when possible."""
    q = parse_qs(urlparse(url).query)
    for k in ("url", "u", "redirect", "dest", "target"):
        if k in q and q[k][0].startswith("http"):
            return q[k][0]
    return url


def canonical(platform, url):
    m = JOB_LINK[platform].search(url)
    if not m:
        return None
    if platform == "LinkedIn":
        return f"https://www.linkedin.com/jobs/view/{m.group(1)}"
    return "https://" + m.group(0)


ALERT_PROMPT = """This is a job-alert email from {platform}. List the jobs in it.
Links are numbered; use the number of the link that opens each job.
Return JSON list: [{{"title": str, "company": str, "location": str|null, "experience": str|null, "link": int}}]
Only jobs actually in the email. No invented companies.

Email text:
{text}

Links:
{links}"""


def parse_alert(platform, html, text):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        u = _unwrap(a["href"])
        c = canonical(platform, u) if platform in JOB_LINK else None
        if c and c not in [x[0] for x in links]:
            links.append((c, re.sub(r"\s+", " ", a.get_text(" ")).strip()[:120]))
    if not links and text:
        for m in re.finditer(r"https?://\S+", text):
            c = canonical(platform, _unwrap(m.group(0))) if platform in JOB_LINK else None
            if c and c not in [x[0] for x in links]:
                links.append((c, ""))
    if not links:
        return []
    body = re.sub(r"\s+", " ", soup.get_text(" ") if html else (text or ""))[:6000]
    out = llm.ask_json(ALERT_PROMPT.format(platform=platform, text=body,
                                           links="\n".join(f"{i}: {t or '(no text)'}" for i, (u, t) in enumerate(links))))
    jobs = []
    if isinstance(out, dict):
        out = next((v for v in out.values() if isinstance(v, list)), [])
    for j in out if isinstance(out, list) else []:
        try:
            u = links[int(j.get("link"))][0]
        except Exception:
            continue
        if j.get("title") and norm(j["title"])[:12] in norm(body):
            jobs.append({"title": j["title"], "company": j.get("company"), "location": j.get("location") or "",
                         "desc": j.get("experience") or "", "url": u})
    if not jobs:   # AI unavailable: keep the links with their anchor text
        jobs = [{"title": t, "company": None, "location": "", "desc": "", "url": u} for u, t in links if len(t) > 6]
    return jobs


def _dom_in(d, k):
    return d == k or d.endswith("." + k)


def alert_platform(msg):
    """Which job site sent this alert email — or None. Trusted only if (1) the real sender ADDRESS is on that
    site (the display name is ignored: anyone can write 'LinkedIn' there) and (2) Gmail's own check says the
    email's signature (DKIM) passed for that site. Forged alerts don't pass both."""
    _, addr = parseaddr(str(make_header(decode_header(msg.get("From", "")))))
    dom = addr.rsplit("@", 1)[-1].lower() if "@" in addr else ""
    plat = next((k for k in ALERT_SENDERS if _dom_in(dom, k)), None)
    if not plat:
        return None
    auth = " ".join(str(h) for h in (msg.get_all("Authentication-Results") or [])).lower()
    signed = [d.lstrip("@") for d in re.findall(r"dkim=pass[^;]*?header\.[id]=(@?[\w.-]+)", auth)]
    if not any(_dom_in(d, plat) for d in signed):
        return None
    return ALERT_SENDERS[plat]


def from_alerts(state, health):
    user, pw = os.environ.get("GMAIL_ADDRESS"), os.environ.get("GMAIL_APP_PASSWORD")
    if not (user and pw):
        health["Job-alert emails"] = {"ok": False, "count": 0, "at": NOW, "error": "Gmail not connected (add GMAIL_ADDRESS + GMAIL_APP_PASSWORD)"}
        return []
    done = set(state.get("alert_ids", []))
    out, n_mail = [], 0
    try:
        M = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        M.login(user, pw)
        M.select("INBOX", readonly=True)
        froms = " OR ".join(f"from:{d}" for d in ALERT_SENDERS)
        typ, data = M.uid("search", None, "X-GM-RAW", f'"newer_than:4d ({froms})"')
        uids = (data[0] or b"").split()[-C.ROLE_ALERT_EMAILS_PER_RUN * 2:]
        for uid in reversed(uids):
            if n_mail >= C.ROLE_ALERT_EMAILS_PER_RUN:
                break
            typ, msgdata = M.uid("fetch", uid, "(RFC822)")
            if not msgdata or not isinstance(msgdata[0], tuple):
                continue
            msg = email.message_from_bytes(msgdata[0][1])
            mid = msg.get("Message-ID") or uid.decode()
            if mid in done:
                continue
            platform = alert_platform(msg)
            if not platform:
                continue
            html, text = _html_of(msg)
            for j in parse_alert(platform, html, text):
                j.update({"platform": platform, "source_kind": "alert",
                          "posted": email.utils.parsedate_to_datetime(msg["Date"]).timestamp() if msg.get("Date") else NOW})
                out.append(j)
            done.add(mid)
            n_mail += 1
        M.logout()
        health["Job-alert emails"] = {"ok": True, "count": len(out), "emails": n_mail, "at": NOW}
    except Exception as e:
        health["Job-alert emails"] = {"ok": False, "count": 0, "at": NOW, "error": str(e)[:200]}
    state["alert_ids"] = list(done)[-500:]
    return out


# ---------------------------------------------------------------- 3. remote boards (from the gig radar's haul)
def from_boards():
    out = []
    for g in load("gigs.json", {}, folder=os.path.join(DATA_DIR, "gigs")).get("gigs", []):
        if g.get("source") not in BOARD_SOURCES or g.get("eligibility") == "blocked":
            continue
        if g.get("work_type") not in ("full-time", "internship", "unknown"):
            continue   # contract / part-time / freelance belong to the Freelance side
        out.append({"title": g["title"], "company": g.get("company"), "location": g.get("location") or "Remote",
                    "url": g["url"], "platform": g["source"], "source_kind": "ats" if g.get("official") else "board",
                    "posted": g.get("posted"), "desc": g.get("desc") or "", "work_type": g.get("work_type"),
                    "eligibility": g.get("eligibility"), "intl": True, "pay_text": g.get("pay_text") or ""})
    return out


# ---------------------------------------------------------------- 4. public job pages via search
SEARCH_PROMPT = """These are web search results for job posts. List each job post.
Return JSON list: [{{"title": str, "company": str|null, "location": str|null, "experience": str|null, "url": str}}]
Only real job posts in the results (skip lists like "500 jobs in Pune"). Use the result's url exactly.

Results:
{text}"""


def search_queries(s):
    locs = SETTINGS.cities(s) + (["India remote"] if any(x.startswith("Remote") for x in s["locations"]) else [])
    qs = []
    for role in s["roles"]:
        for name, site in SEARCH_SITES:
            for loc in locs or ["India"]:
                qs.append((name, f'site:{site} "{C.ROLE_QUERY[role]}" {loc} fresher'))
    return qs


def from_search(s, state, health):
    qs = search_queries(s)
    if not qs:
        return []
    start = state.get("search_cursor", 0) % len(qs)
    batch = (qs[start:] + qs[:start])[:C.ROLE_SEARCHES_PER_RUN]
    state["search_cursor"] = start + len(batch)
    searcher = Searcher(os.path.join(RDIR, "search_cache.json"))
    results = []
    for name, q in batch:
        for r in searcher.search(q):
            p = trust.platform_of(r["url"])
            if p and p != "Company careers (ATS)":
                results.append({**r, "platform": p})
    searcher.save()
    out, seen = [], set()
    for i in range(0, len(results), 30):
        chunk = [r for r in results[i:i + 30] if r["url"] not in seen]
        seen.update(r["url"] for r in chunk)
        if not chunk:
            continue
        text = "\n".join(f"- {r['title']} | {r['url']} | {r['snippet']}" for r in chunk)
        got = llm.ask_json(SEARCH_PROMPT.format(text=text))
        if isinstance(got, dict):
            got = next((v for v in got.values() if isinstance(v, list)), [])
        by_url = {r["url"]: r for r in chunk}
        if isinstance(got, list) and got:
            for j in got:
                if isinstance(j, dict) and j.get("url") in by_url and j.get("title"):
                    out.append({"title": j["title"], "company": j.get("company"), "location": j.get("location") or "",
                                "desc": f"{j.get('experience') or ''} {by_url[j['url']]['snippet']}", "url": j["url"],
                                "platform": by_url[j["url"]]["platform"], "source_kind": "search", "posted": None})
        else:   # no AI: LinkedIn titles parse cleanly — "Company hiring Title in City | LinkedIn"
            for r in chunk:
                m = re.match(r"(.+?) hiring (.+?) in (.+?) \| LinkedIn", r["title"])
                if m:
                    out.append({"title": m.group(2), "company": m.group(1), "location": m.group(3), "desc": r["snippet"],
                                "url": r["url"], "platform": "LinkedIn", "source_kind": "search", "posted": None})
    health["Web search (job pages)"] = {"ok": True, "count": len(out), "queries": len(batch), "at": NOW}
    return out


# ---------------------------------------------------------------- score + assemble
def score(r, s):
    sc, why = 0, []
    if r["roles"]:
        sc += 30; why.append("matches " + ", ".join(r["roles"][:2]))
    main = set(s["main_sectors"])
    if set(r["sectors"]) & main:
        sc += 20; why.append("main sector")
    elif set(r["sectors"]) & set(s["other_sectors"]):
        sc += 10
    sc += {"verified": 20, "likely": 10, "unverified": 0}.get(r["trust"]["verdict"], 0)
    if r["level"] == "entry":
        sc += 10; why.append("entry-level / intern")
    if r.get("posted") and NOW - r["posted"] < 3 * 86400:
        sc += 10; why.append("new")
    if r["location_ok"]:
        sc += 10
    if str(r.get("tier") or "").startswith("1"):
        sc += 5; why.append("India startup")
    if r.get("keywords"):
        sc += min(10, 2 * len(r["keywords"]))
    return min(100, sc), why


def run():
    s = SETTINGS.load(DATA_DIR)
    state, health = load("state.json", {}), load("health.json", {})
    old = {r["id"]: r for r in load("roles.json", {}).get("roles", [])}
    lessons = FB.load_local(DATA_DIR)          # what Daksh taught the shield (common/feedback.py)
    raw = []
    for name, fn in [("Target companies", from_companies), ("Remote boards", from_boards)]:
        try:
            got = fn()
            raw += got
            health[name] = {"ok": True, "count": len(got), "at": NOW}
        except Exception as e:
            health[name] = {"ok": False, "count": 0, "at": NOW, "error": str(e)[:200]}
    raw += from_alerts(state, health)
    try:
        raw += from_search(s, state, health)
    except Exception as e:
        health["Web search (job pages)"] = {"ok": False, "count": 0, "at": NOW, "error": str(e)[:200]}

    roles, blocked, senior, seen = {}, [], 0, set()
    for r in raw:
        if not r.get("title") or not r.get("url"):
            continue
        r["title"] = re.sub(r"\s+", " ", str(r["title"])).strip()
        key = rid(r["title"], r.get("company") or r["url"])
        if key in seen:
            continue
        seen.add(key)
        r["id"] = key
        r["level"] = levels.level(r["title"], r.get("desc"))
        if not levels.allowed(r["level"]):
            senior += 1
            continue
        t = trust.check(r, r.get("company_domain"), r.get("company_verified", False))
        bad, allowed_note = FB.apply(r, t["warn"] if t["verdict"] == "risky" else [], lessons)
        if bad:
            t = {**t, "verdict": "risky", "score": -5, "warn": list(dict.fromkeys(bad + t["warn"]))}
        elif allowed_note:
            t = {**t, "verdict": "unverified", "score": 0, "warn": allowed_note}
        r["trust"] = t
        if r["trust"]["verdict"] == "risky":
            blocked.append({"title": r["title"], "company": r.get("company"), "url": r["url"],
                            "platform": r.get("platform"), "why": r["trust"]["warn"]})
            continue
        r["roles"] = SETTINGS.roles_matched(r["title"], s) or [x for x in C.ROLE_CATALOG
                                                               if any(w in r["title"].lower() for w in C.ROLE_CATALOG[x])]
        r["sectors"] = sectors_of(f"{r['title']} {r.get('company')} {r.get('desc', '')[:800]}", r.get("known_sectors"))
        r["location_ok"] = SETTINGS.location_ok(r.get("location"), s) and r.get("eligibility") != "blocked"
        r["keywords"] = AP.keyword_tips(f"{r['title']} {r.get('desc', '')}")
        r["steps"] = AP.steps_for(r.get("platform"), r["source_kind"])
        plan = r.pop("plan", None)
        if plan and plan.get("contact_1"):
            r["referral"] = {"name": plan.get("contact_1"), "role": plan.get("contact_1_role"),
                             "email": plan.get("contact_1_email"), "grade": plan.get("contact_1_grade"),
                             "linkedin": plan.get("contact_1_linkedin")}
        r["first_seen"] = old.get(key, {}).get("first_seen") or NOW
        if r["source_kind"] in ("alert", "search"):   # one-off sightings expire; live careers/board posts don't
            seen_at = r.get("posted") or r["first_seen"]
            if NOW - seen_at > C.ROLE_MAX_AGE_DAYS * 86400:
                continue
        r["desc"] = (r.get("desc") or "")[:600]
        r["score"], r["why"] = score(r, s)
        roles[key] = r

    # alert-email and search finds are one-off sightings: keep them until they age out.
    # Careers-page and board roles that vanished were closed, so they drop.
    for k, r in old.items():
        if k not in roles and r.get("source_kind") in ("alert", "search") \
                and NOW - r.get("first_seen", NOW) < C.ROLE_MAX_AGE_DAYS * 86400:
            roles[k] = r

    ordered = sorted(roles.values(), key=lambda r: (-r["score"], -(r.get("posted") or r["first_seen"])))
    prev_blocked = load("roles.json", {}).get("blocked", [])
    urls = {b["url"] for b in blocked}
    blocked = blocked + [b for b in prev_blocked if b["url"] not in urls]   # keep history for the Safety tab
    saved = gates.guard("roles", ordered, len(old), health, NOW)
    if saved:
        save("roles.json", {"updated": NOW, "roles": ordered, "blocked": blocked[:200], "senior_hidden": senior})
    save("state.json", state)
    save("health.json", health)
    by = {}
    for r in ordered:
        by[r["source_kind"]] = by.get(r["source_kind"], 0) + 1
    print(f"roles: {len(ordered)} entry-level · {senior} senior hidden · {len(blocked)} blocked as risky · by source {by}"
          + ("" if saved else " · NOT SAVED (output check failed, last good list kept)"))
    return ordered


if __name__ == "__main__":
    run()
