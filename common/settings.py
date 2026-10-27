"""Your choices from the app's Settings tab (saved as settings/settings.json in the private dataset),
merged over the defaults in config.py. Used by the job finder, the gig radar and the app."""
import json
import os
import re

import config as C

SETTINGS_PATH = os.path.join("settings", "settings.json")


def clean(raw):
    s = dict(C.DEFAULT_SETTINGS)
    if isinstance(raw, dict):
        for k in s:
            if isinstance(raw.get(k), list):
                s[k] = raw[k]
    s["main_sectors"] = [x for x in s["main_sectors"] if x in C.SECTOR_CATALOG] or list(C.DEFAULT_SETTINGS["main_sectors"])
    s["other_sectors"] = [x for x in s["other_sectors"] if x in C.SECTOR_CATALOG and x not in s["main_sectors"]]
    s["locations"] = [x for x in s["locations"] if x in C.CITY_OPTIONS + C.REMOTE_OPTIONS] or list(C.DEFAULT_SETTINGS["locations"])
    s["roles"] = [x for x in s["roles"] if x in C.ROLE_CATALOG] or list(C.DEFAULT_SETTINGS["roles"])
    s["gig_types"] = [x for x in s["gig_types"] if x in C.GIG_CATEGORIES] or list(C.DEFAULT_SETTINGS["gig_types"])
    s["experience"] = C.EXPERIENCE
    return s


def load(data_dir=None):
    data_dir = data_dir or os.environ.get("DATA_DIR", "data")
    try:
        with open(os.path.join(data_dir, SETTINGS_PATH)) as f:
            return clean(json.load(f))
    except Exception:
        return clean(None)


def search_terms(s):
    return {x: C.SECTOR_CATALOG[x] for x in s["main_sectors"] + s["other_sectors"]}


def cities(s):
    return [c for c in s["locations"] if c in C.CITY_OPTIONS]


def role_words(s):
    return sorted({w for r in s["roles"] for w in C.ROLE_CATALOG[r]})


def roles_matched(title, s):
    t = str(title or "").lower()
    return [r for r in s["roles"] if any(w in t for w in C.ROLE_CATALOG[r])]


def location_ok(text, s):
    """Does a job location fit your chosen cities / remote options?"""
    t = str(text or "").lower()
    if not t or t in ("nan", "none"):
        return True   # unknown location: keep, the card says so
    for c in cities(s):
        if any(a in t for a in C.CITY_ALIASES.get(c, [c.lower()])):
            return True
    remote = bool(re.search(r"remote|anywhere|worldwide|work from home|wfh", t))
    if remote and "Remote (worldwide)" in s["locations"]:
        return True
    if remote and "Remote (India)" in s["locations"] and re.search(r"india|asia|apac|anywhere|worldwide", t):
        return True
    return False


def load_from(raw):
    return clean(raw)
