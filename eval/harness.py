"""Measurement harness for the two filters that decide what Daksh sees.

  Scam shield  : catch rate   = scams blocked / all scams            (higher = better)
                 false blocks = real posts blocked / all real posts   (lower = better, guardrail)
  Fresher filter: senior leak = senior jobs shown / all senior jobs   (lower = better)
                 entry loss   = entry jobs hidden / all entry jobs    (lower = better, guardrail)

Data: EMSCAD (Vidros et al., 2017) — 17,880 real job ads, 866 confirmed fraudulent, with 'required_experience'.
Split: 60% train / 40% test by a hash of job_id (fixed, never changes). Test is only read with --final.
"""
import csv
import hashlib
import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from common import levels, trust  # noqa: E402

DATA = os.path.join(ROOT, "eval", ".data", "fake_job_postings.csv")
EMSCAD_SHA = "874aea73d6fb9e35ed48846991e652cdedfc4c3dcbd839a7ba9770f61391c8ba"
HARD = os.path.join(ROOT, "eval", "hardset.jsonl")
HARD_SHA = open(os.path.join(ROOT, "eval", "hardset.sha256")).read().split()[0]
SENIOR_LABELS = {"Mid-Senior level", "Director", "Executive"}
ENTRY_LABELS = {"Entry level", "Internship"}


class GateError(RuntimeError):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def split_of(job_id):
    return "train" if int(hashlib.sha1(str(job_id).encode()).hexdigest(), 16) % 10 < 6 else "test"


def half_of(job_id):
    """Two fixed halves of train (A/B): an accepted change must help on both."""
    return "A" if int(hashlib.sha1(("half" + str(job_id)).encode()).hexdigest(), 16) % 2 == 0 else "B"


def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def load(split):
    """G1 data gate: file hash, row and label counts, unique ids, no train/test overlap, frozen hard set unchanged."""
    if split not in ("train", "test"):
        raise GateError("split must be train or test")
    if not os.path.exists(DATA):
        raise GateError(f"EMSCAD missing at {DATA} — run: bash eval/fetch_emscad.sh")
    if sha256(DATA) != EMSCAD_SHA:
        raise GateError("EMSCAD file hash changed — refusing to evaluate on unknown data")
    if sha256(HARD) != HARD_SHA:
        raise GateError("hardset.jsonl changed after it was frozen — revert it (frozen sets never change)")
    csv.field_size_limit(10 ** 7)
    rows = list(csv.DictReader(open(DATA, newline="", encoding="utf-8")))
    ids = [r["job_id"] for r in rows]
    fraud = sum(r["fraudulent"] == "1" for r in rows)
    problems = []
    if len(rows) != 17880:
        problems.append(f"expected 17,880 rows, got {len(rows)}")
    if fraud != 866:
        problems.append(f"expected 866 fraudulent, got {fraud}")
    if len(set(ids)) != len(ids):
        problems.append("duplicate job_id values")
    tr = {i for i in ids if split_of(i) == "train"}
    te = {i for i in ids if split_of(i) == "test"}
    if tr & te:
        problems.append("train/test overlap")
    if problems:
        raise GateError("G1 data gate failed: " + "; ".join(problems))
    out = []
    for r in rows:
        if split_of(r["job_id"]) != split:
            continue
        full = " ".join(clean(r[k]) for k in ("title", "company_profile", "description", "requirements", "benefits"))
        out.append({"id": r["job_id"], "half": half_of(r["job_id"]), "title": clean(r["title"]),
                    "text": full, "level_text": clean(r["description"]) + " " + clean(r["requirements"]),
                    "fraud": r["fraudulent"] == "1", "exp": r["required_experience"]})
    return out


def load_hard():
    if sha256(HARD) != HARD_SHA:
        raise GateError("hardset.jsonl changed after it was frozen")
    return [json.loads(l) for l in open(HARD, encoding="utf-8")]


# ---------------------------------------------------------------- predictions
def predict(rows, shield, level_opts):
    out = []
    for r in rows:
        blocked = bool(trust.scam_reasons(f"{r['title']}\n{r['text']}", shield))
        lv = levels.level(r["title"], r.get("level_text", r["text"]), level_opts)
        out.append({"blocked": blocked, "shown": lv != "senior", "level": lv})
    return out


# ---------------------------------------------------------------- metrics with 95% bootstrap ranges
def rate(flags):
    return (sum(flags) / len(flags)) if flags else float("nan")


def bootstrap(flags, n=1000, seed=7):
    if not flags:
        return (float("nan"), float("nan"))
    rnd = random.Random(seed)
    k = len(flags)
    vals = sorted(sum(flags[rnd.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return vals[int(0.025 * n)], vals[int(0.975 * n) - 1]


def metrics(rows, preds):
    scam = [p["blocked"] for r, p in zip(rows, preds) if r["fraud"]]
    legit = [p["blocked"] for r, p in zip(rows, preds) if not r["fraud"]]
    senior = [p["shown"] for r, p in zip(rows, preds) if r["exp"] in SENIOR_LABELS and not r["fraud"]]
    entry = [not p["shown"] for r, p in zip(rows, preds) if r["exp"] in ENTRY_LABELS and not r["fraud"]]
    return {
        "catch_rate": card(scam, "Share of real scam posts the shield blocks", higher_better=True),
        "false_block": card(legit, "Share of real (non-scam) posts wrongly blocked", higher_better=False),
        "senior_leak": card(senior, "Share of senior jobs that still reach you", higher_better=False),
        "entry_loss": card(entry, "Share of real entry-level jobs wrongly hidden", higher_better=False),
    }


def card(flags, meaning, higher_better):
    lo, hi = bootstrap(flags)
    return {"value": rate(flags), "n": len(flags), "hits": sum(flags), "ci95": [lo, hi], "meaning": meaning,
            "higher_is_better": higher_better}


def compare(new, base):
    """Add change vs baseline and whether the ranges overlap (overlap = the change could be luck)."""
    for k, c in new.items():
        b = base[k]
        c["delta_vs_baseline"] = c["value"] - b["value"]
        c["ranges_overlap"] = not (c["ci95"][0] > b["ci95"][1] or c["ci95"][1] < b["ci95"][0])
    return new


def hard_eval(shield, level_opts):
    res = []
    for c in load_hard():
        txt = f"{c['title']}\n{c['text']}"
        blocked = bool(trust.scam_reasons(txt, shield))
        lv = levels.level(c["title"], c["text"], level_opts)
        ok_scam = blocked == c["scam"]
        ok_level = True if c["level"] is None else ((lv != "senior") == (c["level"] == "entry"))
        res.append({"id": c["id"], "title": c["title"], "scam_ok": ok_scam, "level_ok": ok_level,
                    "blocked": blocked, "level": lv, "reasons": trust.scam_reasons(txt, shield)})
    return res


def fmt(m):
    lines = []
    for k, c in m.items():
        d = f"  Δ {c['delta_vs_baseline']*100:+.1f} pp{' (could be luck)' if c.get('ranges_overlap') else ' (real change)'}" \
            if "delta_vs_baseline" in c else ""
        lines.append(f"{k:12s} {c['value']*100:6.2f}%  [{c['ci95'][0]*100:.2f}–{c['ci95'][1]*100:.2f}]  n={c['n']:5d}{d}  — {c['meaning']}")
    return "\n".join(lines)
