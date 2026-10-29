"""Improvement loop — one command, train split only, deterministic, resumable.
Each iteration: EVALUATE current config → DIAGNOSE mistakes → PROPOSE one change from the rulebook →
JUDGE with the rule declared in eval/OBJECTIVE.md → LOG (eval/loop_log.jsonl + eval/LOOP.md).

  python -m eval.loop            # runs until the rulebook is exhausted
  python -m eval.loop --fresh    # archive the old log and start over
"""
import argparse
import copy
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import levels, trust  # noqa: E402
from eval import harness as H  # noqa: E402
from eval.run_eval import OFF_LEVEL, OFF_SHIELD  # noqa: E402

EV = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(EV, "loop_log.jsonl")
MD = os.path.join(EV, "LOOP.md")

# Rulebook: bug fixes first, then new detectors, then thresholds. 'fixes' = the mistake type each one targets.
RULEBOOK = [
    ("shield", "word_boundaries", True, "bugfix", "false block: partial-word match"),
    ("shield", "chat_contact_only", True, "bugfix", "false block: WhatsApp/Telegram mentioned, not used as contact"),
    ("shield", "negation_guard", True, "bugfix", "false block: 'no fee' / 'company covers the fee'"),
    ("shield", "normalize_text", True, "detector", "missed scam: disguised words"),
    ("shield", "money_transfer_rules", True, "detector", "missed scam: money transfer / reshipping"),
    ("shield", "wfh_money_rules", True, "detector", "missed scam: earn-from-home promise"),
    ("shield", "personal_email_cv", True, "detector", "missed scam: CV to personal email"),
    ("shield", "weak_signal_combo", [2, 3, 4, 5], "threshold", "missed scam: several weak signs"),
    ("level", "staff_needs_role", True, "bugfix", "entry loss: 'Staff' as a noun"),
    ("level", "assistant_not_senior", True, "bugfix", "entry loss: 'Assistant Manager'"),
    ("level", "entry_words_win", True, "bugfix", "entry loss: junior word beside a senior word"),
    ("level", "years_patterns_ext", True, "detector", "senior leak: years written differently"),
    ("level", "senior_words_ext", True, "detector", "senior leak: other senior title words"),
    ("level", "senior_from_desc", True, "detector", "senior leak: senior hints in the text"),
    ("level", "hide_not_stated", True, "threshold", "senior leak: level not stated"),
]


# ---------------------------------------------------------------- evaluation per filter
def eval_shield(rows, cfg):
    out = []
    for r in rows:
        out.append(bool(trust.scam_reasons(f"{r['title']}\n{r['text']}", cfg)))
    return out


def eval_level(rows, cfg):
    return [levels.level(r["title"], r["level_text"], cfg) != "senior" for r in rows]


def shield_stats(rows, blocked, half=None):
    sel = [(r, b) for r, b in zip(rows, blocked) if half is None or r["half"] == half]
    sc = [b for r, b in sel if r["fraud"]]
    lg = [b for r, b in sel if not r["fraud"]]
    return {"catch": sum(sc) / len(sc), "false_block": sum(lg) / len(lg)}


def level_stats(rows, shown, half=None):
    sel = [(r, s) for r, s in zip(rows, shown) if (half is None or r["half"] == half) and not r["fraud"]]
    sen = [s for r, s in sel if r["exp"] in H.SENIOR_LABELS]
    ent = [not s for r, s in sel if r["exp"] in H.ENTRY_LABELS]
    leak, loss = sum(sen) / len(sen), sum(ent) / len(ent)
    return {"senior_leak": leak, "entry_loss": loss, "balanced_error": (leak + loss) / 2}


def hard_ok(family, cfg_shield, cfg_level):
    res = H.hard_eval(cfg_shield, cfg_level)
    return {h["id"]: (h["scam_ok"] if family == "shield" else h["level_ok"]) for h in res}


# ---------------------------------------------------------------- diagnosis
def diagnose(rows, blocked, shown, cfg_shield, cfg_level):
    d = {"false_blocks_by_reason": {}, "missed_scams": 0, "entry_loss_by_cause": {}, "senior_leak_not_stated": 0}
    for r, b in zip(rows, blocked):
        if r["fraud"] and not b:
            d["missed_scams"] += 1
        if not r["fraud"] and b:
            for why in trust.scam_reasons(f"{r['title']}\n{r['text']}", cfg_shield):
                d["false_blocks_by_reason"][why] = d["false_blocks_by_reason"].get(why, 0) + 1
    for r, s in zip(rows, shown):
        if r["fraud"]:
            continue
        if r["exp"] in H.ENTRY_LABELS and not s:
            m = levels.SENIOR.search(r["title"])
            cause = ("title word: " + m.group(0).lower()) if m else "years / text"
            d["entry_loss_by_cause"][cause] = d["entry_loss_by_cause"].get(cause, 0) + 1
        if r["exp"] in H.SENIOR_LABELS and s and levels.level(r["title"], r["level_text"], cfg_level) == "not stated":
            d["senior_leak_not_stated"] += 1
    d["entry_loss_by_cause"] = dict(sorted(d["entry_loss_by_cause"].items(), key=lambda x: -x[1])[:6])
    return d


# ---------------------------------------------------------------- judging (eval/OBJECTIVE.md)
def judge_shield(rows, base_b, new_b, base, new, kind, hard_before, hard_after):
    halves = {h: (shield_stats(rows, base_b, h), shield_stats(rows, new_b, h)) for h in "AB"}
    gained = sum(1 for r, a, b in zip(rows, base_b, new_b) if r["fraud"] and b and not a)
    lost = sum(1 for r, a, b in zip(rows, base_b, new_b) if r["fraud"] and a and not b)
    new_fb = sum(1 for r, a, b in zip(rows, base_b, new_b) if not r["fraud"] and b and not a)
    fixed_fb = sum(1 for r, a, b in zip(rows, base_b, new_b) if not r["fraud"] and a and not b)
    regress = [k for k, ok in hard_before.items() if ok and not hard_after[k]]
    guard = new["false_block"] <= 0.01 and new["false_block"] <= BASE["false_block"] + 0.003 and not regress
    d_catch = new["catch"] - base["catch"]
    d_fb = new["false_block"] - base["false_block"]
    primary_ok = (d_catch >= 0.01 and all(halves[h][1]["catch"] > halves[h][0]["catch"] for h in "AB")
                  and gained - lost > new_fb - fixed_fb)
    bugfix_ok = (kind == "bugfix" and d_fb <= -0.001 and d_catch >= -0.005
                 and all(halves[h][1]["false_block"] < halves[h][0]["false_block"] for h in "AB"))
    accept = guard and (primary_ok or bugfix_ok)
    why = []
    if regress:
        why.append(f"hard set got worse: {regress}")
    if not guard and not regress:
        why.append(f"false blocks {new['false_block']*100:.2f}% break the guardrail")
    if accept:
        why.append("primary rule" if primary_ok else "bug-fix rule (fewer false blocks)")
    elif guard:
        why.append(f"gain too small or not on both halves (catch {d_catch*100:+.2f} pp, false blocks {d_fb*100:+.2f} pp)")
    return accept, "; ".join(why), {"scams_newly_caught": gained, "scams_lost": lost,
                                    "real_posts_newly_blocked": new_fb, "real_posts_unblocked": fixed_fb,
                                    "hard_regressions": regress,
                                    "halves": {h: {"before": halves[h][0], "after": halves[h][1]} for h in "AB"}}


def judge_level(rows, base_s, new_s, base, new, hard_before, hard_after):
    halves = {h: (level_stats(rows, base_s, h), level_stats(rows, new_s, h)) for h in "AB"}
    fixed = broken = 0
    for r, a, b in zip(rows, base_s, new_s):
        if r["fraud"] or a == b:
            continue
        good_after = (b and r["exp"] in H.ENTRY_LABELS) or (not b and r["exp"] in H.SENIOR_LABELS)
        if r["exp"] in H.ENTRY_LABELS | H.SENIOR_LABELS:
            fixed += good_after
            broken += not good_after
    regress = [k for k, ok in hard_before.items() if ok and not hard_after[k]]
    guard = new["entry_loss"] <= 0.15 and new["senior_leak"] <= 0.35 and not regress
    d = new["balanced_error"] - base["balanced_error"]
    primary_ok = (d <= -0.005 and fixed > broken
                  and all(halves[h][1]["balanced_error"] < halves[h][0]["balanced_error"] for h in "AB"))
    accept = guard and primary_ok
    why = []
    if regress:
        why.append(f"hard set got worse: {regress}")
    if not guard and not regress:
        why.append(f"guardrail broken (entry loss {new['entry_loss']*100:.1f}%, senior leak {new['senior_leak']*100:.1f}%)")
    if accept:
        why.append("primary rule")
    elif guard:
        why.append(f"balanced error change {d*100:+.2f} pp too small / not on both halves / fixes ≤ breaks")
    return accept, "; ".join(why), {"fixed": fixed, "broken": broken, "hard_regressions": regress,
                                    "halves": {h: {"before": halves[h][0], "after": halves[h][1]} for h in "AB"}}


def pct(d):
    return {k: round(v * 100, 2) for k, v in d.items()}


def write_md(entries):
    lines = ["# Improvement loop log (train split only)", "",
             "Each row is one proposed change, judged by the rule in `OBJECTIVE.md`. Rejected changes stay in the log.", "",
             "| # | Filter | Change | Type | Before | After | Decision | Why |", "|---|---|---|---|---|---|---|---|"]
    for e in entries:
        b, a = e["before"], e["after"]
        fmt = lambda m: ", ".join(f"{k} {v}%" for k, v in m.items())
        lines.append(f"| {e['iter']} | {e['family']} | `{e['key']}={e['value']}` | {e['kind']} | {fmt(b)} | {fmt(a)} | "
                     f"**{'ACCEPT' if e['accepted'] else 'reject'}** | {e['why']} |")
    open(MD, "w").write("\n".join(lines) + "\n")


BASE = {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args()
    if a.fresh and os.path.exists(LOG):
        shutil.move(LOG, LOG.replace(".jsonl", f".archived-{int(time.time())}.jsonl"))
    rows = H.load("train")                       # loop never touches the test split
    entries = [json.loads(l) for l in open(LOG)] if os.path.exists(LOG) else []
    cfg_s, cfg_l = copy.deepcopy(OFF_SHIELD), copy.deepcopy(OFF_LEVEL)
    for e in entries:                            # resume: replay accepted decisions
        if e["accepted"]:
            (cfg_s if e["family"] == "shield" else cfg_l)[e["key"]] = e["value"]
    tries = {}
    for e in entries:
        tries[(e["key"], json.dumps(e["value"]))] = tries.get((e["key"], json.dumps(e["value"])), 0) + 1

    b_blocked, b_shown = eval_shield(rows, cfg_s), eval_level(rows, cfg_l)
    BASE.update(shield_stats(rows, eval_shield(rows, OFF_SHIELD)))
    queue = list(RULEBOOK)
    it = len(entries)
    while queue:
        fam, key, values, kind, fixes = queue.pop(0)
        cfg = cfg_s if fam == "shield" else cfg_l
        vals = values if isinstance(values, list) else [values]
        vals = [v for v in vals if cfg.get(key) != v and tries.get((key, json.dumps(v)), 0) < 1 + 2]
        if not vals:
            continue
        diag = diagnose(rows, b_blocked, b_shown, cfg_s, cfg_l)
        best = None
        for v in vals:                           # thresholds: sweep and keep the best that passes
            trial = dict(cfg, **{key: v})
            if fam == "shield":
                nb = eval_shield(rows, trial)
                before, after = shield_stats(rows, b_blocked), shield_stats(rows, nb)
                ok, why, ev = judge_shield(rows, b_blocked, nb, before, after, kind,
                                           hard_ok("shield", cfg_s, cfg_l), hard_ok("shield", trial, cfg_l))
            else:
                nb = eval_level(rows, trial)
                before, after = level_stats(rows, b_shown), level_stats(rows, nb)
                ok, why, ev = judge_level(rows, b_shown, nb, before, after,
                                          hard_ok("level", cfg_s, cfg_l), hard_ok("level", cfg_s, trial))
            score = (after["catch"] if fam == "shield" else -after["balanced_error"])
            if best is None or (ok, score) > (best[0], best[1]):
                best = (ok, score, v, nb, before, after, why, ev)
        ok, _, v, nb, before, after, why, ev = best
        it += 1
        tries[(key, json.dumps(v))] = tries.get((key, json.dumps(v)), 0) + 1
        entry = {"iter": it, "family": fam, "key": key, "value": v, "kind": kind, "targets": fixes,
                 "proposer": "rulebook", "diagnosis": diag, "before": pct(before), "after": pct(after),
                 "accepted": ok, "why": why, "evidence": ev}
        entries.append(entry)
        with open(LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"[{it:2d}] {fam:6s} {key}={v!s:5s} → {'ACCEPT' if ok else 'reject':6s} | {why}")
        if ok:
            cfg[key] = v
            if fam == "shield":
                b_blocked = nb
            else:
                b_shown = nb
            # a change in this filter may make earlier rejected ideas work: retry them (max 2 retries each)
            for rb in RULEBOOK:
                if rb[0] == fam and rb[1] != key and any(e["key"] == rb[1] and not e["accepted"] for e in entries) \
                        and rb not in queue:
                    queue.append(rb)
    write_md(entries)
    json.dump({"shield": cfg_s, "level": cfg_l}, open(os.path.join(EV, "accepted_config.json"), "w"), indent=1)
    print("\nAccepted config:", json.dumps({"shield": cfg_s, "level": cfg_l}))


if __name__ == "__main__":
    main()
