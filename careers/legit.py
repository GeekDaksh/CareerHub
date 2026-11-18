"""'How sure are we this job is real?' — a confidence % with every check shown, so it can be verified by hand.

Why it is built this way (measured, see eval/): the scam shield's text check alone catches only ~12% of scam posts
in a public dataset (EMSCAD), while wrongly flagging ~0.2% of real ones. Text is weak evidence. WHERE the job comes
from is strong evidence: a vacancy returned by a company's own careers system, at that company's own web address,
cannot be posted by a scammer. So the score is mostly about the source, and each check says what it proved.

Bands: 95–99 Very high · 80–94 High · 55–79 Medium · below 55 Low.  It is a rule score, not a measured probability.
"""
import time
from urllib.parse import urlparse

from common import trust

ATS_HOSTS = {"amazon": ["amazon.jobs"], "google": ["google.com"], "eightfold": [],
             "greenhouse": ["greenhouse.io"], "lever": ["jobs.lever.co"], "ashby": ["jobs.ashbyhq.com"],
             "smartrecruiters": ["jobs.smartrecruiters.com"], "apple": ["jobs.apple.com"], "orc": []}
SEEN_FRESH_H = 48          # seen in the last collection runs → still open (sites are refreshed in rotation)
CLOSED_AFTER_D = 4         # not seen for this long → probably closed (kept a few days, then dropped)


def host(url):
    try:
        h = urlparse(str(url)).netloc.lower().split(":")[0]
    except Exception:
        return ""
    return h[4:] if h.startswith("www.") else h


def official_hosts(c):
    """Web addresses where this company's real job pages live."""
    hs = list(ATS_HOSTS.get(c.get("ats"), []))
    if c.get("ats") == "workday":
        hs.append(f"{c['tenant']}.{c['wd']}.myworkdayjobs.com")
    if c.get("ats") == "eightfold":
        hs.append(host(c["base"]))
    if c.get("ats") == "orc":
        hs.append(c["host"])
    hs += c.get("domains", [])
    return hs


def host_ok(url, hosts):
    h = host(url)
    return bool(h) and str(url).startswith("https://") and any(h == x or h.endswith("." + x) for x in hosts)


def band(p):
    return "Very high" if p >= 95 else "High" if p >= 80 else "Medium" if p >= 55 else "Low"


def official(job, company, last_seen=None, now=None):
    """Score a job collected from a company's own careers system."""
    now = now or time.time()
    checks, p = [], 70
    checks.append({"ok": True, "label": "From the company's own careers system",
                   "detail": f"returned by {company['name']}'s {job.get('ats') or company.get('ats')} job list, not a job board or repost"})
    if company.get("guessed"):
        p -= 15
        checks.append({"ok": False, "label": "Company's job board was found by its NAME only",
                       "detail": f"a board called '{company.get('slug')}' exists — check it's really {company['name']} "
                                 "(add the careers page link to make it certain)"})
    if host_ok(job.get("url"), official_hosts(company)):
        p += 25
        checks.append({"ok": True, "label": "Link is on the company's official site",
                       "detail": f"{host(job['url'])} belongs to {company['name']}'s careers system"})
    else:
        p -= 30
        checks.append({"ok": False, "label": "Link is NOT on the expected site",
                       "detail": f"{host(job.get('url')) or 'no link'} is not one of {', '.join(official_hosts(company))}"})
    bad = trust.scam_reasons(f"{job.get('title', '')}\n{job.get('desc', '')}")
    if bad:
        p -= 35
        checks.append({"ok": False, "label": "Scam signs in the text", "detail": "; ".join(bad)})
    else:
        p += 4
        checks.append({"ok": True, "label": "No scam signs in the text",
                       "detail": "no fees, chat-app hiring, guaranteed offers or ID requests (this check alone is weak)"})
    seen = last_seen or job.get("last_seen") or now
    age_h = (now - seen) / 3600
    if age_h <= SEEN_FRESH_H:
        checks.append({"ok": True, "label": "Still listed", "detail": f"seen on the official site {max(0, round(age_h))} h ago"})
        still_open = True
    else:
        checks.append({"ok": False, "label": "Not seen recently",
                       "detail": f"last seen {round(age_h / 24, 1)} days ago — it may be closed"})
        still_open = False
    p = max(1, min(99, p))
    return {"pct": p, "band": band(p), "checks": checks, "still_open": still_open, "method": "official"}


def from_trust(t):
    """Same shape for jobs from boards, alerts and search (common/trust.check verdicts)."""
    base = {"verified": 85, "likely": 68, "unverified": 45, "risky": 5}.get(t.get("verdict"), 40)
    checks = [{"ok": True, "label": g, "detail": ""} for g in t.get("good", [])] + \
             [{"ok": False, "label": w, "detail": ""} for w in t.get("warn", [])]
    return {"pct": base, "band": band(base), "checks": checks, "still_open": None, "method": "source + text"}
