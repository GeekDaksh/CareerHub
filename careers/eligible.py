"""Can Daksh apply at all? Separate from level: a role can be entry-level and still need a PhD or a Master's, or
be limited to one graduating batch. Each "not eligible" comes with the exact words it was based on.

Rules (profile from config.PROFILE: degree level + graduation year):
  1. PhD title ("Software Engineer, PhD, Early Career", "Research PhD Intern") → not eligible            [high]
  2. Required qualifications ask for a PhD / current PhD enrolment with no Bachelor's / Master's
     alternative ("PhD, or Master's …" is an alternative)                                             [medium]
  3. Required qualifications ask for a Master's with no Bachelor's / equivalent-experience alternative  [medium]
     (only when the profile's degree is a Bachelor's)
  4. The post is limited to graduation years that don't include the profile's year
     ("2025 graduates", "class of 2026", "graduating between Dec 2025 and Aug 2026")                  [medium]
Anything else → eligible. Unclear wording errs on showing the job.
"""
import re

PHD_TITLE = re.compile(r"\bph\.?\s?d\b|\bdoctoral\b|post-?doc", re.I)
PHD = re.compile(r"\bph\.?\s?d\b|\bdoctorate\b|\bdoctoral\b", re.I)
PHD_ALT = re.compile(r"(?:or|and/or)\s+(?:a\s+)?(?:bachelor|master|b\.?\s?tech|b\.?\s?e\b|b\.?\s?s\b|m\.?\s?s\b|m\.?\s?tech|undergraduate)"
                     r"|(?:bachelor|master|b\.?\s?tech|m\.?\s?s\b|m\.?\s?tech)\w*[^.\n]{0,60}\bor\s+(?:a\s+)?ph\.?\s?d"
                     r"|ph\.?\s?d\.?\s*(?:is\s+)?(?:preferred|a plus|desirable|nice to have|optional)"
                     r"|ph\.?\s?d\.?,\s*or\b", re.I)
MASTERS = re.compile(r"\bmaster['’]?s?\s+(?:degree|or|in)\b|\bmaster['’]?s?\b(?=[^.\n]{0,15}(?:degree|or above|program))|"
                     r"\bm\.?\s?tech\b|\bm\.?\s?s\.?\s+(?:degree|in)\b|\bpost[- ]?graduat\w*", re.I)
BACHELOR = re.compile(r"bachelor|\bb\.?\s?tech\b|\bb\.?\s?e\.?\b|\bb\.?\s?s\.?\b|\bbsc\b|undergraduate|equivalent (?:practical )?experience|"
                      r"or equivalent", re.I)
YEAR_LIMIT = [re.compile(r"graduat\w*\s+(?:in|by|between|from)\s+(?:\w+\s+)?(20[2-3]\d)(?:\s*(?:and|to|-|–|or)\s*(?:\w+\s+)?(20[2-3]\d))?", re.I),
              re.compile(r"class of\s+(20[2-3]\d)(?:\s*(?:and|or|/|-|–)\s*(20[2-3]\d))?", re.I),
              re.compile(r"\b(20[2-3]\d)\s*(?:/\s*(20[2-3]\d)\s*)?(?:graduates|grads|batch|pass-?outs?|passing out)\b", re.I),
              re.compile(r"\bbatch\s*(?:of\s*)?(20[2-3]\d)(?:\s*(?:and|or|/|-|–)\s*(20[2-3]\d))?", re.I)]


def _required(desc):
    """→ (required-qualifications text, whether the post had a 'required' heading)"""
    from careers.match import sections
    parts, has_req = sections(desc)
    return (parts["req"], True) if has_req else (str(desc or "")[:4000], False)


NEEDS = re.compile(r"(pursuing|enrolled|currently|candidate|completed|hold|requires?|must|minimum|degree)\b", re.I)
PREFERRED = re.compile(r"preferred|a plus|nice to have|desirable|bonus", re.I)


def _years(text):
    ys = set()
    for rx in YEAR_LIMIT:
        for m in rx.finditer(text):
            a = int(m.group(1))
            b = int(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else a
            ys |= set(range(min(a, b), max(a, b) + 1))
    return ys, [m.group(0) for rx in YEAR_LIMIT for m in rx.finditer(text)][:2]


def check(job, degree="bachelor", grad_year=None):
    """→ {"ok": bool, "why": str, "evidence": str, "conf": "high"|"medium"|""}"""
    title = str(job.get("title") or "")
    desc = str(job.get("desc") or "")
    req, has_req = _required(desc)
    # a line counts as a requirement if it's in the 'required' section, or (no sections) says so in words
    lines = [l for l in re.split(r"\n|(?<=[.;•])\s|\s-\s", req) if l.strip() and not PREFERRED.search(l)]
    lines = [l for l in lines if has_req or NEEDS.search(l)]
    bachelor_route = bool(BACHELOR.search(req))      # a Bachelor's route anywhere in the requirements → degree rules don't fire
    if bachelor_route:
        lines = []
    if degree != "phd":
        m = PHD_TITLE.search(title)
        if m:
            return {"ok": False, "why": "for PhD holders / PhD students", "evidence": f"title: “{m.group(0)}”", "conf": "high"}
        for line in lines:
            if PHD.search(line) and not BACHELOR.search(line) and not MASTERS.search(line):
                return {"ok": False, "why": "requires a PhD", "evidence": line.strip()[:160], "conf": "medium"}
    if degree == "bachelor":
        for line in lines:
            if MASTERS.search(line) and not BACHELOR.search(line):
                alts = "a PhD or a Master's" if PHD.search(line) else "a Master's (or higher)"
                return {"ok": False, "why": f"requires {alts} — no Bachelor's route", "evidence": line.strip()[:160], "conf": "medium"}
    if grad_year:
        ys, ev = _years(f"{title}\n{req}")
        if ys and int(grad_year) not in ys:
            return {"ok": False, "why": f"only for graduation year {', '.join(map(str, sorted(ys)))} (you: {grad_year})",
                    "evidence": "; ".join(ev)[:160], "conf": "medium"}
    return {"ok": True, "why": "", "evidence": "", "conf": ""}
