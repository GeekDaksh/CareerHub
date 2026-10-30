"""Gate G0: config.py must be complete and typo-free. Unknown or missing keys stop the run."""
import re

import config as C

REQUIRED = {"PROFILE": dict, "SECTOR_CATALOG": dict, "CITY_OPTIONS": list, "ROLE_CATALOG": dict, "ROLE_QUERY": dict,
            "DEFAULT_SETTINGS": dict, "GIG_CATEGORIES": dict, "GIG_QUERIES": dict, "AI_PLATFORMS": list,
            "SHIELD": dict, "LEVEL": dict, "FX_TO_INR": dict, "MONTHLY_GOAL_INR": tuple, "REMOTE_COMPANIES": list}
SHIELD_KEYS = {"word_boundaries": bool, "normalize_text": bool, "negation_guard": bool, "chat_contact_only": bool, "wfh_money_rules": bool,
               "money_transfer_rules": bool, "personal_email_cv": bool, "weak_signal_combo": int}
LEVEL_KEYS = {"entry_words_win": bool, "staff_needs_role": bool, "assistant_not_senior": bool, "years_patterns_ext": bool, "senior_words_ext": bool, "senior_from_desc": bool, "hide_not_stated": bool}
SETTINGS_KEYS = {"main_sectors", "other_sectors", "locations", "roles", "gig_types"}


class ConfigError(ValueError):
    pass


def _check_block(name, block, spec):
    unknown = set(block) - set(spec)
    missing = set(spec) - set(block)
    if unknown or missing:
        raise ConfigError(f"config.{name}: unknown keys {sorted(unknown)} / missing keys {sorted(missing)} — fix the typo in config.py")
    bad = [k for k, t in spec.items() if not isinstance(block[k], t) or (t is int and isinstance(block[k], bool))]
    if bad:
        raise ConfigError(f"config.{name}: wrong type for {bad} (expected {[spec[k].__name__ for k in bad]})")


ATS_KINDS = {"greenhouse", "lever", "ashby"}


def validate(cfg=C):
    for name, t in REQUIRED.items():
        if not hasattr(cfg, name):
            raise ConfigError(f"config.py is missing {name}")
        if not isinstance(getattr(cfg, name), t):
            raise ConfigError(f"config.{name} must be a {t.__name__}")
    _check_block("SHIELD", cfg.SHIELD, SHIELD_KEYS)
    _check_block("LEVEL", cfg.LEVEL, LEVEL_KEYS)
    if set(cfg.DEFAULT_SETTINGS) != SETTINGS_KEYS:
        raise ConfigError(f"config.DEFAULT_SETTINGS keys must be {sorted(SETTINGS_KEYS)}")
    for k in ("main_sectors", "other_sectors"):
        bad = [x for x in cfg.DEFAULT_SETTINGS[k] if x not in cfg.SECTOR_CATALOG]
        if bad:
            raise ConfigError(f"config.DEFAULT_SETTINGS.{k} has unknown sectors {bad}")
    if set(cfg.ROLE_QUERY) != set(cfg.ROLE_CATALOG):
        raise ConfigError("config.ROLE_QUERY and ROLE_CATALOG must list the same roles")
    if not 0 <= cfg.SHIELD["weak_signal_combo"] <= 6:
        raise ConfigError("config.SHIELD.weak_signal_combo must be 0 (off) to 6")
    for c in cfg.REMOTE_COMPANIES:
        if not (isinstance(c, dict) and set(c) == {"name", "ats", "slug"} and c["ats"] in ATS_KINDS
                and re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", str(c["slug"]))):
            raise ConfigError(f"config.REMOTE_COMPANIES entry {c!r} must be {{name, ats (greenhouse/lever/ashby), slug}}")
    return True
