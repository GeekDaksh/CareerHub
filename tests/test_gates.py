"""Every gate is tested with deliberately broken input, to prove it really stops bad data.
A gate that never fails might be asleep.   Run: python tests/test_gates.py"""
import copy
import json
import os
import shutil
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config as C  # noqa: E402
from common import gates  # noqa: E402
from common.config_check import ConfigError, validate  # noqa: E402

FAILS = []


def chk(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        FAILS.append(m)


def raises(fn, exc, gate=None):
    try:
        fn()
    except exc as e:
        return gate is None or getattr(e, "gate", None) == gate
    return False


# ---------------------------------------------------------------- G0 config gate
def cfg_with(**over):
    m = types.SimpleNamespace(**{k: copy.deepcopy(getattr(C, k)) for k in dir(C) if k.isupper()})
    for k, v in over.items():
        setattr(m, k, v)
    return m


validate()
chk(True, "G0: real config.py passes")
chk(raises(lambda: validate(cfg_with(SHIELD={**C.SHIELD, "word_boundary": True})), ConfigError),
    "G0: typo in a SHIELD key ('word_boundary') is rejected")
s = dict(C.SHIELD); s.pop("negation_guard")
chk(raises(lambda: validate(cfg_with(SHIELD=s)), ConfigError), "G0: missing SHIELD key is rejected")
chk(raises(lambda: validate(cfg_with(LEVEL={**C.LEVEL, "entry_words_win": "yes"})), ConfigError),
    "G0: wrong type in LEVEL ('yes' instead of True) is rejected")
chk(raises(lambda: validate(cfg_with(SHIELD={**C.SHIELD, "weak_signal_combo": 9})), ConfigError),
    "G0: weak_signal_combo out of range is rejected")

# ---------------------------------------------------------------- radar output gates
def gig(i, **over):
    g = {"id": f"g{i}", "title": f"Python gig {i}", "url": f"https://www.freelancer.com/projects/{i}",
         "source": "Freelancer.com", "visible": True, "score": 50, "scam": [], "category": "tech"}
    g.update(over)
    return g


def role(i, **over):
    r = {"id": f"r{i}", "title": f"ML Intern {i}", "url": f"https://boards.greenhouse.io/x/jobs/{i}",
         "source_kind": "ats", "score": 60, "trust": {"verdict": "verified"}, "level": "entry"}
    r.update(over)
    return r


good = [gig(i) for i in range(12)]
chk(gates.check_items("gigs", good, prev_visible=12)["visible"] == 12, "gates: a clean list passes")
chk(gates.check_items("roles", [role(i) for i in range(5)], prev_visible=5)["checked"] == 5, "gates: clean roles pass")

cases = [
    ("schema", "gigs", good[:-1] + [{k: v for k, v in gig(99).items() if k != "url"}], "missing url"),
    ("schema", "gigs", good[:-1] + [gig(99, score="high")], "score is text"),
    ("schema", "gigs", good[:-1] + [gig(99, score=True)], "score is True (a bool is not a number here)"),
    ("schema", "gigs", {"gigs": good}, "not a list"),
    ("links", "gigs", good[:-1] + [gig(99, url="javascript:alert(document.cookie)")], "javascript: link"),
    ("links", "gigs", good[:-1] + [gig(99, url="data:text/html,<script>x</script>")], "data: link"),
    ("links", "roles", [role(1, url="file:///etc/passwd")], "file: link"),
    ("links", "gigs", good[:-1] + [gig(99, url="www.no-scheme.com/job")], "link without https://"),
    ("unique", "gigs", good + [gig(3)], "duplicate id"),
    ("safety", "gigs", good[:-1] + [gig(99, scam=["asks you to pay a fee or deposit"])], "scam marked visible"),
    ("safety", "roles", [role(1, trust={"verdict": "risky"})], "risky role in the shown list"),
]
for gate, kind, items, what in cases:
    chk(raises(lambda: gates.check_items(kind, items, prev_visible=len(good)), gates.GateFailed, gate),
        f"gate '{gate}' stops: {what}")

few = [gig(i) for i in range(2)] + [gig(i, visible=False) for i in range(2, 40)]
chk(raises(lambda: gates.check_items("gigs", few, prev_visible=40), gates.GateFailed, "collapse"),
    "gate 'collapse' stops: visible gigs 40 -> 2 in one run")
chk(gates.check_items("gigs", few, prev_visible=5)["visible"] == 2, "collapse is not judged on tiny lists (<10 before)")
chk(gates.check_items("gigs", [gig(i, visible=False) for i in range(3)], prev_visible=None)["visible"] == 0,
    "first run (no previous file) has no collapse check")

# ---------------------------------------------------------------- radar keeps the last good file
work = os.path.join(ROOT, "tests", ".work", "gates")
shutil.rmtree(work, ignore_errors=True)
os.makedirs(os.path.join(work, "gigs"))
last_good = {"updated": 1, "gigs": good}
json.dump(last_good, open(os.path.join(work, "gigs", "gigs.json"), "w"))
os.environ["DATA_DIR"] = work
import importlib  # noqa: E402
from gigs import radar  # noqa: E402
importlib.reload(radar)
broken = good[:-1] + [gig(99, url="javascript:alert(1)")]
radar.collect = lambda state, health: [dict(g, posted=None, desc="", company="X", work_type="freelance",
                                            pay_type="fixed", budget_min=None, budget_max=None, currency="INR")
                                       for g in broken]
radar.ai_note = lambda g: None
try:
    radar.run()
except Exception as e:  # the gate must not crash the scheduled run
    chk(False, f"radar crashed instead of keeping the last file: {e!r}")
after = json.load(open(os.path.join(work, "gigs", "gigs.json")))
health = json.load(open(os.path.join(work, "gigs", "health.json")))
chk(after == last_good, "radar: a failed gate leaves the last good gigs.json untouched")
chk(health.get("Output check", {}).get("ok") is False and "links" in health["Output check"]["error"],
    "radar: the failure is recorded in health.json for the Status tab")

# ---------------------------------------------------------------- G1 evaluation data gate (only if EMSCAD is present)
from eval import harness as H  # noqa: E402
if os.path.exists(H.DATA):
    tampered = os.path.join(work, "emscad.csv")
    with open(H.DATA, "rb") as f, open(tampered, "wb") as g:
        g.write(f.read().replace(b",1\n", b",0\n", 3))
    real = H.DATA
    H.DATA = tampered
    chk(raises(lambda: H.load("train"), H.GateError), "G1: a changed EMSCAD file (3 labels flipped) is refused")
    H.DATA = real
    chk(raises(lambda: H.load("validation"), H.GateError), "G1: unknown split name is refused")
    hard = H.HARD
    H.HARD = os.path.join(work, "hard.jsonl")
    open(H.HARD, "w").write(open(hard).read().replace('"scam": true', '"scam": false', 1))
    chk(raises(lambda: H.load_hard(), H.GateError), "G1: an edited frozen hard set is refused")
    H.HARD = hard
else:
    print("SKIP G1 data gate tests (run: bash eval/fetch_emscad.sh)")

print("\nFAILURES:", FAILS)
sys.exit(1 if FAILS else 0)
