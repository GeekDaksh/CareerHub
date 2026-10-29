"""Run the evaluation.
  python -m eval.run_eval                 # train split (safe, use as often as you like)
  python -m eval.run_eval --baseline      # train split with every switch OFF, saves eval/baseline_train.json
  python -m eval.run_eval --final         # TEST split — run once at the very end; every run is logged
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C  # noqa: E402
from common.config_check import validate  # noqa: E402
from common import levels  # noqa: E402
from eval import harness as H  # noqa: E402

OFF_SHIELD = {k: (0 if isinstance(v, int) and not isinstance(v, bool) else False) for k, v in C.SHIELD.items()}
OFF_LEVEL = {k: False for k in C.LEVEL}
EV = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--final", action="store_true", help="evaluate on the held-out TEST split (logged)")
    ap.add_argument("--feedback", metavar="LESSONS_JSON", help="also score the level filter on your own 'wrong level' reports")
    a = ap.parse_args()
    validate()
    split = "test" if a.final else "train"
    shield, lvl = (OFF_SHIELD, OFF_LEVEL) if a.baseline else (C.SHIELD, C.LEVEL)
    rows = H.load(split)
    preds = H.predict(rows, shield, lvl)
    m = H.metrics(rows, preds)
    base_path = os.path.join(EV, f"baseline_{split}.json")
    if a.baseline:
        json.dump({"metrics": m, "shield": shield, "level": lvl}, open(base_path, "w"), indent=1)
    elif os.path.exists(base_path):
        bj = json.load(open(base_path))
        paired = H.paired_delta(rows, H.predict(rows, bj["shield"], bj["level"]), preds)
        H.compare(m, bj["metrics"], paired)
    cal = H.calibration(rows, preds, shield)
    hard = H.hard_eval(shield, lvl)
    print(f"== {split.upper()} split · {len(rows)} posts · {'baseline (all switches off)' if a.baseline else 'current config'}")
    print(H.fmt(m))
    print(H.fmt_calibration(cal))
    if not a.final and not a.baseline:
        json.dump({"metrics": m, "calibration": cal, "shield": shield, "level": lvl},
                  open(os.path.join(EV, "current_train.json"), "w"), indent=1)
    hs = sum(h["scam_ok"] for h in hard); hl = sum(h["level_ok"] for h in hard)
    print(f"India hard set: scam decisions right {hs}/{len(hard)} · level decisions right {hl}/{len(hard)}")
    for h in hard:
        if not (h["scam_ok"] and h["level_ok"]):
            print(f"   ✗ {h['id']} {h['title']!r}: blocked={h['blocked']} level={h['level']} {h['reasons']}")
    if a.feedback and not a.final:     # personal set: a separate view, never mixed into EMSCAD numbers
        cases = json.load(open(a.feedback)).get("level_cases", [])
        ok = sum((levels.level(c["title"], "", lvl) != "senior") == (c["truth"] == "entry") for c in cases)
        print(f"Your level reports: {ok}/{len(cases)} now decided the way you said" if cases else "No level reports yet")
    if a.final:
        print("Learning: off — the evaluation never loads lessons (common/feedback.py is not imported here)")
        with open(os.path.join(EV, "test_runs.log"), "a") as f:
            f.write(json.dumps({"at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                                "shield": shield, "level": lvl, "metrics": m}) + "\n")
        json.dump({"metrics": m, "calibration": cal, "shield": shield, "level": lvl, "hard": hard},
                  open(os.path.join(EV, "final_test.json"), "w"), indent=1)
        print("Logged to eval/test_runs.log")


if __name__ == "__main__":
    main()
