"""Connectors for companies' OWN careers sites (the official source of each vacancy).

Each connector returns jobs in one shape:
  {id, company, title, url, location, posted, desc, kind_hint, official: True, ats}
Only India / India-remote / APAC / worldwide-remote jobs are kept (Daksh applies from India).
Every request has a time and size limit (gigs.sources.get / post_json), and one company failing never
stops the others.

Supported:
  amazon       amazon.jobs search.json (public JSON)
  google       google.com/about/careers results page (data embedded in the page)
  eightfold    Eightfold "PCS" search used by Microsoft's careers site
  workday      {tenant}.wd{n}.myworkdayjobs.com cxs API (NVIDIA, Salesforce, Adobe, Intel, Qualcomm...)
  greenhouse / lever / ashby / smartrecruiters   public job-board APIs
Companies whose sites can't be read politely (robots.txt disallows, or login-only) get an official search
link in the app instead — never scraped.
"""
import html
import json
import re
import time
from gigs.sources import MAX_BYTES, MAX_SECONDS, SESSION, get, strip_html, to_epoch

INDIA = re.compile(r"\b(india|bengaluru|bangalore|hyderabad|pune|mumbai|gurugram|gurgaon|noida|delhi|chennai|"
                   r"kolkata|ahmedabad|kochi|jaipur|indore|chandigarh|thiruvananthapuram|coimbatore|ind)\b", re.I)
REMOTE_OPEN = re.compile(r"\b(apac|asia|worldwide|anywhere|global)\b", re.I)
QUERIES = ["machine learning", "artificial intelligence", "data scientist", "computer vision", "generative ai",
           "research", "intern", "graduate", "software engineer"]


def in_reach(loc):
    """Location open to someone in India."""
    return bool(INDIA.search(str(loc or "")) or (REMOTE_OPEN.search(str(loc or ""))
                                                 and re.search(r"remote", str(loc or ""), re.I)))


def post_json(url, body, headers=None, timeout=30):
    """POST with the same whole-request time and size limits as get()."""
    start = time.time()
    h = {"Content-Type": "application/json", "Accept": "application/json", "Accept-Language": "en-US"}
    h.update(headers or {})
    with SESSION.post(url, data=json.dumps(body), headers=h, timeout=timeout, stream=True) as r:
        r.raise_for_status()
        buf = bytearray()
        r.raw.decode_content = True
        while True:
            chunk = r.raw.read1(65536) if hasattr(r.raw, "read1") else r.raw.read(65536)
            if not chunk:
                break
            buf += chunk
            if len(buf) > MAX_BYTES or time.time() - start > MAX_SECONDS:
                raise RuntimeError("response too big or too slow")
    return json.loads(bytes(buf).decode("utf-8", "replace"))


def _job(company, jid, title, url, loc, posted, desc="", kind="", ats="", extra=None):
    j = {"id": f"off:{company.lower().replace(' ', '')}:{jid}", "company": company, "title": strip_html(title, 200),
         "url": url, "location": strip_html(loc, 200), "posted": to_epoch(posted), "desc": strip_html(desc, 6000),
         "kind_hint": kind, "official": True, "ats": ats}
    j.update(extra or {})
    return j


# ---------------------------------------------------------------- Amazon
def amazon(c, queries=QUERIES, pages=2):
    out = {}
    for q in queries:
        for p in range(pages):
            d = get("https://www.amazon.jobs/en/search.json", params={
                "base_query": q, "loc_query": "India", "country": "IND", "result_limit": 50, "offset": p * 50,
                "sort": "recent"})
            jobs = d.get("jobs") or []
            for x in jobs:
                if str(x.get("country_code", "")).upper() not in ("IND", "IN") and not in_reach(x.get("location")):
                    continue
                desc = " ".join(filter(None, [x.get("description"), "Basic qualifications: " + str(x.get("basic_qualifications") or ""),
                                              "Preferred qualifications: " + str(x.get("preferred_qualifications") or "")]))
                kind = "internship" if x.get("is_intern") else ("graduate" if x.get("university_job") else "")
                out[x["id"]] = _job(c["name"], x["id"], x.get("title"), "https://www.amazon.jobs" + str(x.get("job_path") or ""),
                                    x.get("normalized_location") or x.get("location"), x.get("posted_date"), desc, kind,
                                    "amazon.jobs", {"team": x.get("job_category")})
            if len(jobs) < 50:
                break
    return list(out.values())


# ---------------------------------------------------------------- Google (data embedded in the results page)
def _google_rows(html):
    m = re.search(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(\[.*?\]), sideChannel", html, re.S)
    if not m:
        raise RuntimeError("Google careers page layout changed (ds:1 block not found)")
    data = json.loads(m.group(1))
    return data[0] if data and isinstance(data[0], list) else []


def google(c, queries=QUERIES[:6], pages=2):
    out = {}
    for q in queries:
        for p in range(1, pages + 1):
            html = get("https://www.google.com/about/careers/applications/jobs/results",
                       params={"q": q, "location": "India", "page": p}, as_json=False)
            rows = _google_rows(html)
            for r in rows:
                try:
                    jid, title = r[0], r[1]
                    locs = "; ".join(x[0] for x in (r[9] or []) if x)
                    desc = " ".join(strip_html(x[1] if isinstance(x, list) else x, 3000) for x in (r[3], r[4], r[10]) if x)
                    posted = (r[12] or [None])[0] if isinstance(r[12], list) else None
                except (IndexError, TypeError):
                    continue
                if not in_reach(locs):
                    continue
                url = f"https://www.google.com/about/careers/applications/jobs/results/{jid}"
                out[jid] = _job(c["name"], jid, title, url, locs, posted, desc, "", "google careers")
            if len(rows) < 20:
                break
    return list(out.values())


# ---------------------------------------------------------------- Eightfold (Microsoft)
def eightfold(c, queries=QUERIES[:6]):
    out = {}
    base, domain = c["base"], c["domain"]
    for q in queries:
        d = get(f"{base}/api/pcsx/search", params={"domain": domain, "query": q, "location": "India", "start": 0,
                                                   "sort_by": "timestamp"})
        jobs = (d.get("data") or {}).get("positions") or d.get("positions") or []
        for x in jobs:
            locs = "; ".join(x.get("locations") or [x.get("location") or ""])
            if not in_reach(locs):
                continue
            url = x.get("positionUrl") or x.get("canonicalPositionUrl") or f"{base}/careers/job/{x.get('id')}"
            if url.startswith("/"):
                url = base + url
            out[x.get("id")] = _job(c["name"], x.get("id"), x.get("name") or x.get("title"), url, locs,
                                    x.get("postedTs") or x.get("t_create"), x.get("job_description") or "", "", "eightfold")
    return list(out.values())


# ---------------------------------------------------------------- Workday
def workday(c, queries=QUERIES, details=8):
    tenant, wd, site = c["tenant"], c["wd"], c["site"]
    host = f"https://{tenant}.{wd}.myworkdayjobs.com"
    api = f"{host}/wday/cxs/{tenant}/{site}"
    out = {}
    for q in queries:
        for offset in (0, 20):
            d = post_json(f"{api}/jobs", {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": f"{q} India"})
            posts = d.get("jobPostings") or []
            for x in posts:
                if not in_reach(x.get("locationsText")) and "Locations" not in str(x.get("locationsText")):
                    continue
                path = x.get("externalPath") or ""
                out[path] = {"path": path, "title": x.get("title"), "loc": x.get("locationsText") or ""}
            if len(posts) < 20:
                break
    jobs = []
    for i, x in enumerate(out.values()):
        desc, loc, posted = "", x["loc"], None
        if i < details * 6 and x["path"] not in c.get("_known", ()):   # details: capped, and only for new jobs
            try:
                dd = get(f"{api}{x['path']}").get("jobPostingInfo") or {}
                desc = dd.get("jobDescription") or ""
                loc = "; ".join(filter(None, [dd.get("location")] + list(dd.get("additionalLocations") or []))) or loc
                posted = dd.get("startDate")
            except Exception:
                pass
        if not in_reach(loc):
            continue
        jobs.append(_job(c["name"], x["path"].rsplit("_", 1)[-1] or x["path"], x["title"], f"{host}/{site}{x['path']}",
                         loc, posted, desc, "", "workday", {"src_key": x["path"]}))
    return jobs


# ---------------------------------------------------------------- public job-board APIs
def greenhouse(c):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{c['slug']}/jobs", params={"content": "true"})
    return [_job(c["name"], j["id"], j.get("title"), j.get("absolute_url"), (j.get("location") or {}).get("name"),
                 j.get("updated_at"), html.unescape(j.get("content") or ""),
                 "", "greenhouse")
            for j in d.get("jobs") or [] if in_reach((j.get("location") or {}).get("name"))]


def lever(c):
    d = get(f"https://api.lever.co/v0/postings/{c['slug']}", params={"mode": "json"})
    return [_job(c["name"], j["id"], j.get("text"), j.get("hostedUrl"),
                 "; ".join(filter(None, [(j.get("categories") or {}).get("location"), j.get("workplaceType")])),
                 j.get("createdAt"), j.get("descriptionPlain") or "", (j.get("categories") or {}).get("commitment") or "", "lever")
            for j in d or [] if in_reach((j.get("categories") or {}).get("location"))]


def ashby(c):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{c['slug']}")
    out = []
    for j in d.get("jobs") or []:
        loc = "; ".join(filter(None, [j.get("location")] + [x.get("location") for x in j.get("secondaryLocations") or []
                                                            if isinstance(x, dict)]))
        if in_reach(loc):
            out.append(_job(c["name"], j["id"], j.get("title"), j.get("jobUrl"), loc, j.get("publishedAt"),
                            j.get("descriptionPlain") or "", j.get("employmentType") or "", "ashby"))
    return out


SR_TECH = re.compile(r"engineer|developer|scientist|data|machine|\bml\b|\bai\b|intern|graduate|trainee|research|"
                     r"software|vision|analyst|architect", re.I)


def smartrecruiters(c, details=40):
    """List API has no description, so fetch it (one request each) for new technical-looking jobs, capped."""
    api = f"https://api.smartrecruiters.com/v1/companies/{c['slug']}/postings"
    out, offset = [], 0
    while offset < 300:
        d = get(api, params={"country": "in", "limit": 100, "offset": offset})
        page = d.get("content") or []
        out += page
        if len(page) < 100:
            break
        offset += 100
    jobs, fetched = [], 0
    for j in out:
        loc = j.get("location") or {}
        locs = ", ".join(filter(None, [loc.get("city"), loc.get("region"), loc.get("country")]))
        if not in_reach(locs):
            continue
        desc = ""
        jid = f"off:{c['name'].lower().replace(' ', '')}:{j['id']}"
        if fetched < details and jid not in c.get("_known", ()) and SR_TECH.search(j.get("name") or ""):
            fetched += 1
            try:
                ad = (get(f"{api}/{j['id']}").get("jobAd") or {}).get("sections") or {}
                desc = " ".join(f"{(v or {}).get('title', '')}: {(v or {}).get('text', '')}" for v in ad.values())
            except Exception:
                pass
        jobs.append(_job(c["name"], j["id"], j.get("name"), f"https://jobs.smartrecruiters.com/{c['slug']}/{j['id']}", locs,
                         j.get("releasedDate"), desc, (j.get("typeOfEmployment") or {}).get("label", ""), "smartrecruiters"))
    return jobs


CONNECTORS = {"amazon": amazon, "google": google, "eightfold": eightfold, "workday": workday,
              "greenhouse": greenhouse, "lever": lever, "ashby": ashby, "smartrecruiters": smartrecruiters}


def search_link(c):
    """Official careers search link for companies we don't collect automatically."""
    return c.get("search_url", "")


def collect(companies, health, now=None, budget_s=420, known=None):
    """Run every company's connector. One failing company never stops the others; the whole step has a budget.
    known = {company: set of job ids/paths already stored} so details are fetched only for new jobs."""
    now, t0, out = now or time.time(), time.time(), []
    for c in companies:
        fn = CONNECTORS.get(c.get("ats"))
        if not fn:
            continue
        c = {**c, "_known": (known or {}).get(c["name"], set())}
        if time.time() - t0 > budget_s:
            health[c["name"]] = {"ok": False, "count": 0, "at": now, "error": "skipped: time budget used, next run"}
            continue
        s = time.time()
        try:
            got = fn(c)
            for j in got:
                j.update(company_tier=c["tier"], company_rank=c.get("rank", 99))
            out += got
            health[c["name"]] = {"ok": True, "count": len(got), "at": now, "secs": round(time.time() - s, 1)}
        except Exception as e:
            health[c["name"]] = {"ok": False, "count": 0, "at": now, "error": str(e)[:200]}
    return out
