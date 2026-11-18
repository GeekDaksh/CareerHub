"""Learns what Daksh likes from what he does in the app, and finds similar jobs. Plain counting, fully explainable.

Signals (weights): Applied +3 · Like +2 · Save +1 · Hide −1 · Dislike −2 (a dislike reason puts the weight on
that kind of feature only: "Too senior" → level, "Not my field" → role type / specialties / skills,
"Not this company" → company, "Wrong place" → work mode / tier).

Features of a job: role type, specialties, top skills, company, company group, level fit, work mode, title words.

Weight of a feature f (clipped to ±2):
    w(f) = log( share of f among liked jobs / share of f among all jobs )
         − log( share of f among disliked jobs / share of f among all jobs )
(shares smoothed with +1/+2; a side with no reactions adds 0). A feature that's in every job (e.g. "India") gets
~0 because its share among liked jobs equals its share overall — only what makes liked jobs DIFFERENT counts.

For-you score of a job = sum of w(f) over its features that have any reaction behind them, shown as 0–100
(50 = neutral), with the 3 biggest reasons. Turns on after MIN_REACTIONS reactions, at least one positive.

Similar jobs: weighted overlap of features, rarer features counting more (idf), skills and role type first.
"""
import math
import re
from collections import Counter

SIGNAL = {"applied": 3.0, "like": 2.0, "saved": 1.0, "hidden": -1.0, "dislike": -2.0}
REASONS = {"senior": ("lvl:",), "field": ("fam:", "spec:", "skill:", "word:"), "company": ("co:",),
           "place": ("mode:", "tier:")}
MIN_REACTIONS = 3
CLIP = 2.0
MAX_REACTIONS = 3000
STOP = set("and the for with of in at to a an ii iii iv sr senior staff principal lead engineer engineering "
           "india bengaluru bangalore hyderabad pune mumbai gurugram noida chennai remote".split())
LABEL = {"fam": "role", "spec": "specialty", "skill": "skill", "co": "company", "tier": "group", "lvl": "level",
         "mode": "work mode", "word": "title word"}


def features(job):
    f = {f"fam:{job.get('family')}", f"co:{job.get('company')}", f"tier:{job.get('company_tier')}",
         f"lvl:{job.get('fresher_fit')}"}
    if job.get("work_mode") and job.get("work_mode") != "Not stated":
        f.add(f"mode:{job['work_mode']}")
    f |= {f"spec:{s}" for s in job.get("specialties") or []}
    sk = job.get("skills") or []
    f |= {f"skill:{s['skill'] if isinstance(s, dict) else s}" for s in sk[:8]}
    for w in re.findall(r"[a-z][a-z+#/]{2,}", str(job.get("title") or "").lower()):
        if w not in STOP:
            f.add(f"word:{w}")
    return sorted(f)


def _weights(reactions, background):
    """reactions: [{r, reason, f:[features]}]; background: list of feature lists (all current jobs)."""
    pos, neg = Counter(), Counter()
    P = N = 0.0
    for x in reactions:
        s = SIGNAL.get(x.get("r"), 0)
        if not s:
            continue
        feats = x.get("f") or []
        if s < 0 and x.get("reason") in REASONS:
            feats = [f for f in feats if f.startswith(REASONS[x["reason"]])] or feats
        for f in feats:
            (pos if s > 0 else neg)[f] += abs(s)
        if s > 0:
            P += s
        else:
            N += -s
    B = len(background) or 1
    bg = Counter(f for fs in background for f in set(fs))
    w = {}
    for f in set(pos) | set(neg):
        base = (bg[f] + 1) / (B + 2)
        v = 0.0
        if P:
            v += math.log(((pos[f] + 1) / (P + 2)) / base)
        if N:
            v -= math.log(((neg[f] + 1) / (N + 2)) / base)
        w[f] = max(-CLIP, min(CLIP, v))
    return w, pos, neg


class Model:
    def __init__(self, reactions, background):
        self.reactions = [x for x in reactions if x.get("r") in SIGNAL][-MAX_REACTIONS:]
        n_pos = sum(1 for x in self.reactions if SIGNAL[x["r"]] > 0)
        self.active = len(self.reactions) >= MIN_REACTIONS and n_pos >= 1
        self.w, self.pos, self.neg = _weights(self.reactions, background) if self.active else ({}, Counter(), Counter())
        self.n_bg = len(background) or 1
        self.idf = {}
        for fs in background:
            for f in set(fs):
                self.idf[f] = self.idf.get(f, 0) + 1
        self.idf = {f: math.log((self.n_bg + 1) / (c + 0.5)) for f, c in self.idf.items()}

    def score(self, feats):
        """→ (0–100 or None, [reasons])"""
        if not self.active:
            return None, []
        parts = [(self.w[f], f) for f in feats if f in self.w and abs(self.w[f]) > 0.05]
        if not parts:
            return 50, []
        raw = sum(v for v, _ in parts) / math.sqrt(len(parts))
        top = sorted(parts, key=lambda x: -abs(x[0]))[:3]
        return round(50 + 50 * math.tanh(raw / 2)), [self.reason(f, v) for v, f in top]

    def reason(self, f, v):
        kind, name = f.split(":", 1)
        n = sum(1 for x in self.reactions if f in (x.get("f") or []) and SIGNAL[x["r"]] * v > 0)
        verb = "you liked / applied to" if v > 0 else "you passed on"
        return {"sign": "+" if v > 0 else "−", "text": f"{LABEL.get(kind, kind)} “{name}”", "detail": f"{verb} {n} like this",
                "w": round(v, 2)}

    def summary(self, top=8):
        """What it has learned, for the Status / learning panel."""
        items = sorted(self.w.items(), key=lambda kv: -kv[1])
        return {"active": self.active, "reactions": len(self.reactions),
                "likes": [self.reason(f, v) for f, v in items[:top] if v > 0.05],
                "dislikes": [self.reason(f, v) for f, v in items[::-1][:top] if v < -0.05],
                "needs": max(0, MIN_REACTIONS - len(self.reactions))}

    def similar(self, feats, candidates, k=6):
        """candidates: [(id, feats)] → top-k ids by idf-weighted overlap (cosine)."""
        def vec(fs):
            return {f: self.idf.get(f, math.log(self.n_bg + 1)) * (2 if f[:4] in ("skil", "fam:", "spec") else 1) for f in fs}
        a = vec(feats)
        na = math.sqrt(sum(v * v for v in a.values())) or 1
        out = []
        for jid, fs in candidates:
            b = vec(fs)
            dot = sum(a[f] * b[f] for f in a.keys() & b.keys())
            if dot:
                out.append((dot / (na * (math.sqrt(sum(v * v for v in b.values())) or 1)), jid))
        return [j for _, j in sorted(out, reverse=True)[:k]]


def holdout_check(reactions, background_jobs):
    """Honest self-check on Daksh's own reactions: leave one reaction out, learn from the rest, and see where the
    left-out job ranks among all current jobs (percentile, 100 = top). Liked jobs should rank high, disliked low.
    Needs ≥ 10 reactions; returns None before that."""
    rs = [x for x in reactions if x.get("r") in SIGNAL and x.get("f")]
    if len(rs) < 10:
        return None
    bg = [j["f"] for j in background_jobs]
    pos_pct, neg_pct = [], []
    for i, x in enumerate(rs):
        m = Model(rs[:i] + rs[i + 1:], bg)
        if not m.active:
            continue
        s, _ = m.score(x["f"])
        others = [m.score(j["f"])[0] for j in background_jobs[:600]]
        pct = 100 * sum(1 for o in others if o is not None and o < s) / max(1, len(others))
        (pos_pct if SIGNAL[x["r"]] > 0 else neg_pct).append(pct)
    avg = lambda xs: round(sum(xs) / len(xs)) if xs else None
    return {"n": len(rs), "liked_rank_pct": avg(pos_pct), "disliked_rank_pct": avg(neg_pct),
            "meaning": "Where a held-out job you liked would rank (100 = top of the list). Random would be ~50."}
