"""Careers classifier improvement loop: try each switch in careers.classify.OPTS (in order), on TRAIN only,
keep it only if it passes the accept rule declared in OBJECTIVE.md. Logs every decision.
   python -m eval.careers.loop"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from careers import classify as K
from eval.careers.measure import run, HERE

ORDER = ["title_underscores", "desc_fallback_tech_only", "nontech_ext", "other_tech", "hardware_ext", "swe_ext",
         "research_titles", "genai_ext", "manager_not_level", "mts_levels", "student_titles", "year_ranges",
         "title_level_first", "product_titles_first", "years_required_only"]
WHY = {"title_underscores": "titles like 'Linux kernel developer_BSH' hide words behind underscores",
       "desc_fallback_tech_only": "non-technical jobs became 'ML' because company boilerplate says 'AI' 3+ times",
       "nontech_ext": "strategist, sourcer, accounting, writer, growth... were missed as non-technical",
       "other_tech": "solutions architects, consultants, network / mechanical / IT ops were called Software",
       "hardware_ext": "DFT, logic / physical design, verification, layout, product engineering were called Software",
       "swe_ext": "architect / programming / kernel titles fell to 'Other'",
       "research_titles": "researcher / student researcher / post-doc titles were called ML Engineer",
       "genai_ext": "'Voice AI', 'Agent Engineer', 'Agentic Systems' not seen as GenAI",
       "manager_not_level": "'Product / Program / Account Manager' is a job name, not a seniority",
       "mts_levels": "Salesforce SMTS / LMTS mean senior",
       "student_titles": "'Student Researcher' is an internship; post-doc is right after PhD",
       "year_ranges": "'2–5 years in DevOps' (no word 'experience') was missed",
       "title_level_first": "dry run: 'Data Scientist II' read as entry because the description's years were checked first",
       "product_titles_first": "dry run: 'Technical Program Manager, AI Products' called an ML role",
       "years_required_only": "dry run: 'preferred: 1+ years of X' made 'Data Scientist II' (requires 2+) look entry-level"}
GUARD = ["level_accuracy", "ml_flag_accuracy", "nontech_accuracy"]


def metrics(opts):
    return {c["metric"]: c["value"] for c in run(opts=opts, quiet=True)}


def accept(old, new):
    dp = new["family_accuracy"] - old["family_accuracy"]
    drops = [g for g in GUARD if new[g] < old[g] - 0.01 + 1e-9]
    if drops:
        return False, "guardrail dropped: " + ", ".join(drops)
    if dp >= 0.01 - 1e-9:
        return True, f"family +{dp:.3f}"
    ups = [g for g in GUARD if new[g] >= old[g] + 0.01 - 1e-9]
    if abs(dp) < 1e-9 and ups:
        return True, "family same, up: " + ", ".join(ups)
    return False, f"not enough gain (family {dp:+.3f})"


def main():
    opts = {k: False for k in K.OPTS}
    cur = metrics(opts)
    log = [{"step": 0, "change": "baseline", "metrics": cur, "decision": "baseline"}]
    for i, k in enumerate(ORDER, 1):
        trial = {**opts, k: True}
        new = metrics(trial)
        ok, why = accept(cur, new)
        log.append({"step": i, "change": k, "why_tried": WHY[k], "before": cur, "after": new,
                    "decision": "ACCEPT" if ok else "REJECT", "reason": why, "proposer": "rule (from error diagnosis)"})
        if ok:
            opts, cur = trial, new
    # one retry for each rejected idea, now that other switches changed (deterministic, same accept rule)
    for k in [r["change"] for r in log if r.get("decision") == "REJECT"]:
        if opts[k]:
            continue
        new = metrics({**opts, k: True})
        ok, why = accept(cur, new)
        log.append({"step": len(log), "change": k + " (retry)", "why_tried": "retry after other changes", "before": cur,
                    "after": new, "decision": "ACCEPT" if ok else "REJECT", "reason": why, "proposer": "retry rule"})
        if ok:
            opts, cur = {**opts, k: True}, new
    with open(os.path.join(HERE, "loop_log.jsonl"), "w") as f:
        for r in log:
            f.write(json.dumps(r) + "\n")
    md = ["# Careers classifier loop (train only, n=200)", "",
          "| # | change | why tried | family | level | ml flag | non-tech | decision |", "|---|---|---|---|---|---|---|---|"]
    for r in log:
        m = r.get("after") or r["metrics"]
        md.append(f"| {r['step']} | {r['change']} | {r.get('why_tried', '')} | {m['family_accuracy']:.3f} | "
                  f"{m['level_accuracy']:.3f} | {m['ml_flag_accuracy']:.3f} | {m['nontech_accuracy']:.3f} | "
                  f"{r['decision']} {r.get('reason', '')} |")
    md += ["", "Accepted switches: " + ", ".join(k for k, v in opts.items() if v)]
    open(os.path.join(HERE, "LOOP.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))
    return opts


if __name__ == "__main__":
    main()
