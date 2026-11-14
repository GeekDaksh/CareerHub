"""Test every candidate careers site for real (run on GitHub's servers, which can reach them).
Prints GitHub annotations so results can be read through the API:  python -m careers.probe
"""
import json
import sys
import time

from careers import registry as R, sources as S


def dump(path):
    """Collect full results from every working site and save them (public job data only) for building the
    classifier and its frozen test set."""
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    health = {}
    jobs = S.collect([c for c in R.CANDIDATES if c["ats"] != "link"], health, budget_s=1500)
    with open(path, "w") as f:
        for j in jobs:
            f.write(json.dumps({k: j.get(k) for k in ("id", "company", "company_tier", "title", "location", "kind_hint",
                                                      "url", "posted", "desc")}) + "\n")
    print(f"::notice title=dump::{len(jobs)} jobs from {sum(h['ok'] for h in health.values())} sites; "
          + "; ".join(f"{k} {v['count']}" for k, v in health.items()))


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--dump":
        dump(sys.argv[2])
        return 0
    res = []
    for c in R.CANDIDATES:
        if c["ats"] == "link":
            continue
        fn = S.CONNECTORS[c["ats"]]
        t = time.time()
        try:
            kw = {"queries": ["machine learning", "intern"]} if c["ats"] in ("amazon", "google", "eightfold", "workday") else {}
            jobs = fn(c, **kw)
            sample = jobs[0] if jobs else {}
            res.append({"name": c["name"], "ok": True, "india": len(jobs), "secs": round(time.time() - t, 1),
                        "sample": f"{sample.get('title', '')[:50]} | {sample.get('location', '')[:40]} | desc {len(sample.get('desc', ''))}"})
        except Exception as e:
            res.append({"name": c["name"], "ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}",
                        "secs": round(time.time() - t, 1)})
    for i in range(0, len(res), 5):   # GitHub keeps 10 notices per step: 5 companies per notice
        chunk = res[i:i + 5]
        msg = " || ".join(f"{r['name']}: " + (f"OK {r['india']} India jobs ({r['secs']}s) e.g. {r['sample']}" if r["ok"]
                                                 else f"FAIL {r['error']}") for r in chunk)
        print(f"::notice title=probe {i // 5 + 1}::{msg}")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
