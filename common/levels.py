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


def level(title, desc=""):
    """'entry' (fresher/junior/intern), 'senior' (hide), or 'not stated' (shown, marked 'check level')."""
    t = str(title or "")
    if re.search(r"\bintern(ship)?\b", t, re.I):
        return "entry"
    if SENIOR.search(t):
        return "senior"
    if ENTRY.search(t):
        return "entry"
    d = str(desc or "")[:4000]
    if re.search(r"\b0\s*(?:[-–]|to)\s*[12]\s*(?:years|yrs)|\bfreshers?\b|\bno experience required\b|\bentry[- ]level\b", d, re.I):
        return "entry"
    yrs = [int(m.group(1)) for m in YEARS.finditer(d)] + [int(m.group(1)) for m in MIN_YEARS.finditer(d)]
    yrs = [y for y in yrs if y < 30]
    if yrs:
        return "senior" if min(yrs) >= 2 else "entry"
    return "not stated"


def allowed(lvl):
    return lvl in ("entry", "not stated")
