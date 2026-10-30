"""AI calls can't stall a scheduled run: a per-run time budget.  python tests/test_llm_budget.py"""
import os
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.update(GEMINI_API_KEY="fake", AI_BUDGET_SECONDS="3", GEMINI_PAUSE="0")
os.environ.pop("GROQ_API_KEY", None)
from common import llm  # noqa: E402

FAILS = []


def chk(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        FAILS.append(m)


calls = {"n": 0}


class Models:
    def generate_content(self, **k):
        calls["n"] += 1
        raise RuntimeError("429 RESOURCE_EXHAUSTED: quota per minute, retry in 60s")


llm._client = types.SimpleNamespace(models=Models())
llm._models = ["gemini-a", "gemini-b", "gemini-c"]
t0 = time.time()
outs = [llm.ask_json("note for gig %d" % i) for i in range(15)]
took = time.time() - t0
chk(all(o is None for o in outs), "rate-limited AI gives no note (the gig still shows, just without a note)")
chk(took < 6, f"15 rate-limited calls finish inside the budget instead of ~30 min of back-off (took {took:.1f}s)")
chk(llm.exhausted(), "after the budget the radar is told AI is exhausted, so it stops asking")
print("\nFAILURES:", FAILS)
sys.exit(1 if FAILS else 0)
