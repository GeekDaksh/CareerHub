"""Score careers/eligible.py on the frozen 50 hand-labelled cases.  python -m eval.careers.measure_eligibility [--errors]"""
import hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from careers.eligible import check
from eval.careers.measure import boot

HERE = os.path.dirname(os.path.abspath(__file__))
want = open(os.path.join(HERE, "eligibility.sha256")).read().split()[0]
raw = open(os.path.join(HERE, "eligibility.jsonl"), "rb").read()
if hashlib.sha256(raw).hexdigest() != want:
    raise SystemExit("GATE: eligibility set changed — it is frozen")
G = [json.loads(l) for l in raw.decode().splitlines()]
res = [(g, check(g, "bachelor", 2027)) for g in G]
caught = [not r["ok"] for g, r in res if not g["gold_eligible"]]          # not-eligible jobs hidden
wrong = [not r["ok"] for g, r in res if g["gold_eligible"]]               # eligible jobs wrongly hidden
acc = [r["ok"] == g["gold_eligible"] for g, r in res]
for name, flags, meaning in [("accuracy", acc, "eligible / not eligible right"),
                             ("not_eligible_caught", caught, "jobs you can't apply to that get hidden"),
                             ("eligible_wrongly_hidden", wrong, "jobs you CAN apply to that get hidden (lower is better)")]:
    v = sum(flags) / len(flags)
    print(f"{name:24s} {v:.3f} n={len(flags):2d} 95% {boot(flags)} — {meaning}")
if "--errors" in sys.argv:
    for g, r in res:
        if r["ok"] != g["gold_eligible"]:
            print("ERR", g["gold_eligible"], "|", g["title"][:60], "|", r["why"], "|", r["evidence"][:120])
