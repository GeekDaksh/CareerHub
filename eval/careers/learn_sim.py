"""Does the 'For you' learner pick up a taste from a few reactions? Simulated users on REAL jobs (the 2,002-job
sample). Each simulated user has a hidden rule ("likes X, dislikes Y"); they react to N random jobs from one half,
the learner ranks the OTHER half, and we score the ranking with AUC (1.0 = every liked job above every other;
0.5 = random). 30 random splits per setting → mean and 95% range.
Honest limit: simulated users' tastes are rules over the same features the learner sees, so this shows the learner
CAN learn such tastes from few clicks — not that it matches Daksh. The in-app self-check (learn.holdout_check) is
the real-user test once he has 10+ reactions.
   python -m eval.careers.learn_sim path/to/jobs.jsonl"""
import json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from careers import classify as K, learn as L, match as M, registry

TIER = {c["name"]: c["tier"] for c in registry.CANDIDATES}
PERSONAS = {
    "GenAI/CV fresher": lambda j: j["family"] in ("GenAI / LLM", "Computer Vision", "ML Engineer / Applied Scientist") and j["fresher_fit"] in ("fits", "stretch", "check"),
    "Hardware at big tech": lambda j: j["family"] == "Embedded / Hardware",
    "Data roles": lambda j: j["family"] in ("Data Science", "Data Analytics", "Data Engineering") and j["fresher_fit"] != "too senior",
}


def auc(scores, truth):
    pos = [s for s, t in zip(scores, truth) if t]
    neg = [s for s, t in zip(scores, truth) if not t]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def main(path):
    jobs = []
    for line in open(path):
        j = json.loads(line)
        j.update(K.classify(j))
        j["skills"] = M.job_skills(j)
        j["company_tier"] = TIER.get(j["company"], j.get("company_tier"))
        if j["family"] != "Non-technical":
            j["f"] = L.features(j)
            jobs.append(j)
    print(f"{len(jobs)} technical jobs")
    rows = []
    for name, rule in PERSONAS.items():
        base_rate = sum(map(rule, jobs)) / len(jobs)
        for n in (5, 10, 20, 40):
            res = []
            for seed in range(30):
                r = random.Random(seed)
                idx = list(range(len(jobs)))
                r.shuffle(idx)
                train, test = [jobs[i] for i in idx[: len(idx) // 2]], [jobs[i] for i in idx[len(idx) // 2:]]
                # the user sees random jobs; to make sure they see some they like, half come from their taste
                likes = [j for j in train if rule(j)]
                seen = r.sample(likes, min(len(likes), n // 2)) + r.sample(train, n - min(len(likes), n // 2))
                reacts = [{"r": "like" if rule(j) else "dislike", "f": j["f"]} for j in seen]
                m = L.Model(reacts, [j["f"] for j in train])
                sc = [m.score(j["f"])[0] or 50 for j in test]
                a = auc(sc, [rule(j) for j in test])
                if a is not None:
                    res.append(a)
            res.sort()
            rows.append((name, round(base_rate, 2), n, round(sum(res) / len(res), 3), res[int(.025 * len(res))], res[int(.975 * len(res)) - 1]))
            print(f"{name:22s} share {rows[-1][1]:.2f}  after {n:2d} reactions: AUC {rows[-1][3]:.3f}  95% [{rows[-1][4]:.2f}, {rows[-1][5]:.2f}]  (random 0.5)")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learn_sim.json")
    json.dump([dict(zip(["persona", "share", "reactions", "auc", "lo", "hi"], r)) for r in rows], open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
