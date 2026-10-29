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


# ---- optional rule sets, switched by config.SHIELD (measured in eval/LOOP.md) ----
# Same reasons as SCAM_RULES, but whole-word matching and tighter phrasing (fixes false blocks found on train).
STRICT_RULES = [
    (r"\b(telegram|whats\s?app)\b|wa\.me/|t\.me/", "moves you to Telegram/WhatsApp"),
    (r"\b(registration|joining|security|training|onboarding|application|processing|placement|verification|kit|"
     r"laptop|id card|uniform)\s*(fee|fees|charge|charges|deposit|amount)\b", "asks you to pay a fee or deposit"),
    (r"\bpay\s+(rs\.?|₹|inr|\$)\s?\d+\s*(to|for)\s*(apply|join|start|register|confirm)\b|\brefundable deposit\b|"
     r"\b(you|must|need to|have to|kindly|first|will need to)\s+pay\b[^.\n]{0,30}\b(to|before|for)\s+"
     r"(apply|join|start|register|confirm|the (job|offer|position))\b", "asks you to pay before starting"),
    (r"(100%|\bguaranteed)\s*(job|placement|selection)\b|\bjob guarantee\b", "promises a guaranteed job"),
    (r"\bno interview\b|\bwithout (an )?interview\b|\bdirect (joining|selection)\b|\boffer letter (in|within) \d+ ?(hours|hrs|days)\b",
     "no interview / instant offer"),
    (r"\bearn\s+(rs\.?|₹|inr|\$)\s?\d[\d,]*\s*(per|a|/)\s*(day|week)\b|\bdaily (payment|payout|income)\b|"
     r"\bweekly payout guaranteed\b", "promises fixed daily/weekly earnings"),
    (r"\btyping jobs?\b|\bcopy[- ]?paste (jobs?|work)\b|\bsms sending\b|\bform filling (jobs?|work)\b|"
     r"\bcaptcha (entry|typing|jobs?)\b|\bdata entry\b.{0,40}\b(homes?|mobile|daily)\b|\bad posting jobs?\b|"
     r"\bmobile (based )?jobs?\b(?! board)|\bpart[- ]time jobs?\b.{0,40}\b(daily|per day)\b", "typing / data-entry-from-home pattern"),
    (r"\blike (and |& )?(subscribe|share)\b|\blike (our )?(posts|videos)\b|\brate (hotels|products|apps)\b|"
     r"\breview (products|hotels) for (cash|money)\b|\btask[- ]based (earning|income)\b|\bprepaid tasks?\b",
     "click / like / rating tasks (classic task scam)"),
    (r"\bcrypto(currency)?\s+(trading|wallet|transfer)\b|\busdt\b|\bforex trading jobs?\b|\bbinary options?\b|"
     r"\b(buy|purchase|send|pay (in|with|via|using))\s+(\w+\s+)?gift ?cards?\b|\b(via|through|by|using) western union\b",
     "crypto / forex / gift-card money"),
    (r"\bsend (me |us )?your (bank|card|otp|password|aadhaar|aadhar|pan)\b|\bshare (your )?otp\b",
     "asks for bank / OTP / ID details"),
    (r"\bfree (sample|test) (work|project) (of|for) (the )?(full|whole|entire)\b", "wants the full job free as a 'test'"),
    (r"\b(hr|recruiter|hiring manager)\b[^.\n]{0,60}@(gmail|yahoo|outlook|hotmail|rediffmail|ymail)\.", "recruiter uses a personal email"),
    (r"\blimited (seats|slots)\b|\bhurry,? apply\b|\bonly today\b", "pressure tactics"),
]
HOMOGLYPHS = str.maketrans({"а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "і": "i", "Т": "T",
                            "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C", "Н": "H", "К": "K", "М": "M", "В": "B"})
NEGATION = re.compile(r"\b(no|never|not|don't|do not|doesn't|without|zero|free of|beware|nor|cover|covers|covered|"
                      r"reimburse|reimbursed|waived|paid by (the )?(company|employer))\b[^.!\n]{0,40}$", re.I)
NEGATABLE = {"asks you to pay a fee or deposit", "asks you to pay before starting"}
CHAT_REASON = "moves you to Telegram/WhatsApp"
CHAT_CONTACT = re.compile(
    r"\b(contact|message|msg|ping|text|reach|dm|chat with|call|join|apply)\s+(us\s+|hr\s+|our\s+|the\s+|me\s+)?"
    r"(on\s+|via\s+|at\s+|through\s+|in\s+)?(whatsapp|telegram)"
    r"|\b(whatsapp|telegram)\s*(hr|recruiter|number|no\.?)\b|\b(whatsapp|telegram)[^a-z]{0,5}\+?\d[\d\s-]{7,}"
    r"|wa\.me|t\.me/|chat\.whatsapp\.com", re.I)
EXTRA_RULES = {
    # v2: dropped "work from home … income" (it hit 15 scams AND 15 real jobs on train, see eval/LOOP.md)
    "wfh_money_rules": [(r"earn (up to |upto )?(\$|₹|rs\.?|inr)\s?\d[\d,]*\+?\s*(per|a|/|every)\s*(week|day|hour)"
                         r"|no experience (necessary|needed|required).{0,80}?(earn|\$\s?\d|₹|income)"
                         r"|home[- ]based (job|work|business)|be your own boss|extra income from home",
                         "earn-from-home money promise")],
    "money_transfer_rules": [(r"money transfer|wire (the )?(money|funds|balance)|transfer (the )?funds"
                              r"|receive (payments|funds|money) (from|into|on behalf)|payment processing (agent|assistant|representative|coordinator)"
                              r"|financial (agent|representative)|reshipp?ing|package (forwarding|handler)|mystery shopper"
                              r"|deposit (the |a )?(check|cheque)", "money-transfer / reshipping / mystery-shopper scheme")],
    "personal_email_cv": [(r"(send|email|mail|forward|share)\s+(your\s+|us\s+your\s+)?(cv|resume|resumes|biodata|profile)"
                           r"[^.\n]{0,40}@(gmail|yahoo|outlook|hotmail|rediffmail|ymail)\.",
                           "asks for your CV at a personal email address")],
}
WEAK_SIGNALS = [
    (r"no (prior )?experience (necessary|needed|required)", "no experience needed"),
    (r"(immediate|urgent)(ly)? (start|joining|hiring|requirement)", "urgent / immediate start"),
    (r"flexible (hours|schedule|time)", "flexible hours"),
    (r"(work|working) from home|home[- ]based|work at home", "work from home"),
    (r"data entry|typing|clerical|administrative assistant", "data entry / admin"),
    (r"(earn|income|make)\s.{0,20}(\$|₹|rs\.?)\s?\d", "money amount promised"),
    (r"(easy|simple) (job|work|task|money)", "'easy money' wording"),
    (r"(apply|send|email)[^.\n]{0,30}@(gmail|yahoo|hotmail|outlook)\.", "personal email contact"),
]


def normalize(t):
    """Undo common tricks scammers use to slip past filters."""
    import unicodedata
    t = unicodedata.normalize("NFKC", t).translate(HOMOGLYPHS)
    t = re.sub(r"[​-‏⁠﻿]", "", t)
    t = re.sub(r"\b(?:[A-Za-z] ){3,}[A-Za-z]\b", lambda m: m.group(0).replace(" ", ""), t)   # 'W h a t s A p p'
    t = re.sub(r"\bw\s?h?a\s?t+s?\s?a\s?p+\b|\bwatsapp\b|\bwhtsapp\b|\bwhatsap\b", "whatsapp", t, flags=re.I)
    t = re.sub(r"\btele\s?gram\b|\btelegrm\b", "telegram", t, flags=re.I)
    return t


def scam_reasons(text, shield=None):
    """Scam signs found in a post, as plain-language reasons. shield = config.SHIELD-style switches (defaults: config)."""
    if shield is None:
        try:
            import config as _C
            shield = _C.SHIELD
        except Exception:
            shield = {}
    t = str(text or "")[:20000]
    if shield.get("normalize_text"):
        t = normalize(t)
    out = []
    for pat, why in (STRICT_RULES if shield.get("word_boundaries") else SCAM_RULES):
        if why == CHAT_REASON and shield.get("chat_contact_only"):
            if CHAT_CONTACT.search(t):
                out.append(why)
            continue
        if why in NEGATABLE and shield.get("negation_guard"):
            if any(not NEGATION.search(t[max(0, m.start() - 60):m.start()]) for m in re.finditer(pat, t, re.I)):
                out.append(why)
            continue
        if re.search(pat, t, re.I):
            out.append(why)
    for key, rules in EXTRA_RULES.items():
        if shield.get(key):
            out += [why for pat, why in rules if re.search(pat, t, re.I)]
    n = shield.get("weak_signal_combo") or 0
    if n:
        weak = [why for pat, why in WEAK_SIGNALS if re.search(pat, t, re.I)]
        if len(weak) >= n:
            out.append("several warning signs together: " + ", ".join(weak))
    return list(dict.fromkeys(out))


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
