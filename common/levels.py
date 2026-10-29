"""Experience level from a job title (+ description if we have it). Fixed rule: only fresher / entry-level."""
import re

ENTRY = re.compile(r"\b(intern|internship|fresher|freshers|graduate|grad|new[- ]grad|entry[- ]level|junior|jr\.?|"
                   r"trainee|apprentice|campus|early[- ]career|associate engineer|associate data|associate ml|"
                   r"associate software|level 1|sde[- ]?(?:1|i)\b|engineer i\b|analyst i\b|0\s*[-–]\s*[12]\s*(?:years|yrs))\b", re.I)
SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead(?!\s*gen)|manager|director|head|vp|vice president|chief|"
                    r"architect|distinguished|fellow|sde[- ]?(?:2|3|ii|iii)\b|engineer (?:ii|iii|iv)\b|"
                    r"scientist (?:ii|iii)\b|l[4-9]\b|mts\s*[2-4])\b", re.I)
YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:[-–]|to)?\s*(?:\d{1,2}\s*)?\+?\s*(?:years|yrs)\.?\s*(?:of\s+)?(?:\w+\s+){0,3}"
                   r"(?:experience|exp\b)", re.I)
MIN_YEARS = re.compile(r"(?:minimum|min\.?|at least)\s*(?:of\s*)?(\d{1,2})\s*\+?\s*(?:years|yrs)", re.I)


YEARS_EXT = [re.compile(r"(\d{1,2})\s*\+?\s*(?:years|yrs)['’]?\s*(?:of\s+)?(?:\w+\s+){0,4}(?:experience|exp\b)", re.I),
             re.compile(r"experience\s*(?:of|:|-)?\s*(\d{1,2})\s*\+?\s*(?:[-–]|to)?\s*(?:\d{1,2}\s*)?(?:years|yrs)", re.I),
             re.compile(r"(\d{1,2})\s*\+\s*(?:years|yrs)\b", re.I)]
SENIOR_EXT = re.compile(r"\b(experienced|team lead|tech lead|supervisor|head of|lead (?:engineer|developer|data|ml|software|scientist))\b", re.I)
SENIOR_DESC = re.compile(r"\b(seasoned|extensive (?:professional |industry )?experience|proven track record|deep expertise|"
                         r"significant (?:professional )?experience)\b", re.I)


def level(title, desc="", opts=None):
    """'entry' (fresher/junior/intern), 'senior' (hide), or 'not stated' (shown, marked 'check level').
    opts = config.LEVEL-style switches (defaults: config)."""
    if opts is None:
        try:
            import config as _C
            opts = _C.LEVEL
        except Exception:
            opts = {}
    lv = _level(title, desc, opts)
    if lv == "not stated" and opts.get("hide_not_stated"):
        return "senior"
    return lv


ROLE_AFTER_STAFF = re.compile(r"^\s*(engineer|scientist|developer|software|data|ml|machine|research|product|designer|"
                              r"architect|analyst|backend|frontend|platform|security|site)", re.I)
JUNIOR_BEFORE = re.compile(r"(assistant|asst\.?|associate|junior|jr\.?|deputy|to the|to our|of the)\s+(\w+\s+){0,2}$", re.I)


def senior_hit(t, opts):
    for m in SENIOR.finditer(t):
        w = m.group(0).lower()
        if w == "staff" and opts.get("staff_needs_role") and not ROLE_AFTER_STAFF.match(t[m.end():]):
            continue
        if opts.get("assistant_not_senior") and w in ("manager", "director", "head", "chief", "lead") \
                and JUNIOR_BEFORE.search(t[:m.start()]):
            continue
        return True
    return bool(opts.get("senior_words_ext") and SENIOR_EXT.search(t))


def _level(title, desc, opts):
    t = str(title or "")
    if re.search(r"\bintern(ship)?\b", t, re.I):
        return "entry"
    if opts.get("entry_words_win") and ENTRY.search(t):
        return "entry"
    if senior_hit(t, opts):
        return "senior"
    if ENTRY.search(t):
        return "entry"
    d = str(desc or "")[:4000]
    if re.search(r"\b0\s*(?:[-–]|to)\s*[12]\s*(?:years|yrs)|\bfreshers?\b|\bno experience required\b|\bentry[- ]level\b", d, re.I):
        return "entry"
    yrs = [int(m.group(1)) for m in YEARS.finditer(d)] + [int(m.group(1)) for m in MIN_YEARS.finditer(d)]
    if opts.get("years_patterns_ext"):
        yrs += [int(m.group(1)) for rx in YEARS_EXT for m in rx.finditer(d)]
    yrs = [y for y in yrs if y < 30]
    if yrs:
        return "senior" if min(yrs) >= 2 else "entry"
    if opts.get("senior_from_desc") and SENIOR_DESC.search(d):
        return "senior"
    return "not stated"


def allowed(lvl):
    return lvl in ("entry", "not stated")
