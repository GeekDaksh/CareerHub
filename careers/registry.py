"""Companies whose OWN careers sites Career Hub reads, in priority order: FAANG+ → big tech → India majors.
(Startups come from the job finder, startup job sites and remote boards.)

tier:   "FAANG+" | "Big tech" | "India major"
ats:    connector in careers/sources.py, or "link" = official search link only (not collected automatically:
        the site forbids it in robots.txt or needs a login)
Verified 2026-11-15 by careers/probe.py on GitHub's servers (run 43635231183): every automatic entry below
answered with India jobs (Canonical and Cloudflare answered with 0). Failed boards were moved to "link".
"""
FAANG = "FAANG+"
BIG = "Big tech"
INDIA = "India major"

CANDIDATES = [
    # ---- FAANG+
    {"name": "Google", "tier": FAANG, "ats": "google"},
    {"name": "Amazon", "tier": FAANG, "ats": "amazon"},
    {"name": "Microsoft", "tier": FAANG, "ats": "eightfold", "base": "https://apply.careers.microsoft.com", "domain": "microsoft.com"},
    {"name": "Apple", "tier": FAANG, "ats": "link", "search_url": "https://jobs.apple.com/en-in/search?location=india-INDC"},
    {"name": "Meta", "tier": FAANG, "ats": "link", "search_url": "https://www.metacareers.com/jobs"},
    {"name": "Netflix", "tier": FAANG, "ats": "link", "search_url": "https://explore.jobs.netflix.net/careers"},
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
    {"name": "Bosch", "tier": BIG, "ats": "smartrecruiters", "slug": "BoschGroup"},
    {"name": "ServiceNow", "tier": BIG, "ats": "smartrecruiters", "slug": "ServiceNow"},
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
    # ---- India majors
    {"name": "Freshworks", "tier": INDIA, "ats": "smartrecruiters", "slug": "Freshworks"},
    {"name": "Swiggy", "tier": INDIA, "ats": "link", "search_url": "https://careers.swiggy.com/"},
    {"name": "Meesho", "tier": INDIA, "ats": "lever", "slug": "meesho"},
    {"name": "CRED", "tier": INDIA, "ats": "lever", "slug": "cred"},
    {"name": "Sarvam AI", "tier": INDIA, "ats": "ashby", "slug": "sarvam"},
    {"name": "Flipkart", "tier": INDIA, "ats": "link", "search_url": "https://www.flipkartcareers.com/#!/joblist"},
    {"name": "TCS Research", "tier": INDIA, "ats": "link", "search_url": "https://ibegin.tcs.com/iBegin/jobs/search"},
    {"name": "Zoho", "tier": INDIA, "ats": "link", "search_url": "https://www.zoho.com/careers/jobs.html"},
]

TIER_RANK = {FAANG: 1, BIG: 2, INDIA: 3}

for _i, _c in enumerate(CANDIDATES):       # rank = order above (FAANG+ first)
    _c.setdefault("rank", _i)
