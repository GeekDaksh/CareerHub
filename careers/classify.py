"""Classify every job: role family, specialties, level, employment type, work mode, company tier.

Rules you can read, each returning the evidence it used:
  • the TITLE decides first (strong evidence → confidence "high")
  • the DESCRIPTION decides only when the title is generic (weaker → "medium"), e.g. "Software Engineer" whose
    description is full of model training → family "Software Engineer", specialty "ML-heavy"
  • nothing found → "low", and the app says "not stated" instead of guessing
"""
import re

from common import levels

# Improvement-loop switches (eval/careers/loop.py turns them on one at a time and keeps only those that pass the
# declared accept rule in eval/careers/OBJECTIVE.md). The values here are the accepted ones.
OPTS = {"title_underscores": True, "desc_fallback_tech_only": True, "nontech_ext": True, "other_tech": True,
        "hardware_ext": True, "swe_ext": True, "research_titles": True, "genai_ext": False,
        "manager_not_level": True, "mts_levels": False, "student_titles": False, "year_ranges": True,
        "title_level_first": True, "product_titles_first": True, "years_required_only": False}

NON_TECH_EXT = (r"strategist|sourcer|government affairs|public policy|total rewards|accounting|technical writer|"
                r"writer|vendor|growth|collections|enablement|mobility|social experience|costing|fp&a|planner|"
                r"category manager|people consultant|people partner|employee success|buyer|commission|cluster head|"
                r"last mile|physical security|account management|quality analyst|supply chain planning|"
                r"business planning|\bgtm\b|go-to-market|strategy|payroll|hr shared|sales operations|marketing science")
OTHER_TECH = (r"\b(solutions? architect\w*|solutions? engineer|sales engineer|pre-?sales|professional services|"
              r"consultant|\bsap\b|functional sme|network engineer|collaboration engineer|mechanical|civil|"
              r"manufacturing engineer|industrial engineer\w*|it operations?|service desk|security analyst|soc analyst|"
              r"compliance lead|information security|deployment strategist|technical solutions|application engineer|"
              r"cloud solution architect|architect infra)\b")
HW_EXT = (r"\b(design engineer|dft|logic design|physical design|design evaluation|formal verification|"
          r"process control|product engineer\w*|\bpe\b|electrical|ecu|autosar|diagnostic|quality (?:assurance )?engineer|"
          r"reliability engineer|rda|layout|test process|soc architect|asic|hw developer)\b")
SWE_EXT = r"\b(architect|programming|technical manager|salesforce engineer|backend engineer|kernel|build)\b"
RESEARCH_TITLES = r"\b(researcher|research scientist|student researcher|post-?doc\w*|research intern|research phd)\b"
PRODUCT_TITLES = r"\b(product manager|program manager|technical program|product owner|product designer|ux designer)\b"
GENAI_EXT = r"\b(voice|agent engineer|agentic systems?|agents)\b"

# ---------------------------------------------------------------- role families (checked in this order)
NON_TECH = (r"account executive|account manager|account development|sales|business development|\bbdr\b|\bsdr\b|"
            r"marketing|brand|communications|public relations|recruit|talent|human resources|\bhr\b|people partner|"
            r"people experience|benefits|payroll|finance|financial|accountant|accounts payable|accounts receivable|"
            r"\btax\b|treasury|audit|legal|counsel|paralegal|compliance|customer success|customer support|"
            r"support specialist|customer service|procurement|purchasing|supplier|sourcing|facilities|workplace|"
            r"office manager|executive assistant|administrative|admin |receptionist|logistics coordinator|"
            r"engagement manager|partner manager|alliances|channel|renewals|deal desk|pricing|revenue|"
            r"emergency response|security officer|event|content writer|copywriter|editor|translator|trainer|annotator")
FAMILIES = [   # (family, title pattern, description pattern for generic titles)
    ("GenAI / LLM", r"\b(llm|genai|gen ai|generative ai|large language|nlp|natural language|conversational ai|"
                    r"ai agents?|agentic|prompt engineer|rag|foundation model|speech|asr|tts)\b", None),
    ("Computer Vision", r"\b(computer vision|vision|perception|image|video|imaging|3d|multimodal|cv engineer)\b", None),
    ("MLOps / ML Platform", r"\b(mlops|ml ops|ml platform|ml infrastructure|ai infrastructure|ml systems|"
                            r"model serving|inference|ai platform)\b", None),
    ("AI Research", r"\b(research scientist|research engineer|research intern|ai research|ml research|"
                    r"research fellow|ai scientist|ml scientist)\b", None),
    ("Data Science", r"\b(data scien\w*|decision scien\w*)\b", None),
    ("ML Engineer / Applied Scientist", r"\b(machine learning|ml|ai|artificial intelligence|deep learning|applied scientist|"
                                        r"applied science|ai/ml|ml/ai)\b", None),
    ("Data Engineering", r"\b(data engineer\w*|etl|data platform|big data|analytics engineer)\b", None),
    ("Robotics / Autonomy", r"\b(robotic\w*|autonom\w*|slam|motion planning|controls engineer)\b", None),
    ("Embedded / Hardware", r"\b(embedded|firmware|fpga|asic|vlsi|rtl|silicon|soc|hardware|pcb|analog|"
                            r"verification engineer|design verification|physical design|cad|layout|"
                            r"product engineer|test engineer|validation engineer|semiconductor|process engineer)\b", None),
    ("Bioinformatics / Comp. Bio", r"\b(bioinformatic\w*|computational biolog\w*|genomic\w*|cheminformatic\w*)\b", None),
    ("Data Analytics", r"\b(data analyst|analytics|business intelligence|bi developer|business analyst)\b", None),
    ("Software Engineering", r"\b(software|sde|developer|engineer|engineering|programmer|full[ -]?stack|"
                             r"backend|back-end|frontend|front-end|devops|sre|site reliability|cloud|security engineer|"
                             r"qa|automation)\b", None),
    ("Product / Design", r"\b(product manager|program manager|technical program|product owner|designer|ux|ui)\b", None),
]
TECH_FAMILIES_ML = {"GenAI / LLM", "Computer Vision", "MLOps / ML Platform", "AI Research",
                    "ML Engineer / Applied Scientist", "Data Science"}

# specialties: (tag, pattern) — counted in title (×3) and description (×1)
SPECIALTIES = [
    ("LLMs", r"\b(llms?|large language models?|gpt|transformers?|fine-?tun\w*)\b"),
    ("RAG / Search", r"\b(rag|retrieval|vector (search|database)|semantic search|search ranking|information retrieval)\b"),
    ("AI agents", r"\b(ai agents?|agentic|multi-agent|langgraph|langchain|tool use)\b"),
    ("NLP", r"\b(nlp|natural language|text classification|named entity|translation)\b"),
    ("Speech", r"\b(speech|asr|tts|voice|audio)\b"),
    ("Computer vision", r"\b(computer vision|image|video|object detection|segmentation|opencv|yolo|vision)\b"),
    ("3D / Graphics", r"\b(3d|point cloud|nerf|gaussian splatting|graphics|rendering)\b"),
    ("Generative media", r"\b(diffusion|generative image|stable diffusion|text-to-image|gan)\b"),
    ("Recommenders", r"\b(recommend\w*|personali[sz]ation|ranking)\b"),
    ("Forecasting / Time series", r"\b(forecast\w*|time[- ]series|demand planning)\b"),
    ("Reinforcement learning", r"\b(reinforcement learning|rl\b|bandits?)\b"),
    ("Optimisation", r"\b(optimi[sz]ation|operations research|bayesian optimi[sz]ation|solver)\b"),
    ("GPU / CUDA / HPC", r"\b(cuda|gpu|triton|hpc|kernel optimi[sz]ation|tensorrt)\b"),
    ("Distributed training", r"\b(distributed training|deepspeed|megatron|fsdp|multi-node)\b"),
    ("Edge / Embedded AI", r"\b(edge ai|on-device|tinyml|embedded ml|quantization)\b"),
    ("Robotics / Autonomy", r"\b(robot\w*|autonomous|self-driving|slam|lidar)\b"),
    ("Healthcare / Bio", r"\b(healthcare|medical|clinical|genomic\w*|drug discovery|biolog\w*)\b"),
    ("Supply chain", r"\b(supply chain|logistics|inventory|warehouse|fulfil+ment)\b"),
]
ML_TERMS = re.compile(r"\b(machine learning|deep learning|pytorch|tensorflow|model training|neural network|llm|"
                      r"computer vision|nlp|scikit-learn|ml models?)\b", re.I)


def _family(title, desc, o=None):
    o = OPTS if o is None else o
    t = title.lower()
    if o["title_underscores"]:
        t = re.sub(r"[_/]+", " ", t)
    nontech = NON_TECH + ("|" + NON_TECH_EXT if o["nontech_ext"] else "")
    if re.search(nontech, t) and not re.search(r"\b(engineer|scientist|developer|research)\b", t):
        return "Non-technical", "high", "title"
    if o["product_titles_first"] and re.search(PRODUCT_TITLES, t):
        return "Product / Design", "high", "title"
    if o["research_titles"] and re.search(RESEARCH_TITLES, t):
        return "AI Research", "high", "title"
    if o["genai_ext"] and re.search(GENAI_EXT, t):
        return "GenAI / LLM", "high", "title"
    if o["other_tech"] and re.search(OTHER_TECH, t):
        return "Other", "high", "title (solutions / consulting / IT / other engineering)"
    if o["hardware_ext"] and re.search(HW_EXT, t) and not re.search(r"\b(software|machine learning|ml|ai)\b", t):
        return "Embedded / Hardware", "high", "title"
    for fam, pat, _ in FAMILIES:
        if re.search(pat, t, re.I):
            # 'scientist' alone means AI Research only when nothing more specific matched before it
            return fam, "high", "title"
    if o["swe_ext"] and re.search(SWE_EXT, t):
        return "Software Engineering", "high", "title"
    if re.search(nontech, t):
        return "Non-technical", "medium", "title"
    if o["desc_fallback_tech_only"] and not re.search(r"\b(engineer|developer|scientist|architect|analyst)\b", t):
        return "Other", "low", "none"
    d = desc.lower()[:4000]
    for fam, pat, _ in FAMILIES[:6]:      # generic title: let a strongly ML description decide
        if o["desc_fallback_tech_only"]:
            pat = pat.replace("|ml|ai|", "|").replace("|ai/ml|ml/ai", "")
        if len(re.findall(pat, d)) >= 3:
            return fam, "medium", "description"
    return "Other", "low", "none"


def specialties(title, desc, top=4):
    t, d = title.lower(), desc.lower()[:6000]
    scored = []
    for tag, pat in SPECIALTIES:
        n = 3 * len(re.findall(pat, t)) + len(re.findall(pat, d))
        if n >= 2:
            scored.append((n, tag))
    return [tag for _, tag in sorted(scored, reverse=True)[:top]]


# ---------------------------------------------------------------- level
INTERN = re.compile(r"\b(intern|internship|co-?op|apprentice|trainee)\b", re.I)
NEW_GRAD = re.compile(r"\b(new grad\w*|graduate|university|campus|fresher|freshers|entry[- ]level|early career|"
                      r"associate engineer|junior|jr\.?|level 1|sde[- ]?(i|1)\b|engineer i\b|engineer 1\b|"
                      r"scientist i\b|developer i\b)", re.I)
MID = re.compile(r"\b(ii|2|iii|3|mid[- ]level|intermediate|smts|mts)\b", re.I)
SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|manager|director|head|architect|distinguished|fellow|vp|"
                    r"iv|4|5)\b", re.I)


NOT_LEVEL_MANAGER = re.compile(r"\b(product|program|project|account|customer success|technical program|partner|"
                               r"collections|category|deputy|assistant|asst\.?)\s+manager\b", re.I)
STUDENT = re.compile(r"\b(student researcher|student)\b", re.I)
POSTDOC = re.compile(r"\bpost-?doc\w*\b|\bpost-doctoral\b", re.I)
SENIOR_MTS = re.compile(r"\b(smts|lmts|pmts|dmts)\b", re.I)
RANGE_YEARS = re.compile(r"\b(\d{1,2})\s*(?:[-–]|to)\s*\d{1,2}\s*\+?\s*(?:years?|yrs?)\b", re.I)


def level(title, desc, kind_hint="", o=None):
    """→ (label, confidence, evidence). Labels: Intern · New grad / entry · Early career (1–3 yrs) · Mid · Senior+."""
    o = OPTS if o is None else o
    t = title or ""
    if o["title_underscores"]:
        t = re.sub(r"[_/]+", " ", t)
    if o["student_titles"] and STUDENT.search(t):
        return "Intern", "high", "title says student"
    if o["student_titles"] and POSTDOC.search(t):
        return "New grad / entry", "high", "post-doctoral role (right after a PhD)"
    if o["mts_levels"] and SENIOR_MTS.search(t) and not re.search(r"\bmts\b", t, re.I):
        return "Senior+", "high", f"title level '{SENIOR_MTS.search(t).group(0)}'"
    if o["manager_not_level"]:
        t = NOT_LEVEL_MANAGER.sub(lambda m: m.group(0).replace("anager", "anagr"), t)   # 'Product Manager' is a job, not a level
    if INTERN.search(t) or kind_hint == "internship":
        return "Intern", "high", "title says intern" if INTERN.search(t) else "the site marks it as an internship"
    if kind_hint == "graduate":
        return "New grad / entry", "high", "the site marks it as a university / graduate job"
    if SENIOR.search(t) and not NEW_GRAD.search(t):
        return "Senior+", "high", f"title says '{SENIOR.search(t).group(0)}'"
    if NEW_GRAD.search(t):
        return "New grad / entry", "high", f"title says '{NEW_GRAD.search(t).group(0)}'"
    if o["title_level_first"] and MID.search(t):
        return "Mid", "high", f"title level '{MID.search(t).group(0)}'"
    if o["years_required_only"]:
        from careers.match import sections       # 'preferred: 1+ years of X' must not make a 2+ years job entry-level
        parts, has_req = sections(desc)
        if has_req:
            desc = parts["req"]
    yrs = levels.min_years(desc)
    if o["year_ranges"]:
        r = [int(m.group(1)) for m in RANGE_YEARS.finditer(str(desc or "")[:6000])]
        r = [y for y in r if y < 30]
        if r:
            yrs = min(r + ([yrs] if yrs is not None else []))
    if yrs is not None:
        if yrs <= 1:
            return "New grad / entry", "medium", f"description asks for {yrs}+ years"
        if yrs == 2:
            return "Early career (1–3 yrs)", "medium", f"description asks for {yrs}+ years"
        if yrs <= 5:
            return "Mid", "medium", f"description asks for {yrs}+ years"
        return "Senior+", "medium", f"description asks for {yrs}+ years"
    if MID.search(t):
        return "Mid", "medium", f"title level '{MID.search(t).group(0)}'"
    lv = levels.level(t, desc)
    if lv == "senior":
        return "Senior+", "medium", "senior wording in the description"
    if lv == "entry":
        return "New grad / entry", "medium", "entry wording in the description"
    return "Not stated", "low", "no level words or years found"


FRESHER_FIT = {"Intern": "fits", "New grad / entry": "fits", "Early career (1–3 yrs)": "stretch",
               "Not stated": "check", "Mid": "too senior", "Senior+": "too senior"}


def employment(title, desc, kind_hint=""):
    s = f"{title} {kind_hint}".lower()
    if INTERN.search(s):
        return "Internship"
    if re.search(r"\b(contract|contractor|freelance|temporary|fixed[- ]term)\b", s):
        return "Contract"
    if re.search(r"\bpart[- ]time\b", s):
        return "Part-time"
    return "Full-time"


def work_mode(location, desc):
    s = f"{location} {desc[:3000]}".lower()
    if re.search(r"\bhybrid\b", s):
        return "Hybrid"
    if re.search(r"\bremote\b", str(location).lower()):
        return "Remote"
    if re.search(r"\b(onsite|on-site|in office|in-office)\b", s):
        return "On-site"
    return "Not stated"


def classify(job, o=None):
    o = OPTS if o is None else o
    title, desc = str(job.get("title") or ""), str(job.get("desc") or "")
    fam, fam_conf, fam_ev = _family(title, desc, o)
    spec = specialties(title, desc)
    if fam == "Software Engineering" and len(ML_TERMS.findall(desc)) >= 4:
        spec = ["ML-heavy"] + spec
    lv, lv_conf, lv_ev = level(title, desc, job.get("kind_hint") or "", o)
    return {"family": fam, "family_conf": fam_conf, "family_evidence": fam_ev, "specialties": spec,
            "is_ml": fam in TECH_FAMILIES_ML or "ML-heavy" in spec,
            "level": lv, "level_conf": lv_conf, "level_evidence": lv_ev, "fresher_fit": FRESHER_FIT[lv],
            "employment": employment(title, desc, job.get("kind_hint") or ""),
            "work_mode": work_mode(job.get("location") or "", desc)}
