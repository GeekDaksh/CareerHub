"""Free, public gig sources. Each returns a list of normalised gigs:
{id, source, title, url, company, desc, posted (epoch s), pay_type, budget_min, budget_max, currency,
 location, restrictions, work_type, tags, bids}
Every source is fail-safe: an error only marks that source unhealthy.
"""
import html
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

UA = {"User-Agent": "CareerHub/1.0 (personal freelance search)", "Accept": "application/json, */*"}
SESSION = requests.Session()
SESSION.headers.update(UA)


MAX_SECONDS = 60          # whole download, not per chunk: a server that trickles bytes can't stall the run
MAX_BYTES = 25_000_000


def get(url, params=None, timeout=30, as_json=True):
    start = time.time()
    with SESSION.get(url, params=params, timeout=timeout, stream=True) as r:
        r.raise_for_status()
        buf = bytearray()
        r.raw.decode_content = True
        while True:   # read1 returns whatever has arrived (up to 64 KB), so the deadline is checked often
            chunk = r.raw.read1(65536) if hasattr(r.raw, "read1") else r.raw.read(65536)
            if not chunk:
                break
            buf += chunk
            if len(buf) > MAX_BYTES:
                raise RuntimeError(f"response over {MAX_BYTES // 1_000_000} MB")
            if time.time() - start > MAX_SECONDS:
                raise RuntimeError(f"download took over {MAX_SECONDS}s")
        text = bytes(buf).decode(r.encoding or "utf-8", "replace")
    import json as _json
    return _json.loads(text) if as_json else text


def strip_html(s, limit=1500):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", str(s or ""), flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</li>", "\n", s, flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s).strip()
    return s[:limit]


def to_epoch(v):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v / 1000 if v > 1e12 else v)
    s = str(v).strip()
    if s.isdigit():
        return to_epoch(int(s))
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d"):
        try:
            d = datetime.strptime(s.replace("Z", "+0000"), fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d.timestamp()
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(s).timestamp()
    except Exception:
        return None


def work_type_of(*texts):
    t = " ".join(str(x or "") for x in texts).lower()
    if re.search(r"freelanc|gig\b|one[- ]off|per task|per project", t):
        return "freelance"
    if re.search(r"contract|contractor|temporary|temp\b", t):
        return "contract"
    if re.search(r"part[- _]?time", t):
        return "part-time"
    if re.search(r"intern", t):
        return "internship"
    if re.search(r"full[- _]?time|permanent", t):
        return "full-time"
    return "unknown"


def num(v):
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- Freelancer.com
def freelancer(queries):
    out, seen = [], set()
    for q in queries:
        d = get("https://www.freelancer.com/api/projects/0.1/projects/active/",
                params={"query": q, "limit": 30, "job_details": "true", "compact": "true"})
        for p in (d.get("result") or {}).get("projects", []):
            if p.get("id") in seen:
                continue
            seen.add(p.get("id"))
            if p.get("language") and p.get("language") != "en":
                continue
            b, cur = p.get("budget") or {}, (p.get("currency") or {}).get("code")
            out.append({
                "id": f"freelancer:{p['id']}", "source": "Freelancer.com", "title": p.get("title", ""),
                "url": f"https://www.freelancer.com/projects/{p.get('seo_url', p['id'])}",
                "company": None, "desc": strip_html(p.get("description") or p.get("preview_description")),
                "posted": to_epoch(p.get("time_submitted") or p.get("submitdate")),
                "pay_type": "hourly" if p.get("type") == "hourly" else "fixed",
                "budget_min": num(b.get("minimum")), "budget_max": num(b.get("maximum")), "currency": cur or "USD",
                "location": "Remote (Freelancer.com)", "restrictions": [], "work_type": "freelance",
                "tags": [j.get("name") for j in p.get("jobs") or [] if isinstance(j, dict)],
                "bids": (p.get("bid_stats") or {}).get("bid_count"),
            })
        time.sleep(1.5)
    return out


# ---------------------------------------------------------------- RemoteOK (link back required)
def remoteok():
    d = get("https://remoteok.com/api")
    out = []
    for j in d if isinstance(d, list) else []:
        if not isinstance(j, dict) or not j.get("id") or not j.get("position"):
            continue   # first item is the legal notice
        out.append({
            "id": f"remoteok:{j['id']}", "source": "RemoteOK", "title": j.get("position", ""),
            "url": j.get("url") or j.get("apply_url"), "company": j.get("company"),
            "desc": strip_html(j.get("description")), "posted": to_epoch(j.get("epoch") or j.get("date")),
            "pay_type": "salary" if num(j.get("salary_min")) else "unknown",
            "budget_min": num(j.get("salary_min")), "budget_max": num(j.get("salary_max")), "currency": "USD",
            "location": j.get("location") or "", "restrictions": [],
            "work_type": work_type_of(" ".join(j.get("tags") or []), j.get("position")),
            "tags": j.get("tags") or [], "bids": None,
        })
    return out


# ---------------------------------------------------------------- Himalayas
def himalayas(pages=5):
    out, cursor = [], None
    for _ in range(pages):
        params = {"limit": 20}
        if cursor:
            params["cursor"] = cursor
        d = get("https://himalayas.app/jobs/api", params=params)
        jobs = d.get("jobs") or []
        for j in jobs:
            period = str(j.get("salaryPeriod") or "").lower()
            out.append({
                "id": f"himalayas:{j.get('guid') or j.get('applicationLink')}", "source": "Himalayas",
                "title": j.get("title", ""), "url": j.get("applicationLink") or j.get("guid"),
                "company": j.get("companyName"), "desc": strip_html(j.get("description") or j.get("excerpt")),
                "posted": to_epoch(j.get("pubDate")),
                "pay_type": "hourly" if "hour" in period else ("salary" if num(j.get("minSalary")) else "unknown"),
                "budget_min": num(j.get("minSalary")), "budget_max": num(j.get("maxSalary")),
                "currency": j.get("currency") or "USD", "location": ", ".join(j.get("locationRestrictions") or []) or "Worldwide",
                "restrictions": j.get("locationRestrictions") or [],
                "work_type": work_type_of(j.get("employmentType")), "tags": (j.get("categories") or [])[:8], "bids": None,
            })
        nxt = d.get("nextCursor")
        if not nxt or nxt == cursor or not jobs:
            break
        cursor = nxt
        time.sleep(1)
    return out


# ---------------------------------------------------------------- Jobicy (credit + direct links required)
def jobicy():
    d = get("https://jobicy.com/api/v2/remote-jobs", params={"count": 100})
    out = []
    for j in d.get("jobs") or []:
        period = str(j.get("salaryPeriod") or "").lower()
        out.append({
            "id": f"jobicy:{j.get('id')}", "source": "Jobicy", "title": html.unescape(j.get("jobTitle", "")),
            "url": j.get("url"), "company": j.get("companyName"),
            "desc": strip_html(j.get("jobDescription") or j.get("jobExcerpt")), "posted": to_epoch(j.get("pubDate")),
            "pay_type": "hourly" if "hour" in period else ("salary" if num(j.get("salaryMin")) else "unknown"),
            "budget_min": num(j.get("salaryMin")), "budget_max": num(j.get("salaryMax")),
            "currency": j.get("salaryCurrency") or "USD", "location": j.get("jobGeo") or "",
            "restrictions": [], "work_type": work_type_of(" ".join(j.get("jobType") or []) if isinstance(j.get("jobType"), list) else j.get("jobType")),
            "tags": j.get("jobIndustry") if isinstance(j.get("jobIndustry"), list) else [], "bids": None,
        })
    return out


# ---------------------------------------------------------------- Remotive (asks for <= 4 calls/day)
def remotive():
    d = get("https://remotive.com/api/remote-jobs", params={"limit": 200})
    out = []
    for j in d.get("jobs") or []:
        out.append({
            "id": f"remotive:{j.get('id')}", "source": "Remotive", "title": j.get("title", ""), "url": j.get("url"),
            "company": j.get("company_name"), "desc": strip_html(j.get("description")),
            "posted": to_epoch(j.get("publication_date")), "pay_type": "unknown", "budget_min": None,
            "budget_max": None, "currency": "USD", "salary_text": j.get("salary"),
            "location": j.get("candidate_required_location") or "", "restrictions": [],
            "work_type": work_type_of(j.get("job_type")), "tags": (j.get("tags") or [])[:8] + [j.get("category") or ""],
            "bids": None,
        })
    return out


# ---------------------------------------------------------------- We Work Remotely (RSS)
def weworkremotely():
    xml = get("https://weworkremotely.com/remote-jobs.rss", as_json=False)
    root = ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    out = []
    for it in root.iter("item"):
        g = lambda tag: (it.findtext(tag) or "").strip()
        title = g("title")
        company, _, role = title.partition(":")
        out.append({
            "id": f"wwr:{g('guid') or g('link')}", "source": "We Work Remotely", "title": (role or title).strip(),
            "url": g("link"), "company": company.strip() if role else None, "desc": strip_html(g("description")),
            "posted": to_epoch(g("pubDate")), "pay_type": "unknown", "budget_min": None, "budget_max": None,
            "currency": "USD", "location": g("region") or "", "restrictions": [],
            "work_type": work_type_of(g("type")), "tags": [g("category")] if g("category") else [], "bids": None,
        })
    return out


# ---------------------------------------------------------------- Working Nomads (remote jobs, public JSON)
def working_nomads():
    d = get("https://www.workingnomads.com/api/exposed_jobs/")
    out = []
    for j in d if isinstance(d, list) else []:
        if not isinstance(j, dict) or not j.get("url") or not j.get("title"):
            continue
        tags = j.get("tags") if isinstance(j.get("tags"), list) else [t.strip() for t in str(j.get("tags") or "").split(",") if t.strip()]
        out.append({
            "id": f"wn:{j['url']}", "source": "Working Nomads", "title": strip_html(j["title"], 160), "url": j["url"],
            "company": j.get("company_name"), "desc": strip_html(j.get("description")), "posted": to_epoch(j.get("pub_date")),
            "pay_type": "unknown", "budget_min": None, "budget_max": None, "currency": None,
            "location": j.get("location") or "", "restrictions": [],
            "work_type": work_type_of(j.get("title"), " ".join(tags)), "tags": tags[:8] + [j.get("category_name") or ""],
            "bids": None,
        })
    return out


# ---------------------------------------------------------------- remote-first companies' own job boards
def _in_reach(loc):
    """Location open to someone in India: India, APAC/Asia, or worldwide."""
    return bool(re.search(r"india|bengaluru|bangalore|mumbai|pune|hyderabad|gurugram|gurgaon|noida|delhi|chennai|"
                          r"apac|asia|worldwide|anywhere|global", str(loc or ""), re.I))


def remote_companies(companies):
    out, errors = [], []
    for c in companies:
        try:
            if c["ats"] == "greenhouse":
                d = get(f"https://boards-api.greenhouse.io/v1/boards/{c['slug']}/jobs")
                jobs = [(j.get("id"), j.get("title"), j.get("absolute_url"), (j.get("location") or {}).get("name"),
                         j.get("updated_at") or j.get("first_published"), "") for j in d.get("jobs") or []]
            elif c["ats"] == "lever":
                d = get(f"https://api.lever.co/v0/postings/{c['slug']}", params={"mode": "json"})
                jobs = [(j.get("id"), j.get("text"), j.get("hostedUrl"),
                         "; ".join(filter(None, [(j.get("categories") or {}).get("location"), j.get("workplaceType")])),
                         j.get("createdAt"), (j.get("categories") or {}).get("commitment") or "") for j in d or []]
            else:
                d = get(f"https://api.ashbyhq.com/posting-api/job-board/{c['slug']}")
                jobs = [(j.get("id"), j.get("title"), j.get("jobUrl"),
                         "; ".join(filter(None, [j.get("location")] + [x.get("location") for x in j.get("secondaryLocations") or []
                                                                     if isinstance(x, dict)])),
                         j.get("publishedAt"), j.get("employmentType") or "") for j in d.get("jobs") or []]
        except Exception as e:
            errors.append(f"{c['name']}: {str(e)[:60]}")
            continue
        for jid, title, url, loc, when, kind in jobs:
            if not (jid and title and url) or not _in_reach(loc):
                continue
            remote = bool(re.search(r"remote|home based|anywhere|worldwide|global", str(loc), re.I))
            out.append({
                "id": f"rc:{c['slug']}:{jid}", "source": "Remote-first companies", "title": title, "url": url,
                "company": c["name"], "desc": "", "posted": to_epoch(when), "pay_type": "unknown",
                "budget_min": None, "budget_max": None, "currency": None, "location": loc,
                "restrictions": [], "work_type": work_type_of(title, kind) if work_type_of(title, kind) != "unknown" else "full-time",
                "tags": ["remote" if remote else "India office", c["name"]], "bids": None, "official": True,
                "company_size": c.get("size"),
            })
    if errors and not out:
        raise RuntimeError("; ".join(errors[:3]))
    return out


# ---------------------------------------------------------------- Hacker News monthly "Who is hiring?" (remote, open to India)
def hn_hiring(limit=400):
    d = get("https://hn.algolia.com/api/v1/search_by_date",
            params={"tags": "story,author_whoishiring", "query": "who is hiring", "hitsPerPage": 5})
    story = next((h for h in d.get("hits", []) if (h.get("title") or "").lower().startswith("ask hn: who is hiring")), None)
    if not story:
        return []
    item = get(f"https://hn.algolia.com/api/v1/items/{story['objectID']}")
    out = []
    for c in (item.get("children") or [])[:limit]:
        text = strip_html(c.get("text"), 2500)
        first = text.split("\n")[0]
        if "|" not in first or not re.search(r"\bremote\b", first, re.I):
            continue
        if not re.search(r"worldwide|anywhere|global|india|apac|asia|any time ?zone", text[:800], re.I):
            continue          # 'REMOTE (US)' etc. is not open to India
        parts = [p.strip() for p in first.split("|") if p.strip()]
        role = next((p for p in parts[1:] if re.search(r"engineer|developer|scientist|analyst|intern|ml|ai|data|"
                                                        r"designer|writer|marketing|research", p, re.I)), parts[1] if len(parts) > 1 else first)
        out.append({
            "id": f"hnhire:{c.get('id')}", "source": "HN Who is hiring", "title": role[:140], "company": parts[0][:80],
            "url": f"https://news.ycombinator.com/item?id={c.get('id')}", "desc": text,
            "posted": to_epoch(c.get("created_at_i") or c.get("created_at")), "pay_type": "unknown",
            "budget_min": None, "budget_max": None, "currency": None, "location": first[:200], "restrictions": [],
            "work_type": work_type_of(first) if work_type_of(first) != "unknown" else "full-time", "tags": [], "bids": None,
        })
    return out


# ---------------------------------------------------------------- Hacker News monthly "Freelancer? Seeking freelancer?"
def hn_freelancer():
    d = get("https://hn.algolia.com/api/v1/search_by_date",
            params={"tags": "story,author_whoishiring", "query": "freelancer", "hitsPerPage": 5})
    story = next((h for h in d.get("hits", []) if "freelancer" in (h.get("title") or "").lower()), None)
    if not story:
        return []
    item = get(f"https://hn.algolia.com/api/v1/items/{story['objectID']}")
    out = []
    for c in item.get("children") or []:
        text = strip_html(c.get("text"), 2000)
        if not re.match(r"\s*seeking\s+freelancer", text, re.I):
            continue
        first = text.split("\n")[0]
        title = re.sub(r"^\s*seeking\s+freelancer\s*[|:\-–]*\s*", "", first, flags=re.I)[:140] or "Seeking freelancer"
        out.append({
            "id": f"hn:{c.get('id')}", "source": "Hacker News", "title": title,
            "url": f"https://news.ycombinator.com/item?id={c.get('id')}", "company": None, "desc": text,
            "posted": to_epoch(c.get("created_at_i") or c.get("created_at")), "pay_type": "unknown",
            "budget_min": None, "budget_max": None, "currency": "USD", "location": first, "restrictions": [],
            "work_type": "freelance", "tags": [], "bids": None,
        })
    return out
