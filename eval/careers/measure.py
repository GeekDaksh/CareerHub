"""Score careers/classify.py against the frozen gold set. Prints metric cards (value, n, 95% bootstrap range).
   python -m eval.careers.measure [--errors]"""
import hashlib, json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from careers.classify import classify, TECH_FAMILIES_ML

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD = os.path.join(HERE, "gold.jsonl")
FRESH = {"Intern", "New grad / entry"}


def load_gold():
    want = open(os.path.join(HERE, "gold.sha256")).read().split()[0]
    got = hashlib.sha256(open(GOLD, "rb").read()).hexdigest()
    if got != want:
        raise SystemExit(f"GATE: gold set changed (sha {got[:12]} != {want[:12]}). It is frozen; do not edit it.")
    return [json.loads(l) for l in open(GOLD)]


def boot(flags, n=2000, seed=7):
    if not flags:
        return [0, 0]
    r = random.Random(seed)
    xs = sorted(sum(r.choice(flags) for _ in flags) / len(flags) for _ in range(n))
    return [round(xs[int(.025 * n)], 3), round(xs[int(.975 * n)], 3)]


def card(name, flags, meaning):
    v = sum(flags) / len(flags) if flags else 0
    return {"metric": name, "value": round(v, 3), "n": len(flags), "ci95": boot(flags), "meaning": meaning}


def run(show_errors=False):
    gold = load_gold()
    fam, lev, mlflag, nontech, fresh_found, fresh_prec, errs = [], [], [], [], [], [], []
    for g in gold:
        c = classify(g)
        fam.append(c["family"] == g["gold_family"])
        lev.append(c["level"] == g["gold_level"])
        mlflag.append((c["family"] in TECH_FAMILIES_ML) == (g["gold_family"] in TECH_FAMILIES_ML))
        nontech.append((c["family"] == "Non-technical") == (g["gold_family"] == "Non-technical"))
        if g["gold_level"] in FRESH:
            fresh_found.append(c["level"] in FRESH)
        if c["level"] in FRESH:
            fresh_prec.append(g["gold_level"] in FRESH)
        if c["family"] != g["gold_family"] or c["level"] != g["gold_level"]:
            errs.append((g["title"][:60], g["gold_family"], c["family"], g["gold_level"], c["level"], c["level_evidence"]))
    cards = [card("family_accuracy", fam, "role family matches the hand label"),
             card("level_accuracy", lev, "level matches the hand label"),
             card("ml_flag_accuracy", mlflag, "'is an ML/AI role' yes/no is right"),
             card("nontech_accuracy", nontech, "'non-technical' yes/no is right"),
             card("fresher_recall", fresh_found, "fresher jobs (intern/new grad) the app marks as fresher"),
             card("fresher_precision", fresh_prec, "jobs the app marks fresher that really are")]
    for c in cards:
        print(f"{c['metric']:18s} {c['value']:.3f}  n={c['n']:3d}  95% {c['ci95']}  — {c['meaning']}")
    if show_errors:
        for e in errs:
            print(" | ".join(map(str, e)))
    return cards


if __name__ == "__main__":
    out = run("--errors" in sys.argv)
    if "--save" in sys.argv:
        json.dump(out, open(os.path.join(HERE, sys.argv[sys.argv.index("--save") + 1]), "w"), indent=1)
