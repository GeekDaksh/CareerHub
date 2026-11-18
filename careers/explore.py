"""One-off checks for NEW companies, run on GitHub's servers (python -m careers.explore).
Each check first reads the site's robots.txt; a site that disallows bots for the path we'd use is reported and
NOT fetched. Results come back as GitHub annotations (max 10 per step, so several checks share one notice)."""
import json
import re
import time
import urllib.robotparser
from urllib.parse import urlparse

from careers import sources as S
from gigs.sources import SESSION

UA = SESSION.headers.get("User-Agent", "*")
OUT = []


def robots_ok(url):
    p = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = SESSION.get(f"{p.scheme}://{p.netloc}/robots.txt", timeout=20)
        if r.status_code >= 400:
            return True, f"no robots.txt ({r.status_code})"
        rp.parse(r.text.splitlines())
        return rp.can_fetch(UA, url) and rp.can_fetch("*", url), "robots read"
    except Exception as e:
        return True, f"robots unreadable ({type(e).__name__})"


def check(name, url, fn):
    ok, why = robots_ok(url)
    if not ok:
        OUT.append(f"{name}: SKIPPED — robots.txt disallows {urlparse(url).path}")
        return
    t = time.time()
    try:
        OUT.append(f"{name}: {fn()} ({time.time() - t:.1f}s; {why})")
    except Exception as e:
        OUT.append(f"{name}: FAIL {type(e).__name__}: {str(e)[:160]} ({why})")


def wd(tenant, wdn, site):
    def f():
        c = {"name": tenant, "tenant": tenant, "wd": wdn, "site": site}
        jobs = S.workday(c, queries=["machine learning"], details=1)
        s = jobs[0] if jobs else {}
        return f"OK {len(jobs)} India jobs e.g. {s.get('title', '')[:45]} | {s.get('location', '')[:30]} | desc {len(s.get('desc', ''))}"
    return f


def sr(slug):
    def f():
        jobs = S.smartrecruiters({"name": slug, "slug": slug}, details=2)
        s = next((j for j in jobs if j.get("desc")), jobs[0] if jobs else {})
        return f"OK {len(jobs)} India jobs e.g. {s.get('title', '')[:45]} | desc {len(s.get('desc', ''))}"
    return f


def orc(host, site):
    """Oracle Recruiting Cloud public job search (used by JPMorgan, Oracle...)."""
    def f():
        url = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        d = S.get(url, params={"onlyData": "true", "expand": "requisitionList.secondaryLocations",
                               "finder": f'findReqs;siteNumber={site},limit=25,keyword="machine learning",sortBy=POSTING_DATES_DESC'})
        items = (d.get("items") or [{}])[0]
        reqs = items.get("requisitionList") or []
        india = [r for r in reqs if S.in_reach(f"{r.get('PrimaryLocation', '')} {r.get('PrimaryLocationCountry', '')}")]
        s = india[0] if india else (reqs[0] if reqs else {})
        return (f"OK {items.get('TotalJobsCount')} total, {len(india)}/{len(reqs)} India in first page e.g. "
                f"{s.get('Title', '')[:45]} | {s.get('PrimaryLocation', '')[:30]} | keys {sorted(s)[:8]}")
    return f


def apple():
    html = S.get("https://jobs.apple.com/en-in/search", params={"location": "india-INDC", "search": "machine learning"},
                 as_json=False)
    m = re.search(r"__staticRouterHydrationData\s*=\s*JSON\.parse\((\".*?\")\);", html, re.S)
    if not m:
        return f"page {len(html)} chars, no embedded data found; markers: {re.findall(r'(positionId|searchResults|totalRecords)', html)[:5]}"
    data = json.loads(json.loads(m.group(1)))
    txt = json.dumps(data)
    return (f"embedded data OK; positionId x{txt.count('positionId')}, totalRecords {re.findall(r'totalRecords.{0,12}', txt)[:1]}; "
            f"sample {re.findall(r'postingTitle.{0,70}', txt)[:2]}")


def microsoft_details():
    base = "https://apply.careers.microsoft.com"
    d = S.get(f"{base}/api/pcsx/search", params={"domain": "microsoft.com", "query": "machine learning", "location": "India",
                                                   "start": 0, "sort_by": "timestamp"})
    pos = (d.get("data") or {}).get("positions") or d.get("positions") or []
    if not pos:
        return "search gave 0 positions"
    pid = pos[0].get("id")
    out = [f"{len(pos)} positions; keys {sorted(pos[0])[:12]}"]
    for path in ("/api/pcsx/position_details", "/api/apply/v2/jobs/" + str(pid)):
        try:
            dd = S.get(base + path, params={"position_id": pid, "domain": "microsoft.com", "hl": "en"})
            body = json.dumps(dd)
            out.append(f"{path}: OK {len(body)} chars, has description: {'job_description' in body or 'jobDescription' in body}")
        except Exception as e:
            out.append(f"{path}: {type(e).__name__} {str(e)[:60]}")
    return " | ".join(out)


def pacing():
    """Do Workday 429s go away with ~1.5 s between requests?"""
    codes = []
    for i in range(12):
        r = SESSION.post("https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs",
                         json={"appliedFacets": {}, "limit": 20, "offset": 20 * (i % 3), "searchText": "machine learning India"},
                         headers={"Accept": "application/json"}, timeout=30)
        codes.append(r.status_code)
        if r.status_code == 429:
            codes.append(f"retry-after={r.headers.get('Retry-After')}")
        time.sleep(1.5)
    return f"12 requests 1.5 s apart → {codes}"


def robots_audit():
    """Exact robots verdict for every address the connectors use (RFC 9309: a 4xx robots.txt means allowed)."""
    urls = {"amazon": "https://www.amazon.jobs/en/search.json", "google": "https://www.google.com/about/careers/applications/jobs/results",
            "ms-apply": "https://apply.careers.microsoft.com/api/pcsx/search", "ms-gcs": "https://gcsservices.careers.microsoft.com/search/api/v1/search",
            "ms-jobs": "https://jobs.careers.microsoft.com/global/en/search",
            "sr-api": "https://api.smartrecruiters.com/v1/companies/BoschGroup/postings", "sr-jobs": "https://jobs.smartrecruiters.com/BoschGroup",
            "sr-careers": "https://careers.smartrecruiters.com/BoschGroup", "greenhouse": "https://boards-api.greenhouse.io/v1/boards/databricks/jobs",
            "lever": "https://api.lever.co/v0/postings/meesho", "ashby": "https://api.ashbyhq.com/posting-api/job-board/sarvam",
            "workday": "https://salesforce.wd12.myworkdayjobs.com/wday/cxs/salesforce/External_Career_Site/jobs",
            "apple": "https://jobs.apple.com/en-in/search", "orc": "https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"}
    out = []
    for k, u in urls.items():
        p = urlparse(u)
        try:
            r = SESSION.get(f"{p.scheme}://{p.netloc}/robots.txt", timeout=20)
            if r.status_code >= 500:
                out.append(f"{k}: robots {r.status_code} → treat as disallowed")
                continue
            if r.status_code >= 400:
                out.append(f"{k}: robots {r.status_code} → allowed (RFC 9309)")
                continue
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(r.text.splitlines())
            dis = [l.strip() for l in r.text.splitlines() if l.lower().startswith("disallow")][:4]
            out.append(f"{k}: {'ALLOWED' if rp.can_fetch(UA, u) and rp.can_fetch('*', u) else 'DISALLOWED'} {dis}")
        except Exception as e:
            out.append(f"{k}: robots unreachable {type(e).__name__}")
    return " ;; ".join(out)


def apple_shape():
    html = S.get("https://jobs.apple.com/en-in/search", params={"location": "india-INDC", "search": "machine learning"}, as_json=False)
    m = re.search(r"__staticRouterHydrationData\s*=\s*JSON\.parse\((\".*?\")\);", html, re.S)
    data = json.loads(json.loads(m.group(1)))
    found = []

    def walk(x):
        if isinstance(x, dict):
            if "positionId" in x and "postingTitle" in x:
                found.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(data)
    s = found[0] if found else {}
    return f"{len(found)} items; item: " + json.dumps({k: (str(v)[:70]) for k, v in s.items()})[:1400]


def orc_shape():
    url = "https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    d = S.get(url, params={"onlyData": "true", "expand": "requisitionList.secondaryLocations",
                           "finder": 'findReqs;siteNumber=CX_1001,limit=5,keyword="machine learning",sortBy=POSTING_DATES_DESC'})
    s = ((d.get("items") or [{}])[0].get("requisitionList") or [{}])[0]
    return "item: " + json.dumps({k: (str(v)[:60]) for k, v in s.items()})[:1400]


def main():
    if len(__import__("sys").argv) > 1 and __import__("sys").argv[1] == "2":
        for name, fn in [("robots", robots_audit), ("apple shape", apple_shape), ("orc shape", orc_shape)]:
            try:
                print(f"::notice title={name}::{fn()}")
            except Exception as e:
                print(f"::notice title={name}::FAIL {type(e).__name__} {str(e)[:200]}")
        return
    check("Apple", "https://jobs.apple.com/en-in/search?location=india-INDC", apple)
    check("Mastercard", "https://mastercard.wd1.myworkdayjobs.com/wday/cxs/mastercard/CorporateCareers/jobs",
          wd("mastercard", "wd1", "CorporateCareers"))
    check("Visa", "https://api.smartrecruiters.com/v1/companies/Visa/postings", sr("Visa"))
    check("PayPal", "https://paypal.wd1.myworkdayjobs.com/wday/cxs/paypal/jobs/jobs", wd("paypal", "wd1", "jobs"))
    check("Citi", "https://citi.wd5.myworkdayjobs.com/wday/cxs/citi/2/jobs", wd("citi", "wd5", "2"))
    check("Fidelity", "https://fmr.wd1.myworkdayjobs.com/wday/cxs/fmr/FidelityCareers/jobs", wd("fmr", "wd1", "FidelityCareers"))
    check("BlackRock", "https://blackrock.wd1.myworkdayjobs.com/wday/cxs/blackrock/BlackRock_Professional/jobs",
          wd("blackrock", "wd1", "BlackRock_Professional"))
    check("Morgan Stanley", "https://ms.wd5.myworkdayjobs.com/wday/cxs/ms/External/jobs", wd("ms", "wd5", "External"))
    check("Deutsche Bank", "https://db.wd3.myworkdayjobs.com/wday/cxs/db/DBWebSite/jobs", wd("db", "wd3", "DBWebSite"))
    check("American Express", "https://aexp.wd5.myworkdayjobs.com/wday/cxs/aexp/AmexCareers/jobs", wd("aexp", "wd5", "AmexCareers"))
    check("JPMorgan", "https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions", orc("jpmc.fa.oraclecloud.com", "CX_1001"))
    check("Oracle", "https://eeho.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions", orc("eeho.fa.us2.oraclecloud.com", "CX_45001"))
    check("Microsoft details", "https://apply.careers.microsoft.com/api/pcsx/search", microsoft_details)
    check("Workday pacing", "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs", pacing)
    for i in range(0, len(OUT), 2):
        print(f"::notice title=explore {i // 2 + 1}::" + " || ".join(OUT[i:i + 2]))
    print("\n".join(OUT))


if __name__ == "__main__":
    main()
