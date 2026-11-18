"""Companies whose OWN careers sites Career Hub reads, in priority order: FAANG+ → big tech → finance & payments →
India majors.
(Startups come from the job finder, startup job sites and remote boards.)

tier:   "FAANG+" | "Big tech" | "Finance & payments" | "India major"
ats:    connector in careers/sources.py, or "link" = official search link only (not collected automatically:
        the site forbids it in robots.txt or needs a login)
Verified 2026-11-15 by careers/probe.py on GitHub's servers (run 43635231183): every automatic entry below
answered with India jobs (Canonical and Cloudflare answered with 0). Failed boards were moved to "link".
2026-11-18 (explore runs 44301457575 + robots audit, read the standard RFC 9309 way — longest rule wins):
Microsoft allows /api/pcsx (kept). Google disallows its search-results pages → link only. SmartRecruiters' API
disallows all bots except LinkedIn's → Bosch, ServiceNow, Freshworks, Visa are links only. Meta (robots notice: written permission needed), Goldman Sachs and Netflix
(robots disallow) stay links. Added: Apple (its search page carries the data; no robots.txt), JPMorgan and Oracle
(Oracle Recruiting Cloud), Mastercard, Citi, Morgan Stanley, Deutsche Bank, PayPal, Fidelity (Workday).
Every run also re-checks robots.txt for each company (sources.robots_allowed), so a rule change is obeyed at once.
"""
FAANG = "FAANG+"
BIG = "Big tech"
FIN = "Finance & payments"
INDIA = "India major"

CANDIDATES = [
    # ---- FAANG+
    {"name": "Google", "tier": FAANG, "ats": "link",
     "search_url": "https://www.google.com/about/careers/applications/jobs/results?location=India&target_level=EARLY&target_level=INTERN_AND_APPRENTICE",
     "why": "robots.txt disallows reading its search results (single job pages only)"},
    {"name": "Amazon", "tier": FAANG, "ats": "amazon"},
    {"name": "Apple", "tier": FAANG, "ats": "apple", "domains": ["apple.com"]},
    {"name": "Microsoft", "tier": FAANG, "ats": "eightfold", "base": "https://apply.careers.microsoft.com", "domain": "microsoft.com",
     "domains": ["microsoft.com"]},
    {"name": "Meta", "tier": FAANG, "ats": "link", "search_url": "https://www.metacareers.com/jobs?offices[0]=Bangalore%2C%20India",
     "why": "needs Meta's written permission for automated collection"},
    {"name": "Netflix", "tier": FAANG, "ats": "link", "search_url": "https://explore.jobs.netflix.net/careers?location=India",
     "why": "robots.txt disallows bots"},
    # ---- Big tech (Workday career sites)
    {"name": "NVIDIA", "tier": BIG, "ats": "workday", "tenant": "nvidia", "wd": "wd5", "site": "NVIDIAExternalCareerSite"},
    {"name": "Salesforce", "tier": BIG, "ats": "workday", "tenant": "salesforce", "wd": "wd12", "site": "External_Career_Site"},
    {"name": "Adobe", "tier": BIG, "ats": "workday", "tenant": "adobe", "wd": "wd5", "site": "external_experienced"},
    {"name": "Intel", "tier": BIG, "ats": "workday", "tenant": "intel", "wd": "wd1", "site": "External"},
    {"name": "Qualcomm", "tier": BIG, "ats": "link", "search_url": "https://www.qualcomm.com/company/careers"},
    {"name": "Micron", "tier": BIG, "ats": "workday", "tenant": "micron", "wd": "wd1", "site": "External"},
    {"name": "Dell", "tier": BIG, "ats": "link", "search_url": "https://jobs.dell.com/en/search-jobs/India"},
    {"name": "HP", "tier": BIG, "ats": "workday", "tenant": "hp", "wd": "wd5", "site": "ExternalCareerSite"},
    {"name": "Walmart Global Tech", "tier": BIG, "ats": "link", "search_url": "https://careers.walmart.com/"},
    {"name": "Autodesk", "tier": BIG, "ats": "workday", "tenant": "autodesk", "wd": "wd1", "site": "Ext"},
    {"name": "Applied Materials", "tier": BIG, "ats": "workday", "tenant": "amat", "wd": "wd1", "site": "External"},
    {"name": "Analog Devices", "tier": BIG, "ats": "workday", "tenant": "analogdevices", "wd": "wd1", "site": "External"},
    {"name": "Cadence", "tier": BIG, "ats": "workday", "tenant": "cadence", "wd": "wd1", "site": "External_Careers"},
    {"name": "Workday", "tier": BIG, "ats": "workday", "tenant": "workday", "wd": "wd5", "site": "Workday"},
    {"name": "Nutanix", "tier": BIG, "ats": "link", "search_url": "https://careers.nutanix.com/"},
    {"name": "Oracle", "tier": BIG, "ats": "orc", "host": "eeho.fa.us2.oraclecloud.com", "site": "CX_45001",
     "domains": ["oracle.com"]},
    {"name": "Bosch", "tier": BIG, "ats": "link", "search_url": "https://careers.smartrecruiters.com/BoschGroup/india",
     "why": "SmartRecruiters' API disallows bots in robots.txt"},
    {"name": "ServiceNow", "tier": BIG, "ats": "link", "search_url": "https://careers.servicenow.com/jobs/?location=India",
     "why": "SmartRecruiters' API disallows bots in robots.txt"},
    # ---- Big tech (public job-board APIs)
    {"name": "Databricks", "tier": BIG, "ats": "greenhouse", "slug": "databricks", "domains": ["databricks.com"]},
    {"name": "Rubrik", "tier": BIG, "ats": "greenhouse", "slug": "rubrik", "domains": ["rubrik.com"]},
    {"name": "Cloudflare", "tier": BIG, "ats": "greenhouse", "slug": "cloudflare", "domains": ["cloudflare.com"]},
    {"name": "Airbnb", "tier": BIG, "ats": "greenhouse", "slug": "airbnb", "domains": ["airbnb.com"]},
    {"name": "Zscaler", "tier": BIG, "ats": "greenhouse", "slug": "zscaler", "domains": ["zscaler.com"]},
    {"name": "GitLab", "tier": BIG, "ats": "greenhouse", "slug": "gitlab", "domains": ["gitlab.com"]},
    {"name": "Elastic", "tier": BIG, "ats": "greenhouse", "slug": "elastic", "domains": ["elastic.co"]},
    {"name": "MongoDB", "tier": BIG, "ats": "greenhouse", "slug": "mongodb", "domains": ["mongodb.com"]},
    {"name": "Datadog", "tier": BIG, "ats": "greenhouse", "slug": "datadog", "domains": ["datadoghq.com"]},
    {"name": "Canonical", "tier": BIG, "ats": "greenhouse", "slug": "canonical", "domains": ["canonical.com"]},
    {"name": "Atlassian", "tier": BIG, "ats": "link", "search_url": "https://www.atlassian.com/company/careers/all-jobs"},
    # ---- Finance & payments
    {"name": "JPMorgan Chase", "tier": FIN, "ats": "orc", "host": "jpmc.fa.oraclecloud.com", "site": "CX_1001",
     "domains": ["jpmorganchase.com", "jpmorgan.com"]},
    {"name": "Goldman Sachs", "tier": FIN, "ats": "link", "search_url": "https://higher.gs.com/results?LOCATION=Bengaluru|Hyderabad",
     "why": "robots.txt disallows bots"},
    {"name": "Mastercard", "tier": FIN, "ats": "workday", "tenant": "mastercard", "wd": "wd1", "site": "CorporateCareers"},
    {"name": "Visa", "tier": FIN, "ats": "link", "search_url": "https://corporate.visa.com/en/jobs/?cities=Bangalore",
     "why": "its job host (SmartRecruiters API) disallows bots in robots.txt"},
    {"name": "Citi", "tier": FIN, "ats": "workday", "tenant": "citi", "wd": "wd5", "site": "2"},
    {"name": "Morgan Stanley", "tier": FIN, "ats": "workday", "tenant": "ms", "wd": "wd5", "site": "External"},
    {"name": "Deutsche Bank", "tier": FIN, "ats": "workday", "tenant": "db", "wd": "wd3", "site": "DBWebSite"},
    {"name": "PayPal", "tier": FIN, "ats": "workday", "tenant": "paypal", "wd": "wd1", "site": "jobs"},
    {"name": "Fidelity", "tier": FIN, "ats": "workday", "tenant": "fmr", "wd": "wd1", "site": "FidelityCareers"},
    {"name": "American Express", "tier": FIN, "ats": "link", "search_url": "https://www.americanexpress.com/en-us/careers/",
     "why": "its Workday address didn't answer (422)"},
    # ---- India majors
    {"name": "Freshworks", "tier": INDIA, "ats": "link", "search_url": "https://www.freshworks.com/company/careers/",
     "why": "SmartRecruiters' API disallows bots in robots.txt"},
    {"name": "Swiggy", "tier": INDIA, "ats": "link", "search_url": "https://careers.swiggy.com/"},
    {"name": "Meesho", "tier": INDIA, "ats": "lever", "slug": "meesho"},
    {"name": "CRED", "tier": INDIA, "ats": "lever", "slug": "cred"},
    {"name": "Sarvam AI", "tier": INDIA, "ats": "ashby", "slug": "sarvam"},
    {"name": "Flipkart", "tier": INDIA, "ats": "link", "search_url": "https://www.flipkartcareers.com/#!/joblist"},
    {"name": "TCS Research", "tier": INDIA, "ats": "link", "search_url": "https://ibegin.tcs.com/iBegin/jobs/search"},
    {"name": "Zoho", "tier": INDIA, "ats": "link", "search_url": "https://www.zoho.com/careers/jobs.html"},
]

STARTUP = "Startup"          # only for companies Daksh adds himself
TIER_RANK = {FAANG: 1, BIG: 2, FIN: 3, INDIA: 4, STARTUP: 5}
TIERS = [FAANG, BIG, FIN, INDIA, STARTUP]

for _i, _c in enumerate(CANDIDATES):       # rank = order above (FAANG+ first)
    _c.setdefault("rank", _i)
