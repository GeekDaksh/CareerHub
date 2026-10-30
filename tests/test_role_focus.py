"""ML / GenAI / CV focus, whole-word role matching, and startups vs big firms.  python tests/test_role_focus.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("DATA_DIR", os.path.join(ROOT, "tests", ".work", "role_focus"))
import config as C  # noqa: E402
from common import settings as S  # noqa: E402
from roles import radar as R  # noqa: E402

FAILS = []


def chk(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        FAILS.append(m)


s = S.clean(None)
cases = {   # real titles from the first live run, plus traps
    "Machine Learning Engineer": ["ML / AI Engineer"], "Deep Learning Engineer": ["ML / AI Engineer"],
    "AI/ML Developer Intern": ["ML / AI Engineer"], "GenAI Intern": ["LLM / GenAI Engineer"],
    "LLM Engineer (RAG)": ["LLM / GenAI Engineer"], "NLP Engineer": ["LLM / GenAI Engineer"],
    "Computer Vision Intern": ["Computer Vision Engineer"], "Perception Engineer": ["Computer Vision Engineer"],
    "Data Science Intern": ["Data Scientist"], "AI Research Intern": ["Research Engineer"],
    # not your roles (these ranked near the top before the fix)
    "Intermediate Backend Engineer, India": [], "Front End Developer": [], "Software Engineer - Storage": [],
    "Storage Engineer": [], "Paragraph Editor": [], "Mail Engineer": [],
    # AI words, but not engineering work
    "AI Sales Executive": [], "Customer Success Manager - AI": [], "Generative AI Marketing Lead": [],
    "Talent Acquisition - AI": [], "AI Trainer (Hindi)": [],
}
for t, want in cases.items():
    chk(S.roles_matched(t, s) == want, f"role match: {t!r} -> {want or 'not your roles'} (got {S.roles_matched(t, s)})")

chk(R.search_queries(s)[0][1].startswith('site:') and '"Machine Learning Engineer"' in R.search_queries(s)[0][1],
    "web search starts with your core roles (ML first)")
phrases = " ".join(q for _, q in R.search_queries(s))
chk(all(p in phrases for p in ('"LLM Engineer"', '"Computer Vision Intern"', '"GenAI Intern"', '"Data Science Intern"')),
    "extra ML / GenAI / CV phrases are searched too")

ct = R.company_type
chk(ct({"tier": "1 · India startup"}) == "startup" and ct({"tier": "4 · Global corporate"}) == "big", "company type from the job finder's tier")
chk(ct({"company": "GitLab", "company_size": "big"}) == "big" and ct({"company": "Supabase", "company_size": "startup"}) == "startup",
    "company type from the remote-company list")
chk(ct({"company": "Tata Consultancy Services"}) == "big" and ct({"company": "Microsoft India"}) == "big", "big firms by name")
chk(ct({"company": "Metamorph Labs"}) == "unknown" and ct({"company": "Hpcl Biofuels"}) == "unknown",
    "no false 'big firm' from part of a word (Meta in Metamorph, HP in Hpcl)")
chk(ct({"company": "Artha Labs", "platform": "Wellfound"}) == "startup", "jobs on startup-only sites count as startups")
chk(ct({"company": "Acme", "platform": "LinkedIn"}) == "unknown", "otherwise: not sure (no guessing)")

r = {"roles": ["ML / AI Engineer"], "focus": True, "sectors": [], "trust": {"verdict": "likely"}, "level": "entry",
     "location_ok": True, "keywords": []}
o = {**r, "roles": [], "focus": False}
chk(R.score(r, s)[0] - R.score(o, s)[0] >= 60, "an ML role outranks a non-matching role by a wide margin")
chk(R.score(o, s)[0] >= 0, "scores never go below 0")
print("\nFAILURES:", FAILS)
sys.exit(1 if FAILS else 0)
