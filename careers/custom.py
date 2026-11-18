"""Companies Daksh adds himself (in the app), and finding where their jobs live.

Safety: a pasted link is never fetched as-is. It is only matched against known job-system address patterns, and
the collector then builds the API address itself from cleaned-up parts (letters, digits, - and _ only). Anything
else becomes a plain link in the app. So a pasted link can't make the collector reach an arbitrary server.

Stored by the app in the private data store: careerprefs/companies.json  [{name, url, tier, added}]
Found settings are cached by the collector in careers/official.json → "custom".
"""
import re

MAX_COMPANIES = 30
TIERS = ["FAANG+", "Big tech", "Finance & payments", "India major", "Startup"]
SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,59}$")
NAME = re.compile(r"^[\w .,&()'+-]{1,60}$")

PATTERNS = [   # (ats, regex on the pasted link)
    ("workday", re.compile(r"^https://([a-z0-9-]{1,40})\.(wd\d{1,2})\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]{1,60})(?:[/?#]|$)")),
    ("greenhouse", re.compile(r"^https://(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/([A-Za-z0-9_-]{1,60})(?:[/?#]|$)")),
    ("lever", re.compile(r"^https://jobs\.lever\.co/([A-Za-z0-9_-]{1,60})(?:[/?#]|$)")),
    ("ashby", re.compile(r"^https://jobs\.ashbyhq\.com/([A-Za-z0-9_.-]{1,60})(?:[/?#]|$)")),
    ("orc", re.compile(r"^https://([a-z0-9-]{2,30}\.fa\.(?:[a-z0-9]{2,6}\.)?oraclecloud\.com)/hcmUI/CandidateExperience/[a-z-]{2,8}/sites/([A-Za-z0-9_]{1,30})(?:[/?#]|$)")),
]


class Bad(ValueError):
    pass


def clean(name, url="", tier="Big tech"):
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    if not NAME.match(name):
        raise Bad("company name: 1–60 letters, numbers, spaces or . , & ( ) ' + -")
    url = str(url or "").strip()
    if url and (not url.startswith("https://") or len(url) > 300 or re.search(r"[\s<>\"']", url)):
        raise Bad("careers link must be a normal https:// address")
    if tier not in TIERS:
        raise Bad("pick a group from the list")
    return {"name": name, "url": url, "tier": tier}


def from_url(url):
    """Pasted link → connector settings, or None (then it's shown as a link)."""
    for ats, rx in PATTERNS:
        m = rx.match(str(url or ""))
        if not m:
            continue
        if ats == "workday":
            return {"ats": "workday", "tenant": m.group(1), "wd": m.group(2), "site": m.group(3)}
        if ats == "orc":
            return {"ats": "orc", "host": m.group(1), "site": m.group(2)}
        return {"ats": ats, "slug": m.group(1)}
    return None


def slug_guesses(name):
    base = re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()
    out = [base.replace(" ", ""), base.replace(" ", "-"), base.split(" ")[0] if base else ""]
    return [s for i, s in enumerate(out) if s and SLUG.match(s) and s not in out[:i]]


def discover(entry, try_board):
    """Find where a company's jobs live. try_board(ats, slug) → number of jobs (raises if not found).
    Returns settings + 'found' text. Only Greenhouse / Lever / Ashby can be guessed from a name; Workday and Oracle
    need the careers link."""
    if entry.get("url"):
        cfg = from_url(entry["url"])
        if cfg:
            return {**cfg, "found": f"from your link ({cfg['ats']})"}
    for slug in slug_guesses(entry["name"]):
        for ats in ("greenhouse", "lever", "ashby"):
            try:
                n = try_board(ats, slug)
            except Exception:
                continue
            if n:
                return {"ats": ats, "slug": slug, "guessed": True,
                        "found": f"found on {ats.title()} by name ({n} jobs worldwide) — check it's the right company"}
    return {"ats": "link", "search_url": entry.get("url") or "",
            "found": "couldn't find its job list automatically — " +
                     ("shown as a link" if entry.get("url") else "add its careers page link to try again")}
