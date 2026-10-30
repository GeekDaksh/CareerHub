"""Run every v2 notebook cell with fake search / web / Gemini / Hunter / GitHub / DNS."""
import json, os, re, sys, shutil, builtins, time
os.environ.update(DATA_DIR="data", GEMINI_API_KEY="fake", HUNTER_API_KEY="fake-hunter", SERPER_API_KEY="", GITHUB_TOKEN="", TOMBA_KEY="tk", TOMBA_SECRET="ts", ZEROBOUNCE_API_KEY="zb", GROQ_API_KEY="gq", TAVILY_API_KEY="tv", JINA_API_KEY="")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
work = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "tests", ".work", "pipeline")
shutil.rmtree(work, ignore_errors=True); os.makedirs(work); os.chdir(work)
builtins.display = lambda df: print(df.to_string(max_colwidth=38) if hasattr(df, "to_string") else df)

if len(sys.argv) > 1:
    nb = json.load(open(sys.argv[1]))
    code = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
else:   # split jobs/pipeline.py at its '# CELL n' markers, the way the notebook had them
    src = open(os.path.join(ROOT, "jobs", "pipeline.py")).read()
    parts = re.split(r"\n(?=# -{70}\n# CELL)", src)
    code = [parts[0] + "\n" + parts[1]] + parts[2:]
code = ["\n".join(l for l in c.splitlines() if not l.strip().startswith("!")) for c in code]

def cf(s, key=0x42):
    return f"{key:02x}" + "".join(f"{ord(ch) ^ key:02x}" for ch in s)

JSONLD = json.dumps({"@context": "https://schema.org", "@type": "Organization", "name": "GenoMind AI",
                     "foundingDate": "2021", "founder": [{"@type": "Person", "name": "Priya Sharma"}],
                     "employee": [{"@type": "Person", "name": "Kavya Iyer", "jobTitle": "Head of Bioinformatics"}],
                     "sameAs": ["https://www.linkedin.com/company/genomind"]})
PAGES = {
 "https://genomind.ai": f"""<html><head><script type="application/ld+json">{JSONLD}</script></head><body>
   <h1>GenoMind AI</h1><p>We use deep learning and PyTorch for genomics and protein design. Our platform GenoCore speeds drug discovery.</p>
   <a href="/about">About us</a> <a href="/careers">Careers</a> <a href="https://github.com/genomind">GitHub</a>
   <a href="tel:+91 80 1234 5678">call</a>
   <footer>Write to hello [at] genomind [dot] ai or careers@genomind.ai.
   <a href="/cdn-cgi/l/email-protection#{cf('priya@genomind.ai')}">email</a></footer></body></html>""",
 "https://genomind.ai/about": """<html><body><h2>Leadership</h2><p>Priya Sharma — Co-founder & CEO. Amit Rao — Head of Research.
   Founded in 2021 in Bengaluru. Our team published a Nature paper on protein folding in 2025.</p></body></html>""",
 "https://genomind.ai/careers": """<html><body><p>Open roles: Machine Learning Intern (Bengaluru); Sales Manager</p>
   <a href="https://boards.greenhouse.io/genomind">See all jobs</a></body></html>""",
 "https://shipflow.in": """<html><body><p>ShipFlow builds demand forecasting and route optimization for logistics.</p>
   <a href="/contact">Contact</a></body></html>""",
 "https://shipflow.in/contact": """<html><body>Reach us: info@shipflow.in, ankit.mehta@shipflow.in</body></html>""",
}
PAGES["https://labloop.ai"] = '<html><body><div id="root"></div><script src="/app.js"></script></body></html>'
JINA = {"https://labloop.ai": """<html><body><h1>LabLoop</h1><p>LabLoop builds closed-loop lab automation with Bayesian optimization for chemistry labs, so experiments run themselves day and night.</p>
   <p>Founded by Sneha Kulkarni. Contact founders@labloop.ai or sneha@labloop.ai</p> <a href="/team">Team</a></body></html>""",
        "https://labloop.ai/team": "<html><body><p>Sneha Kulkarni — Founder & CEO. Vikram Shah — CTO.</p></body></html>"}
YC = [{"name": "LabLoop", "website": "https://labloop.ai", "all_locations": "Bengaluru, KA, India", "regions": ["India"],
       "status": "Active", "one_liner": "Lab automation for chemistry labs", "tags": ["Lab Automation"],
       "url": "https://www.ycombinator.com/companies/labloop"},
      {"name": "FarAway", "website": "https://faraway.com", "all_locations": "San Francisco", "status": "Active",
       "one_liner": "logistics"}]

class R:
    def __init__(self, status=200, text="", url="", ctype="text/html", js=None, headers=None):
        self.status_code, self.text, self.url, self._js = status, text, url, js
        self.headers = {"Content-Type": ctype, **(headers or {})}
    def json(self): return self._js

VERIFY = {"divya.rao@shipflow.in": "invalid", "divya@shipflow.in": "valid"}
LOG = {"verify": [], "github": 0, "hunter_search": 0, "tomba": [], "jina": 0, "hunter_limit": []}

def fake_get(url, params=None, timeout=None, allow_redirects=True, headers=None):
    u = url.rstrip("/")
    J = lambda js, **k: R(200, url=u, ctype="application/json", js=js, **k)
    if u.endswith("robots.txt"): return R(404)
    if u.startswith("https://r.jina.ai/"):
        LOG["jina"] += 1
        t = u[len("https://r.jina.ai/"):].rstrip("/")
        return R(200, JINA[t], u) if t in JINA else R(404)
    if "api.tomba.io/v1/domain-search" in u:
        LOG["tomba"].append(params["domain"])
        if params["domain"] == "genomind.ai":
            return J({"data": {"organization": {"pattern": "{first}", "accept_all": False}, "emails": [
                {"email": "amit@genomind.ai", "first_name": "Amit", "last_name": "Rao", "position": "Head of Research", "score": 92},
                {"email": "neha@genomind.ai", "first_name": "Neha", "last_name": "Gupta", "position": "Talent Acquisition Lead", "score": 88}]}})
        return J({"data": {"organization": {}, "emails": []}})
    if "api.zerobounce.net/v2/getcredits" in u: return J({"Credits": "100"})
    if "api.zerobounce.net/v2/validate" in u:
        LOG["verify"].append(params["email"])
        st = {"divya.rao@shipflow.in": "invalid", "divya@shipflow.in": "valid"}.get(params["email"], "unknown")
        return J({"status": st, "sub_status": ""})
    if u in PAGES: return R(200, PAGES[u], u)
    if "yc-oss.github.io" in u: return J(YC)
    if "boards-api.greenhouse.io/v1/boards/genomind/jobs" in u:
        return J({"jobs": [
            {"title": "Bioinformatics Scientist", "location": {"name": "Bengaluru"}, "absolute_url": "https://boards.greenhouse.io/genomind/jobs/1", "updated_at": "2026-10-01"},
            {"title": "Office Administrator", "location": {"name": "London"}, "absolute_url": "https://boards.greenhouse.io/genomind/jobs/2", "updated_at": "2026-09-01"}]})
    if "api.github.com" in u:
        LOG["github"] += 1
        h = {"X-RateLimit-Remaining": "50"}
        if u.endswith("/orgs/genomind/repos"): return J([{"name": "genocore", "fork": False, "html_url": "https://github.com/genomind/genocore"}], headers=h)
        if u.endswith("/repos/genomind/genocore/commits"):
            return J([{"commit": {"author": {"name": "Kavya Iyer", "email": "kavya@genomind.ai"}}},
                      {"commit": {"author": {"name": "bot", "email": "123+bot@users.noreply.github.com"}}}], headers=h)
        return R(404)
    if "api.hunter.io/v2/account" in u:
        return J({"data": {"requests": {"credits": {"used": 2, "available": 50}}}})
    if "api.hunter.io/v2/domain-search" in u:
        LOG["hunter_search"] += 1
        LOG["hunter_limit"].append(params["limit"])
        if params["domain"] == "genomind.ai":
            return J({"data": {"pattern": "{first}", "accept_all": False, "emails": [
                {"value": "amit@genomind.ai", "first_name": "Amit", "last_name": "Rao", "position": "Head of Research", "confidence": 92},
                {"value": "neha@genomind.ai", "first_name": "Neha", "last_name": "Gupta", "position": "Talent Acquisition Lead", "confidence": 88}]}})
        return J({"data": {"pattern": None, "accept_all": False, "emails": []}})
    if "api.hunter.io/v2/email-verifier" in u:
        LOG["verify"].append("hunter:" + params["email"])
        return J({"data": {"status": VERIFY.get(params["email"], "unknown"), "score": 95}})
    return R(404)

CALLS = {"search": 0, "gemini": 0}
LI = lambda name, head, slug, snip="": {"title": f"{name} - {head} | LinkedIn", "url": f"https://in.linkedin.com/in/{slug}", "snippet": snip}

def fake_search(q, n=10, prefer_google=False):
    CALLS["search"] += 1
    if "official website" in q:
        if "ShipFlow" in q: return [{"title": "ShipFlow news", "url": "https://inc42.com/x", "snippet": ""},
                                    {"title": "ShipFlow", "url": "https://www.shipflow.in/", "snippet": "ShipFlow home"}]
        return []
    if q.startswith("site:linkedin.com/in"):
        if '"GenoMind AI"' in q and "CTO" in q:
            return [LI("Rahul Verma", "CTO - GenoMind AI", "rahul-verma-123", "Experience: GenoMind AI · Location: Bengaluru"),
                    LI("Sanjay Kumar", "Ex-Data Scientist at GenoMind AI", "sanjayk"),
                    LI("Rohan Das", "Engineer - GenoMind Labs", "rohand", "Experience: GenoMind Labs")]
        if '"GenoMind AI"' in q and "talent" in q:
            return [LI("Meera Nair", "Talent Acquisition Lead - GenoMind AI", "meera-nair")]
        if '"GenoMind AI"' in q and "founder" in q:
            return [LI("Priya Sharma", "Co-founder & CEO at GenoMind AI", "priyasharma")]
        if '"ShipFlow"' in q and "founder" in q:
            return [LI("Ankit Mehta", "Founder - ShipFlow", "ankitmehta")]
        if '"ShipFlow"' in q and "CTO" in q:
            return [{"title": "Divya Rao | LinkedIn", "url": "https://in.linkedin.com/in/divyarao",
                     "snippet": "CTO at ShipFlow · Experience: ShipFlow · Pune"}]
        if '"TCS"' in q and "head" in q:
            return [LI("Arjun Patel", "Head of AI Research - TCS", "arjunp")]
        return []
    if "private limited directors" in q and "GenoMind" in q:
        return [{"title": "GENOMIND AI PRIVATE LIMITED - Zauba Corp", "url": "https://www.zaubacorp.com/company/GENOMIND-AI",
                 "snippet": "The directors of GENOMIND AI PRIVATE LIMITED are PRIYA SHARMA and AMIT RAO."}]
    if "co-founder CEO said" in q and "GenoMind" in q:
        return [{"title": "GenoMind AI raises $5M", "url": "https://inc42.com/genomind",
                 "snippet": "Priya Sharma, co-founder and CEO of GenoMind AI, said the funds will go to hiring."}]
    if q == '"@genomind.ai"':
        return [{"title": "Speaker list", "url": "https://conf.example.org/speakers", "snippet": "Rahul Verma (rahul@genomind.ai)"}]
    if "funding raised" in q and "GenoMind" in q:
        return [{"title": "GenoMind AI raises $5M Series A", "url": "https://inc42.com/genomind-series-a",
                 "snippet": "Bengaluru-based GenoMind AI raised $5M in a Series A round led by Accel in March 2026."}]
    if "founder CEO CTO" in q and "GenoMind" in q:
        return [{"title": "Meet the founders", "url": "https://yourstory.com/genomind",
                 "snippet": "Priya Sharma, co-founder and CEO of GenoMind AI, started the company in 2021."}]
    if "bioinformatics" in q:
        return [{"title": "Top bioinformatics startups in Bengaluru", "url": "https://seedtable.com/bio",
                 "snippet": "GenoMind AI (genomind.ai) is a Bengaluru startup using AI for genomics. TCS also runs life sciences units."}]
    if "logistics" in q or "supply chain" in q:
        return [{"title": "Pune logistics startups", "url": "https://startuptalky.com/pune",
                 "snippet": "ShipFlow is a Pune-based logistics tech startup."}]
    return []

def fake_gemini(prompt, temperature=0.1):
    CALLS["gemini"] += 1
    if "list the companies they name" in prompt:
        out = []
        if "GenoMind" in prompt:
            out += [{"name": "GenoMind AI", "website": "genomind.ai", "city": "Bengaluru", "country": "India", "type": "startup",
                     "what_they_do": "AI for genomics", "source_url": "https://seedtable.com/bio"},
                    {"name": "TCS", "website": None, "city": "Mumbai", "country": "India", "type": "corporate",
                     "what_they_do": "IT services", "source_url": "https://seedtable.com/bio"},
                    {"name": "Invented Bio Labs", "website": None, "city": None, "country": "India", "type": "startup",
                     "what_they_do": "made up", "source_url": "x"}]
        if "ShipFlow" in prompt:
            out += [{"name": "ShipFlow", "website": "https://inc42.com/shipflow", "city": "Pune", "country": "India",
                     "type": "startup", "what_they_do": "logistics", "source_url": "https://startuptalky.com/pune"}]
        return out
    if "cold email" in prompt:
        return {"subject": "Your protein folding work + my SDL project", "body": "Hi Priya, ... Daksh"}
    name = re.search(r'company "([^"]+)"', prompt).group(1)
    assert "structured data" in prompt if name == "GenoMind AI" else True, "JSON-LD block missing from corpus"
    assert "hello@genomind.ai" in prompt if name == "GenoMind AI" else True, "obfuscated email not decoded"
    if name == "GenoMind AI":
        return {"official_name": "GenoMind AI", "founded_year": 2021, "hq_city": "Bengaluru", "country": "India",
                "is_startup": True, "stage": "Series A", "one_liner": "AI for genomics",
                "what_they_do": "Deep learning for genomics and protein design.",
                "products": [{"name": "GenoCore", "description": "drug discovery platform", "source": "https://genomind.ai"}],
                "research_and_discoveries": [{"item": "Nature paper on protein folding (2025)", "source": "https://genomind.ai/about"}],
                "tech_and_methods": ["deep learning", "PyTorch", "bayesian optimization"],
                "funding": {"total": "$5M", "last_round": "Series A", "last_round_amount": "$5M", "last_round_date": "March 2026",
                            "investors": ["Accel"], "source": "https://inc42.com/genomind-series-a"},
                "funding_rounds": [{"round": "Series A", "amount": "$5M", "date": "2026-03", "investors": ["Accel"], "source": "https://inc42.com/genomind-series-a"}],
                "people": [{"name": "Priya Sharma", "role": "Co-founder & CEO", "is_key_contact": True, "linkedin": None, "email": None, "source": "https://genomind.ai/about"},
                           {"name": "Amit Rao", "role": "Head of Research", "is_key_contact": True, "linkedin": None, "email": None, "source": "https://genomind.ai/about"},
                           {"name": "Ghost Person", "role": "CEO", "is_key_contact": True, "linkedin": None, "email": None, "source": "x"}],
                "open_roles": [{"title": "Machine Learning Intern", "location": "Bengaluru", "url": None}],
                "contact": {"general_email": "hello@genomind.ai", "phone": None, "address": None}}
    if name == "ShipFlow":
        return {"official_name": "ShipFlow", "hq_city": "Pune", "country": "India", "is_startup": True,
                "what_they_do": "Demand forecasting and route optimization for logistics.", "products": [],
                "people": [], "open_roles": [], "contact": {}}
    if name == "LabLoop":
        assert "closed-loop lab automation" in prompt, "Jina-rendered text missing"
        return {"official_name": "LabLoop", "is_startup": True, "hq_city": "Bengaluru", "country": "India",
                "what_they_do": "Closed-loop lab automation with Bayesian optimization.",
                "people": [{"name": "Sneha Kulkarni", "role": "Founder & CEO", "is_key_contact": True, "source": "https://labloop.ai/team"},
                           {"name": "Vikram Shah", "role": "CTO", "is_key_contact": True, "source": "https://labloop.ai/team"}],
                "open_roles": []}
    return {"official_name": name, "is_startup": False, "people": [], "open_roles": []}

MX = {"genomind.ai": {"has_mx": True, "provider": "Google Workspace", "hosts": ["aspmx.l.google.com"]},
      "shipflow.in": {"has_mx": True, "provider": "Zoho Mail", "hosts": ["mx.zoho.in"]},
      "labloop.ai": {"has_mx": True, "provider": "Google Workspace", "hosts": ["aspmx.l.google.com"]}}

ns = {"__file__": "/home/claude/career-hub/jobs/pipeline.py"}
for i, c in enumerate(code):
    print(f"\n========== CODE CELL {i + 1} ==========")
    exec(compile(c, f"cell{i + 1}", "exec"), ns)
    if i == 0:
        ns["SAVE_TO_DRIVE"] = False
    if i == 1:
        ns["GEMINI_PAUSE"] = 0; ns["SEARCH_PAUSE"] = 0
        if os.environ.get("TOPUP"): ns["TOMBA_SEARCH_MAX"] = 0; ns["HUNTER_SEARCH_MAX"] = 0
    if i == 2:
        ns["web_search_raw"] = fake_search
        ns["web_search"] = fake_search
        ns["ask_gemini"] = fake_gemini
        ns["mx_lookup"] = lambda d: MX.get(d, {"has_mx": False, "provider": None, "hosts": []})
        ns["SESSION"].get = fake_get
        ns["time"].sleep = lambda s: None
LOG_RUN1 = json.loads(json.dumps(LOG))
print("\nCALLS run 1:", CALLS, "| verifications:", LOG["verify"], "| github calls:", LOG["github"], "| hunter searches:", LOG["hunter_search"])

if os.environ.get("TOPUP"):
    pdb = ns["people_db"]["GenoMind AI"]
    print("month 1 finder_done:", pdb["finder_done"], "| Amit sources:", [x["source_types"] for x in pdb["people"] if x["name"] == "Amit Rao"])
    ns["TOMBA_SEARCH_MAX"] = 25; ns["HUNTER_SEARCH_MAX"] = 15
    for i in (6, 7):
        exec(compile(code[i], f"cell{i+1}-month2", "exec"), ns)
    pdb = ns["people_db"]["GenoMind AI"]
    print("month 2 finder_done:", pdb["finder_done"], "| Amit sources:", [x["source_types"] for x in pdb["people"] if x["name"] == "Amit Rao"])
    print("TOPUP", "PASS" if pdb["finder_done"] and "Tomba" in [x for x in pdb["people"] if x["name"] == "Amit Rao"][0]["source_types"] else "FAIL")
    sys.exit()
# ---- checks ----
C = ns["contacts"].set_index("name")
def chk(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    globals().setdefault("FAILS", []).append(msg) if not cond else None
chk("Ghost Person" not in C.index, "Gemini-invented person dropped")
chk("Sanjay Kumar" not in C.index, "former employee (Ex-) dropped")
chk("Rohan Das" not in C.index, "person at a different company (GenoMind Labs) dropped")
chk(C.loc["Priya Sharma", "email"] == "priya@genomind.ai" and C.loc["Priya Sharma", "email_grade"] == "A · published", "Priya: Cloudflare email on site -> A published")
chk(C.loc["Priya Sharma", "person_confidence"] == "High" and "company registry" in C.loc["Priya Sharma", "source_types"]
    and "news" in C.loc["Priya Sharma", "source_types"], "Priya merged across site, LinkedIn, registry, news")
chk(C.loc["Amit Rao", "email"] == "amit@genomind.ai" and C.loc["Amit Rao", "email_grade"] == "B · strong" and "Tomba" in C.loc["Amit Rao", "source_types"], "Amit: Tomba 92% -> B")
chk("genomind.ai" in LOG_RUN1["tomba"] and LOG_RUN1["hunter_limit"] and set(LOG_RUN1["hunter_limit"]) == {1}, "Tomba used first; Hunter only with limit=1")
chk(LOG_RUN1["hunter_search"] == len([d for d in LOG_RUN1["tomba"] if d != "genomind.ai"]), "Hunter skipped where Tomba already found emails")
chk(ns["profiles"]["LabLoop"]["crawl"].get("rendered_with_jina") and C.loc["Sneha Kulkarni", "email"] == "sneha@labloop.ai", "JS-only site read via Jina; founder email found")
chk(C.loc["Vikram Shah", "email"] == "vikram@labloop.ai" and C.loc["Vikram Shah", "email_grade"] == "C · likely", "Vikram: pattern seen once -> C")
chk("vikram@labloop.ai" in LOG_RUN1["verify"] and "hunter:vikram@labloop.ai" in LOG_RUN1["verify"], "ZeroBounce 'unknown' -> Hunter tried next")
chk(C.loc["Rahul Verma", "email"] == "rahul@genomind.ai" and C.loc["Rahul Verma", "email_grade"] == "B · strong", "Rahul: email from web search -> B")
chk(C.loc["Rahul Verma", "category"] == "CTO / Engineering lead", "Rahul categorised as CTO")
chk(C.loc["Kavya Iyer", "email"] == "kavya@genomind.ai" and C.loc["Kavya Iyer", "category"] == "AI / Research lead", "Kavya: JSON-LD person + GitHub email")
chk(C.loc["Meera Nair", "email"] == "meera@genomind.ai" and C.loc["Meera Nair", "email_grade"] == "B · strong", "Meera: built from confirmed {first} pattern -> B")
chk(C.loc["Divya Rao", "email"] == "divya@shipflow.in" and C.loc["Divya Rao", "email_grade"] == "A · verified", "Divya: first guess invalid, second verified")
chk(C.loc["Ankit Mehta", "email"] == "ankit.mehta@shipflow.in", "Ankit: site email matched by name")
chk(C.loc["Arjun Patel", "category"] == "AI / Research lead" and pd_isna(C.loc["Arjun Patel", "email"]) if (pd_isna := __import__("pandas").isna) else True, "Arjun (TCS, no domain): no fake email")
P = ns["plan"].set_index("company")
chk(P.loc["GenoMind AI", "contact_1"] == "Priya Sharma", "startup -> founder is contact 1")
chk(P.loc["TCS", "contact_1"] == "Arjun Patel", "corporate -> AI lead is contact 1")
chk(P.loc["GenoMind AI", "hiring_contact"] in ("Meera Nair", "Neha Gupta"), "hiring contact filled")
chk(len(ns["drafts"]) == int(ns["plan"]["contact_1"].notna().sum()), "a draft only where there is a contact")
chk(all(len(x) <= 200 for x in P["linkedin_note"].dropna()), "LinkedIn notes <= 200 chars")
chk("LabLoop" in ns["ranked"]["company"].values, "YC directory company added")
chk(ns["companies_mail"]["ShipFlow"]["pattern"] == "{first}", "ShipFlow pattern updated from verified email")
print("\nGenoMind talking point:", P.loc["GenoMind AI", "talking_point"])
print("GenoMind LinkedIn note:", P.loc["GenoMind AI", "linkedin_note"])

# ---- rerun cells 4..12: nothing new should be fetched ----
CALLS.update(search=0, gemini=0); LOG.update(verify=[], github=0, hunter_search=0)
for i in range(3, len(code)):
    exec(compile(code[i], f"cell{i + 1}-rerun", "exec"), ns)
print("\nCALLS run 2:", CALLS, "| verifications:", LOG["verify"], "| github:", LOG["github"], "| hunter searches:", LOG["hunter_search"])
chk(CALLS["gemini"] == 0 and not LOG["verify"] and LOG["hunter_search"] == 0,
    "rerun costs no Gemini / Hunter / verifications")
left = len([q for q in ns["queries"] if q[1] not in ns["search_log"]])
chk(left == 0, f"rerun finishes the discovery searches the first run left (cap {ns['DISCOVERY_PER_RUN']} per run)")
CALLS.update(search=0, gemini=0); LOG.update(verify=[], github=0, hunter_search=0)
for i in range(3, len(code)):
    exec(compile(code[i], f"cell{i + 1}-rerun3", "exec"), ns)
chk(CALLS["search"] == 0 and CALLS["gemini"] == 0 and not LOG["verify"] and LOG["hunter_search"] == 0,
    "third run (everything done) costs no searches / Gemini / Hunter")

# ---- a company with people but no email evidence at all (crashed live run #2: no pattern learned) ----
ap = ns["apply_pattern"]
chk(ap(None, "priya", "sharma") is None and ap("{first}", "priya", "") == "priya",
    "no email pattern learned yet: no crash, no made-up address")

# ---- time budget: a run that is out of time stops each stage and still writes the outputs ----
ns["RUN_START"] = time.time() - 10_000
ns["_stage_logged"].clear()
ns["search_log"].clear()
ns["save_json"]("search_results.json", {})
CALLS.update(search=0, gemini=0)
for i in range(3, len(code)):
    exec(compile(code[i], f"cell{i + 1}-late", "exec"), ns)
chk(CALLS["search"] == 0 and CALLS["gemini"] == 0, "out of time: no new searches or AI calls are started")
chk(os.path.exists(os.path.join(work, "data", "jobs", "run_status.json")) or os.path.exists(os.path.join(work, "jobs", "run_status.json"))
    or any(f == "run_status.json" for _, _, fs in os.walk(work) for f in fs), "out of time: the run still writes its status and outputs")
chk({"discovery", "emails"} <= ns["_stage_logged"], f"out of time: stages with work left say they stopped ({sorted(ns['_stage_logged'])})")
print("\nFAILURES:", globals().get("FAILS", []))

# ---- unit tests: Groq fallback, search order (real functions, mocked network) ----
src3 = code[2]
u = dict(ns)   # copy of globals with mocks
exec(compile(src3, "cell3-fresh", "exec"), u)   # fresh, un-mocked helpers
class FakeResp:
    def __init__(self, code, js=None, text=""): self.status_code, self._js, self.text = code, js, text
    def json(self): return self._js
posts = []
def fake_post(url, json=None, headers=None, timeout=None):
    posts.append((url, json))
    if "groq" in url:
        if json["model"] == "llama-3.3-70b-versatile":
            return FakeResp(429, text="Rate limit reached ... tokens per day (TPD)")
        return FakeResp(200, {"choices": [{"message": {"content": '{"result": [{"name": "X"}]}'}}]})
    if "tavily" in url:
        return FakeResp(200, {"results": [{"title": "T", "url": "https://in.linkedin.com/in/x", "content": "c"}]})
    if "serper" in url:
        return FakeResp(200, {"organic": [{"title": "G", "link": "https://google-result", "snippet": "s"}]})
u["requests"].post = fake_post
class Boom:
    def generate_content(self, **k): raise Exception("429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel")
u["client"].models.generate_content = Boom().generate_content
u["time"].sleep = lambda s: None
out = u["ask_gemini"]("Return JSON list")
chk(out == [{"name": "X"}] and "llama-3.3-70b-versatile" in u["_groq_dead"], "Gemini daily limit -> Groq (skips model out of daily tokens), unwraps list")
u["ddg_search"] = lambda q, n=10: None   # DuckDuckGo blocked
res = u["web_search_raw"]('site:linkedin.com/in "GenoMind AI" CTO')
tv = [j for url, j in posts if "tavily" in url][-1]
chk(res and res[0]["title"] == "T" and tv["include_domains"] == ["linkedin.com"] and "site:" not in tv["query"], "DDG blocked -> Tavily with domain filter")
u["SERPER_KEY"] = "sk"
res = u["web_search_raw"]("x", prefer_google=True)
chk(res[0]["title"] == "G", "people searches go to Google (Serper) first")
print("\nFAILURES:", globals().get("FAILS", []))
sys.exit(1 if globals().get("FAILS") else 0)
