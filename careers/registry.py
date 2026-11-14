"""Companies whose OWN careers sites Career Hub reads, in priority order: FAANG+ → big tech → India majors.
(Startups come from the job finder, startup job sites and remote boards.)

tier:   "FAANG+" | "Big tech" | "India major"
ats:    connector in careers/sources.py, or "link" = official search link only (not collected automatically:
        the site forbids it in robots.txt or needs a login)
status: filled in by careers/probe.py runs on GitHub's servers — only "ok" entries are collected.
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
    {"name": "Adobe (university)", "tier": BIG, "ats": "workday", "tenant": "adobe", "wd": "wd5", "site": "external_university"},
    {"name": "Intel", "tier": BIG, "ats": "workday", "tenant": "intel", "wd": "wd1", "site": "External"},
    {"name": "Qualcomm", "tier": BIG, "ats": "workday", "tenant": "qualcomm", "wd": "wd5", "site": "External"},
    {"name": "Micron", "tier": BIG, "ats": "workday", "tenant": "micron", "wd": "wd1", "site": "External"},
    {"name": "Dell", "tier": BIG, "ats": "workday", "tenant": "dell", "wd": "wd1", "site": "External"},
    {"name": "HP", "tier": BIG, "ats": "workday", "tenant": "hp", "wd": "wd5", "site": "ExternalCareerSite"},
    {"name": "Walmart Global Tech", "tier": BIG, "ats": "workday", "tenant": "walmart", "wd": "wd5", "site": "WalmartExternal"},
    {"name": "Autodesk", "tier": BIG, "ats": "workday", "tenant": "autodesk", "wd": "wd1", "site": "Ext"},
    {"name": "Applied Materials", "tier": BIG, "ats": "workday", "tenant": "amat", "wd": "wd1", "site": "External"},
    {"name": "Analog Devices", "tier": BIG, "ats": "workday", "tenant": "analogdevices", "wd": "wd1", "site": "External"},
    {"name": "Cadence", "tier": BIG, "ats": "workday", "tenant": "cadence", "wd": "wd1", "site": "External_Careers"},
    {"name": "Workday", "tier": BIG, "ats": "workday", "tenant": "workday", "wd": "wd5", "site": "Workday"},
    {"name": "Nutanix", "tier": BIG, "ats": "workday", "tenant": "nutanix", "wd": "wd1", "site": "Nutanix"},
    {"name": "Bosch", "tier": BIG, "ats": "smartrecruiters", "slug": "BoschGroup"},
    {"name": "ServiceNow", "tier": BIG, "ats": "smartrecruiters", "slug": "ServiceNow"},
    # ---- Big tech (public job-board APIs)
    {"name": "Databricks", "tier": BIG, "ats": "greenhouse", "slug": "databricks"},
    {"name": "Rubrik", "tier": BIG, "ats": "greenhouse", "slug": "rubrik"},
    {"name": "Cloudflare", "tier": BIG, "ats": "greenhouse", "slug": "cloudflare"},
    {"name": "Airbnb", "tier": BIG, "ats": "greenhouse", "slug": "airbnb"},
    {"name": "Zscaler", "tier": BIG, "ats": "greenhouse", "slug": "zscaler"},
    {"name": "GitLab", "tier": BIG, "ats": "greenhouse", "slug": "gitlab"},
    {"name": "Elastic", "tier": BIG, "ats": "greenhouse", "slug": "elastic"},
    {"name": "MongoDB", "tier": BIG, "ats": "greenhouse", "slug": "mongodb"},
    {"name": "Datadog", "tier": BIG, "ats": "greenhouse", "slug": "datadog"},
    {"name": "Canonical", "tier": BIG, "ats": "greenhouse", "slug": "canonical"},
    {"name": "Atlassian", "tier": BIG, "ats": "lever", "slug": "atlassian"},
    # ---- India majors
    {"name": "Freshworks", "tier": INDIA, "ats": "smartrecruiters", "slug": "Freshworks"},
    {"name": "Swiggy", "tier": INDIA, "ats": "lever", "slug": "swiggy"},
    {"name": "Meesho", "tier": INDIA, "ats": "lever", "slug": "meesho"},
    {"name": "CRED", "tier": INDIA, "ats": "lever", "slug": "cred"},
    {"name": "InMobi", "tier": INDIA, "ats": "lever", "slug": "inmobi"},
    {"name": "ShareChat", "tier": INDIA, "ats": "lever", "slug": "sharechat"},
    {"name": "Postman", "tier": INDIA, "ats": "greenhouse", "slug": "postman"},
    {"name": "Sarvam AI", "tier": INDIA, "ats": "ashby", "slug": "sarvam"},
    {"name": "Flipkart", "tier": INDIA, "ats": "link", "search_url": "https://www.flipkartcareers.com/#!/joblist"},
    {"name": "TCS Research", "tier": INDIA, "ats": "link", "search_url": "https://ibegin.tcs.com/iBegin/jobs/search"},
    {"name": "Zoho", "tier": INDIA, "ats": "link", "search_url": "https://www.zoho.com/careers/jobs.html"},
]

TIER_RANK = {FAANG: 1, BIG: 2, INDIA: 3}
