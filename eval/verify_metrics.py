"""Check our metric code against scikit-learn (independent reference). Differences must be exactly 0."""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sklearn.metrics import recall_score, confusion_matrix
from eval import harness as H

rnd = random.Random(1)
worst = 0.0
for trial in range(200):
    n = rnd.randint(30, 400)
    rows = [{"fraud": rnd.random() < 0.2, "exp": rnd.choice(["Entry level", "Internship", "Mid-Senior level", "Director", "Associate", ""])} for _ in range(n)]
    preds = [{"blocked": rnd.random() < 0.3, "shown": rnd.random() < 0.6} for _ in range(n)]
    m = H.metrics(rows, preds)
    y = [r["fraud"] for r in rows]; p = [q["blocked"] for q in preds]
    if any(y):
        worst = max(worst, abs(m["catch_rate"]["value"] - recall_score(y, p, zero_division=0)))
    tn, fp, fn, tp = confusion_matrix(y, p, labels=[False, True]).ravel()
    if tn + fp:
        worst = max(worst, abs(m["false_block"]["value"] - fp / (tn + fp)))
    sen = [(r, q) for r, q in zip(rows, preds) if r["exp"] in H.SENIOR_LABELS and not r["fraud"]]
    if sen:   # senior leak = recall of "shown" among senior jobs
        worst = max(worst, abs(m["senior_leak"]["value"] - recall_score([True] * len(sen), [q["shown"] for _, q in sen], zero_division=0)))
    ent = [(r, q) for r, q in zip(rows, preds) if r["exp"] in H.ENTRY_LABELS and not r["fraud"]]
    if ent:
        worst = max(worst, abs(m["entry_loss"]["value"] - recall_score([True] * len(ent), [not q["shown"] for _, q in ent], zero_division=0)))
print(f"max difference vs scikit-learn over 200 random cases: {worst}")
assert worst == 0.0
