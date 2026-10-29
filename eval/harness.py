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


def load(split, final=False):
    """G1 data gate: file hash, row and label counts, unique ids, no train/test overlap, frozen hard set unchanged.
    The test split opens only with final=True, which only `python -m eval.run_eval --final` passes (and logs)."""
    if split not in ("train", "test"):
        raise GateError("split must be train or test")
    if split == "test" and not final:
        raise GateError("the test split is locked — only `python -m eval.run_eval --final` may open it")
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
        camp = hashlib.sha1(re.sub(r"[^a-z]", "", (clean(r["description"]) or clean(r["title"])).lower())[:400].encode()).hexdigest()[:12]
        out.append({"id": r["job_id"], "half": half_of(r["job_id"]), "title": clean(r["title"]), "cluster": camp,
                    "text": full, "level_text": clean(r["description"]) + " " + clean(r["requirements"]),
                    "fraud": r["fraudulent"] == "1", "exp": r["required_experience"]})
    return out


def unseen_campaigns(test_rows, train_rows):
    """Test posts whose campaign (same opening text) never appears in train. EMSCAD repeats scam campaigns, so a
    rule tuned on train may 'catch' a test copy of a train scam. Scoring only unseen campaigns removes that help."""
    seen = {r["cluster"] for r in train_rows}
    return [r for r in test_rows if r["cluster"] not in seen]


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


def bootstrap(flags, n=1000, seed=7, clusters=None):
    """95% range by resampling. With clusters, whole campaigns are resampled together (copies of one scam
    campaign are not independent evidence, so this gives a wider, more honest range)."""
    if not flags:
        return (float("nan"), float("nan"))
    rnd = random.Random(seed)
    if clusters is None:
        k = len(flags)
        vals = sorted(sum(flags[rnd.randrange(k)] for _ in range(k)) / k for _ in range(n))
    else:
        groups = {}
        for f, c in zip(flags, clusters):
            groups.setdefault(c, []).append(f)
        g = list(groups.values())
        vals = []
        for _ in range(n):
            pick = [g[rnd.randrange(len(g))] for _ in range(len(g))]
            tot = sum(len(x) for x in pick)
            vals.append(sum(sum(x) for x in pick) / tot)
        vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n) - 1]


def metrics(rows, preds):
    def pick(cond, val):
        sel = [(val(p), r.get("cluster", r.get("id", i))) for i, (r, p) in enumerate(zip(rows, preds)) if cond(r)]
        return [x for x, _ in sel], [c for _, c in sel]
    scam = pick(lambda r: r["fraud"], lambda p: p["blocked"])
    legit = pick(lambda r: not r["fraud"], lambda p: p["blocked"])
    senior = pick(lambda r: r["exp"] in SENIOR_LABELS and not r["fraud"], lambda p: p["shown"])
    entry = pick(lambda r: r["exp"] in ENTRY_LABELS and not r["fraud"], lambda p: not p["shown"])
    return {
        "catch_rate": card(*scam, "Share of real scam posts the shield blocks", higher_better=True),
        "false_block": card(*legit, "Share of real (non-scam) posts wrongly blocked", higher_better=False),
        "senior_leak": card(*senior, "Share of senior jobs that still reach you", higher_better=False),
        "entry_loss": card(*entry, "Share of real entry-level jobs wrongly hidden", higher_better=False),
    }


def card(flags, clusters, meaning, higher_better):
    lo, hi = bootstrap(flags, clusters=clusters)
    return {"value": rate(flags), "n": len(flags), "campaigns": len(set(clusters)), "hits": sum(flags), "ci95": [lo, hi],
            "meaning": meaning, "higher_is_better": higher_better, "range_method": "campaign (cluster) bootstrap"}


METRIC_SEL = {
    "catch_rate": (lambda r: r["fraud"], lambda p: p["blocked"]),
    "false_block": (lambda r: not r["fraud"], lambda p: p["blocked"]),
    "senior_leak": (lambda r: r["exp"] in SENIOR_LABELS and not r["fraud"], lambda p: p["shown"]),
    "entry_loss": (lambda r: r["exp"] in ENTRY_LABELS and not r["fraud"], lambda p: not p["shown"]),
}


def paired_delta(rows, base_preds, new_preds, n=1000, seed=7):
    """Change vs baseline with a PAIRED campaign bootstrap: both versions are scored on the same resampled
    campaigns, so the range is for the difference itself. Range not containing 0 = a real change."""
    out = {}
    for k, (cond, val) in METRIC_SEL.items():
        groups = {}
        for r, a, b in zip(rows, base_preds, new_preds):
            if cond(r):
                g = groups.setdefault(r.get("cluster", r.get("id")), [0, 0, 0])
                g[0] += 1; g[1] += val(a); g[2] += val(b)
        g = list(groups.values())
        tot = sum(x[0] for x in g)
        delta = (sum(x[2] for x in g) - sum(x[1] for x in g)) / tot
        rnd = random.Random(seed)
        vals = []
        for _ in range(n):
            pick = [g[rnd.randrange(len(g))] for _ in range(len(g))]
            t = sum(x[0] for x in pick)
            vals.append((sum(x[2] for x in pick) - sum(x[1] for x in pick)) / t)
        vals.sort()
        lo, hi = vals[int(0.025 * n)], vals[int(0.975 * n) - 1]
        out[k] = {"delta": delta, "ci95": [lo, hi], "real_change": lo > 0 or hi < 0}
    return out


def calibration(rows, preds, shield):
    """Are the labels true? For the shield: of the posts with N scam signs, how many really are scams.
    For the level filter: of the posts labelled entry / not stated / senior, what EMSCAD says they are."""
    sc = {}
    for r in rows:
        n = min(len(trust.scam_reasons(f"{r['title']}\n{r['text']}", shield)), 2)
        c = sc.setdefault(n, [0, 0])
        c[0] += 1
        c[1] += r["fraud"]
    lv = {}
    for r, p in zip(rows, preds):
        if r["fraud"] or r["exp"] not in ENTRY_LABELS | SENIOR_LABELS:
            continue
        c = lv.setdefault(p["level"], [0, 0, 0])
        c[0] += 1
        c[1] += r["exp"] in ENTRY_LABELS
        c[2] += r["exp"] in SENIOR_LABELS
    return {"shield": {f"{k}{'+' if k == 2 else ''} signs": {"posts": v[0], "really_scam": v[1],
                                                           "scam_rate": v[1] / v[0]} for k, v in sorted(sc.items())},
            "level": {k: {"posts": v[0], "really_entry": v[1] / v[0], "really_senior": v[2] / v[0]}
                      for k, v in sorted(lv.items())}}


def fmt_calibration(cal):
    out = ["Calibration — scam signs found vs. really a scam:"]
    for k, v in cal["shield"].items():
        out.append(f"   {k:9s} {v['posts']:6d} posts · {v['really_scam']:4d} scams · {v['scam_rate']*100:5.1f}% are scams")
    out.append("Calibration — level label vs. EMSCAD's own label (jobs with a stated level):")
    for k, v in cal["level"].items():
        out.append(f"   {k:11s} {v['posts']:5d} posts · {v['really_entry']*100:5.1f}% entry · {v['really_senior']*100:5.1f}% senior")
    return "\n".join(out)


def compare(new, base, paired=None):
    """Add change vs baseline and whether the ranges overlap (overlap = the change could be luck)."""
    for k, c in new.items():
        b = base[k]
        c["delta_vs_baseline"] = c["value"] - b["value"]
        c["ranges_overlap"] = not (c["ci95"][0] > b["ci95"][1] or c["ci95"][1] < b["ci95"][0])
        if paired:
            c["delta_ci95"] = paired[k]["ci95"]
            c["real_change"] = paired[k]["real_change"]
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
        d = ""
        if "delta_ci95" in c:
            lo, hi = c["delta_ci95"]
            d = f"  Δ {c['delta_vs_baseline']*100:+.2f} pp [{lo*100:+.2f}…{hi*100:+.2f}]{' real change' if c['real_change'] else ' could be luck'}"
        elif "delta_vs_baseline" in c:
            d = f"  Δ {c['delta_vs_baseline']*100:+.1f} pp{' (could be luck)' if c.get('ranges_overlap') else ' (real change)'}"
        lines.append(f"{k:12s} {c['value']*100:6.2f}%  [{c['ci95'][0]*100:.2f}–{c['ci95'][1]*100:.2f}]  n={c['n']:5d} ({c.get('campaigns','?')} campaigns){d}  — {c['meaning']}")
    return "\n".join(lines)
