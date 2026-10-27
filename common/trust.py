"""Scam shield. Every job and gig gets a verdict with plain reasons:
  verified   – official source (company careers page / ATS) or a known platform + company checks out
  likely     – known platform, nothing suspicious
  unverified – found via search or unknown source; check before applying
  risky      – scam signs → hidden from feeds, listed in the Safety tab with the reason
"""
import re
from urllib.parse import urlparse

# Official applicant-tracking systems companies use for their own careers pages
ATS_DOMAINS = {"greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "smartrecruiters.com", "myworkdayjobs.com",
               "keka.com", "darwinbox.in", "darwinbox.com", "zohorecruit.com", "zohorecruit.in", "freshteam.com",
               "teamtailor.com", "recruitee.com", "breezy.hr", "bamboohr.com", "icims.com", "successfactors.com",
               "taleo.net", "oraclecloud.com", "jobvite.com", "personio.de", "rippling.com", "pinpointhq.com"}
# Real job platforms (still check each post)
PLATFORM_DOMAINS = {"linkedin.com": "LinkedIn", "naukri.com": "Naukri", "internshala.com": "Internshala",
                    "wellfound.com": "Wellfound", "angel.co": "Wellfound", "instahyre.com": "Instahyre",
                    "cutshort.io": "Cutshort", "indeed.com": "Indeed", "foundit.in": "Foundit", "hirist.tech": "Hirist",
                    "hirist.com": "Hirist", "glassdoor.co.in": "Glassdoor", "glassdoor.com": "Glassdoor",
                    "iimjobs.com": "iimjobs", "unstop.com": "Unstop", "workatastartup.com": "YC Work at a Startup",
                    "ycombinator.com": "YC Work at a Startup", "freelancer.com": "Freelancer.com",
                    "remoteok.com": "RemoteOK", "himalayas.app": "Himalayas", "jobicy.com": "Jobicy",
                    "remotive.com": "Remotive", "weworkremotely.com": "We Work Remotely",
                    "news.ycombinator.com": "Hacker News", "apna.co": "apna", "shine.com": "Shine",
                    "timesjobs.com": "TimesJobs", "upwork.com": "Upwork", "contra.com": "Contra"}
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "cutt.ly", "rb.gy", "shorturl.at", "is.gd", "t.me",
              "wa.me", "chat.whatsapp.com", "forms.gle", "linktr.ee"}
BAD_TLDS = (".xyz", ".top", ".click", ".icu", ".buzz", ".shop", ".online", ".site", ".live", ".work", ".loan", ".rest")

# (pattern, reason) — India-specific job-scam patterns included
SCAM_RULES = [
    (r"telegram|whats\s?app|wa\.me|t\.me/", "moves you to Telegram/WhatsApp"),
    (r"(registration|joining|security|training|onboarding|application|processing|placement|verification|kit|"
     r"laptop|id card|uniform)\s*(fee|fees|charge|charges|deposit|amount)", "asks you to pay a fee or deposit"),
    (r"pay\s+(rs\.?|₹|inr|\$)?\s?\d+\s*(to|for)\s*(apply|join|start|register|confirm)|refundable deposit|"
     r"pay to (apply|join|start)", "asks you to pay before starting"),
    (r"(100%|guaranteed)\s*(job|placement|selection)|job guarantee", "promises a guaranteed job"),
    (r"no interview|without interview|direct (joining|selection)|offer letter (in|within) \d+ ?(hours|hrs|days)",
     "no interview / instant offer"),
    (r"earn\s+(rs\.?|₹|inr|\$)\s?\d[\d,]*\s*(per|a|/)\s*(day|week)|daily (payment|payout|income)|"
     r"weekly payout guaranteed", "promises fixed daily/weekly earnings"),
    (r"typing job|copy[- ]?paste|sms sending|form filling|captcha|data entry.{0,40}(home|mobile|daily)|"
     r"ad posting job|mobile (?:based )?job|part[- ]time job.{0,40}(daily|per day)", "typing / data-entry-from-home pattern"),
    (r"like (?:and |& )?(?:subscribe|share)|like (?:our )?(?:posts|videos)|rate (?:hotels|products|apps)|"
     r"review (?:products|hotels) for (?:cash|money)|task[- ]based (?:earning|income)|prepaid tasks?",
     "click / like / rating tasks (classic task scam)"),
    (r"crypto(currency)?\s+(trading|wallet|transfer)|usdt|forex trading job|binary option|gift ?cards?|"
     r"western union", "crypto / forex / gift-card money"),
    (r"send (?:me |us )?your (?:bank|card|otp|password|aadhaar|aadhar|pan)|share (?:your )?otp",
     "asks for bank / OTP / ID details"),
    (r"free (?:sample|test) (?:work|project) (?:of|for) (?:the )?(?:full|whole|entire)", "wants the full job free as a 'test'"),
    (r"(hr|recruiter|hiring manager)[^.\n]{0,60}@(gmail|yahoo|outlook|hotmail|rediffmail|ymail)\.", "recruiter uses a personal email"),
    (r"limited (seats|slots)|hurry,? apply|only today", "pressure tactics"),
]


def domain(url):
    try:
        d = urlparse(url if "://" in str(url) else "https://" + str(url)).netloc.lower().split(":")[0]
    except Exception:
        return ""
    return d[4:] if d.startswith("www.") else d


def in_set(d, s):
    return bool(d) and any(d == x or d.endswith("." + x) for x in s)


def platform_of(url):
    d = domain(url)
    for k, v in PLATFORM_DOMAINS.items():
        if d == k or d.endswith("." + k):
            return v
    if in_set(d, ATS_DOMAINS):
        return "Company careers (ATS)"
    return None


def scam_reasons(text):
    t = str(text or "")
    return [why for pat, why in SCAM_RULES if re.search(pat, t, re.I)]


def check(item, company_domain=None, company_verified=False):
    """item needs: title, url, desc (optional), source_kind ('ats'|'alert'|'board'|'search'|'freelance'|'careers'),
    pay_inr_month (optional, for jobs). Returns {"verdict", "score", "good": [...], "warn": [...]}"""
    good, warn = [], []
    url = item.get("url") or ""
    d = domain(url)
    kind = item.get("source_kind")
    text = f"{item.get('title', '')}\n{item.get('company', '')}\n{item.get('desc', '')}"
    bad = scam_reasons(text)
    score = 0
    if in_set(d, SHORTENERS):
        bad.append("link hides its destination (shortener / chat link)")
    if d.endswith(BAD_TLDS):
        bad.append(f"unusual web address ({d})")
    if not url.startswith("https://") and url:
        warn.append("link is not https")
        score -= 1

    if kind == "ats" or in_set(d, ATS_DOMAINS) or (company_domain and in_set(d, {company_domain})):
        score += 3; good.append("official company careers page")
    elif kind == "alert":
        score += 2; good.append(f"from your {item.get('platform') or 'job site'} alert email")
    elif platform_of(url):
        score += 1; good.append(f"on {platform_of(url)}")
    elif kind == "search":
        warn.append("found via web search — check it's still open")
    else:
        warn.append("unknown website")

    if company_verified:
        score += 2; good.append("company checked (website + mail server)")
    if kind == "search":
        score -= 1
        if not any("web search" in w for w in warn):
            warn.append("found via web search — check it's still open")
    p = item.get("pay_inr_month")
    if p and p > 150000 and re.search(r"fresher|intern|trainee|entry", text, re.I):
        bad.append("pay is far too high for a fresher role")
    if bad:
        return {"verdict": "risky", "score": -5, "good": good, "warn": bad + warn}
    verdict = "verified" if score >= 3 else "likely" if score >= 1 else "unverified"
    return {"verdict": verdict, "score": score, "good": good, "warn": warn}


SAFETY_RULES = [
    ("Never pay to get a job or a task", "Real employers and platforms don't charge registration, training, kit or "
     "'refundable' deposits. Any payment request means it's a scam."),
    ("Interviews come before offers", "An offer letter with no interview, or a job 'confirmed in 24 hours', is fake."),
    ("Stay on the platform", "Recruiters who push you to WhatsApp or Telegram, or chat-only 'HR', are the most common scam in India."),
    ("Check the company", "Open the company's own website and careers page, and find the recruiter on LinkedIn under that company. "
     "Real recruiters email from the company domain, not Gmail."),
    ("Never share OTPs, bank logins, Aadhaar or PAN early", "You only need these after a real offer, through official HR onboarding."),
    ("No 'like, rate or review' tasks", "Paid likes, hotel ratings and prepaid 'task' sites always end with you paying in."),
    ("If it sounds too good, it is", "A fresher job paying lakhs a month, or ₹5,000 a day for typing, is bait."),
    ("Report it", "India: call 1930 or report at cybercrime.gov.in. Also report the post on the platform."),
]
