"""How well does each of your resumes fit a job, which one to send, and what to put in it.

Everything here is grounded: a skill counts as "yours" only if its words appear in that resume's text, and every
tip points at the exact resume line or the exact job requirement it came from. Nothing is invented, and no AI model
writes anything (so text inside a job post can't steer the advice).

Match % (per resume) = weighted share of the job's skills that the resume shows.
   weight 3 = skill in the job title, 2 = in the required / basic / minimum qualifications, 1 = anywhere else
   (preferred qualifications, responsibilities). Fewer than 3 skills found in the job → no % at all (the post says too little to judge; a "100%" from
   one skill would mislead).
Hard requirements (years, PhD, degree) are shown separately — a resume can't fix those.
"""
import re

MIN_SKILLS = 3          # a job must name at least this many skills before a match % is shown

# canonical skill → regex (whole words, case-insensitive). Kept broad but explicit, so every match is explainable.
SKILLS = {
    # languages
    "Python": r"python", "C++": r"c\+\+|cpp", "C": r"\bc\b(?![+#])", "Java": r"java(?!script)", "JavaScript": r"javascript|\bjs\b",
    "TypeScript": r"typescript", "Go": r"golang|\bgo\b(?= (?:language|lang|programming))", "Rust": r"\brust\b", "SQL": r"\bsql\b|mysql|postgres\w*",
    "R": r"\br\b(?= (?:programming|language|studio))|\brstudio\b", "MATLAB": r"matlab", "Bash / shell": r"\bbash\b|shell script\w*",
    # ML core
    "Machine learning": r"machine learning|\bml\b", "Deep learning": r"deep learning|neural networks?",
    "PyTorch": r"pytorch|torch\b", "TensorFlow": r"tensorflow|\btf2?\b|keras", "JAX": r"\bjax\b",
    "scikit-learn": r"scikit[- ]learn|sklearn", "XGBoost / boosting": r"xgboost|lightgbm|catboost|gradient boost\w*",
    "Statistics": r"statistic\w*|hypothesis test\w*|a/b test\w*|regression analysis",
    "Probability / linear algebra": r"linear algebra|probability|calculus",
    "Time series": r"time[- ]series|forecast\w*|arima", "Reinforcement learning": r"reinforcement learning|\brl\b|ppo|q-learning",
    "Optimisation": r"optimi[sz]ation|operations research|bayesian optimi[sz]ation",
    "Recommender systems": r"recommend\w* system\w*|recommender\w*|collaborative filtering",
    "Feature engineering": r"feature engineering",
    # GenAI / NLP
    "LLMs": r"\bllms?\b|large language models?|gpt-?\d?|gemini|llama|mistral|claude",
    "Transformers": r"transformers?\b|attention mechanism|bert\b",
    "Hugging Face": r"hugging ?face", "Fine-tuning (LoRA / PEFT)": r"fine-?tun\w*|\blora\b|qlora|\bpeft\b|sft\b|rlhf|dpo\b",
    "RAG": r"\brag\b|retrieval[- ]augmented", "Vector databases": r"vector (?:db|database|store|search)\w*|faiss|pinecone|chroma\w*|milvus|qdrant|weaviate|pgvector",
    "LangChain / LangGraph": r"langchain|langgraph|llamaindex|llama-index", "AI agents": r"\bai agents?\b|agentic|multi-agent|tool[- ]calling|function calling",
    "Prompt engineering": r"prompt engineering|prompting", "NLP": r"\bnlp\b|natural language processing|text classification|named entity|ner\b|sentiment",
    "Speech / audio": r"speech|\basr\b|\btts\b|whisper|audio", "Evaluation of models": r"model evaluation|evals?\b|benchmark\w*",
    # CV
    "Computer vision": r"computer vision|\bcv\b(?! ?\()|image (?:processing|classification|segmentation)",
    "OpenCV": r"opencv", "Object detection (YOLO etc.)": r"object detection|yolo\w*|detectron|faster r-?cnn",
    "Segmentation": r"segmentation|\bsam\b|u-?net", "Video understanding": r"video (?:analytics|understanding|processing)|action recognition|tracking",
    "Multimodal": r"multimodal|multi-modal|vision[- ]language|\bvlm\b|\bclip\b",
    "3D / point clouds": r"point clouds?|\b3d\b|lidar|nerf|slam",
    # MLOps / data
    "MLOps": r"mlops|ml ops|model (?:deployment|serving|monitoring)", "MLflow / experiment tracking": r"mlflow|weights (?:&|and) biases|\bwandb\b",
    "Docker": r"docker|containers?\b", "Kubernetes": r"kubernetes|\bk8s\b", "CI/CD": r"ci/cd|ci cd|github actions|jenkins|gitlab ci",
    "AWS": r"\baws\b|amazon web services|sagemaker|\bs3\b|\bec2\b|lambda\b", "GCP": r"\bgcp\b|google cloud|vertex ai|bigquery",
    "Azure": r"\bazure\b", "Spark / big data": r"spark|pyspark|hadoop|databricks|big data", "Airflow": r"airflow",
    "ONNX / TensorRT / quantisation": r"onnx|tensorrt|quanti[sz]\w*|openvino", "CUDA / GPU": r"cuda|\bgpus?\b|triton",
    "Distributed training": r"distributed training|deepspeed|fsdp|megatron|horovod",
    "Pandas / NumPy": r"pandas|numpy", "Data visualisation": r"matplotlib|seaborn|plotly|tableau|power ?bi|data visuali[sz]ation",
    "Data pipelines / ETL": r"\betl\b|data pipelines?|kafka",
    # software
    "REST APIs": r"rest(?:ful)? apis?|\bapis?\b", "FastAPI / Flask / Django": r"fastapi|flask|django",
    "React": r"react(?:\.js|js)?\b", "Git": r"\bgit\b|github|gitlab", "Linux": r"linux|unix",
    "System design": r"system design|distributed systems|scalab\w*", "Data structures & algorithms": r"data structures|algorithms",
    "Microservices": r"microservices?", "Testing": r"unit test\w*|pytest|test automation",
    # hardware / embedded (for completeness)
    "Embedded C / firmware": r"embedded c|firmware|rtos|microcontroller\w*|arduino|raspberry pi",
    "Verilog / RTL": r"verilog|systemverilog|\brtl\b|vhdl|fpga",
    "ROS / robotics": r"\bros2?\b|robot\w*",
    # domain
    "Bioinformatics": r"bioinformatic\w*|genomic\w*|protein|molecular", "Healthcare data": r"healthcare|medical imag\w*|clinical",
    "Finance / trading": r"trading|quantitative finance|stock market|fintech",
}
# using one of these shows the broader skill too (shown as "implied by …", never silently)
IMPLIES = {"PyTorch": ["Deep learning", "Machine learning"], "TensorFlow": ["Deep learning", "Machine learning"],
           "JAX": ["Deep learning", "Machine learning"], "scikit-learn": ["Machine learning"],
           "XGBoost / boosting": ["Machine learning"], "Deep learning": ["Machine learning"],
           "Transformers": ["Deep learning", "Machine learning"], "Fine-tuning (LoRA / PEFT)": ["LLMs", "Deep learning"],
           "RAG": ["LLMs"], "LangChain / LangGraph": ["LLMs"], "AI agents": ["LLMs"],
           "Object detection (YOLO etc.)": ["Computer vision", "Deep learning"], "Segmentation": ["Computer vision"],
           "OpenCV": ["Computer vision"], "Multimodal": ["Deep learning"], "Reinforcement learning": ["Machine learning"],
           "Computer vision": ["Machine learning"], "NLP": ["Machine learning"], "Kubernetes": ["Docker"],
           "FastAPI / Flask / Django": ["REST APIs"], "Pandas / NumPy": ["Python"]}
# the role itself asks for its core skill even when the text doesn't spell it out
FAMILY_CORE = {"ML Engineer / Applied Scientist": ["Machine learning"], "AI Research": ["Machine learning", "Deep learning"],
               "GenAI / LLM": ["LLMs"], "Computer Vision": ["Computer vision"], "MLOps / ML Platform": ["MLOps"],
               "Data Science": ["Statistics", "Machine learning"]}
_RX = {k: re.compile(r"(?<![A-Za-z0-9])(?:" + v + r")(?![A-Za-z0-9])", re.I) for k, v in SKILLS.items()}

REQ_HEAD = re.compile(r"(basic qualifications|minimum qualifications|required qualifications|requirements|"
                      r"what you(?:'|’)?ll need|what we(?:'|’)?re looking for|what we look for|what you bring|"
                      r"who you are|you(?:'|’)?re our person if|qualifications|must have|what we need to see)", re.I)
PREF_HEAD = re.compile(r"(preferred qualifications|nice to have|bonus|ways to stand out|good to have|"
                       r"preferred skills|it(?:'|’)?s a plus|plus if)", re.I)
OTHER_HEAD = re.compile(r"(about (?:the|this) (?:role|team|job)|responsibilities|what you(?:'|’)?ll do|"
                        r"about us|benefits|our commitment|equal opportunity)", re.I)
PHD = re.compile(r"\bph\.?d\b", re.I)
DEGREE = re.compile(r"\b(bachelor\w*|b\.?tech|b\.?e\.?|master\w*|m\.?tech|m\.?s\.?)\b", re.I)


def skills_in(text, implied=False):
    """{skill: first matching snippet} for a piece of text. implied=True adds skills shown by a more specific one."""
    out, t = {}, str(text or "")
    for k, rx in _RX.items():
        m = rx.search(t)
        if m:
            out[k] = m.group(0)
    if implied:
        for k in list(out):
            for b in IMPLIES.get(k, []):
                out.setdefault(b, f"implied by {k}")
    return out


def sections(desc):
    """Split a job description into required / preferred / other text by its headings (best effort)."""
    d = str(desc or "")[:8000]
    pref = [(m.start(), m.end()) for m in PREF_HEAD.finditer(d)]
    # "qualifications" inside "Preferred qualifications" is NOT a required heading
    req = [(m.start(), "req") for m in REQ_HEAD.finditer(d) if not any(a <= m.start() < b for a, b in pref)]
    marks = sorted(req + [(a, "pref") for a, _ in pref] + [(m.start(), "other") for m in OTHER_HEAD.finditer(d)])
    parts = {"req": "", "pref": "", "other": ""}
    if not marks:
        parts["other"] = d
        return parts, False
    parts["other"] += d[:marks[0][0]]
    for i, (pos, kind) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(d)
        parts[kind] += " " + d[pos:end]
    return parts, bool(parts["req"].strip())


def job_skills(job):
    """[{skill, weight, where, evidence}] — what the job asks for and where it says so."""
    parts, has_req = sections(job.get("desc"))
    found = {}
    for where, text, w in [("title", job.get("title"), 3), ("required", parts["req"], 2),
                           ("preferred", parts["pref"], 1), ("description", parts["other"], 1)]:
        for k, ev in skills_in(text).items():
            if k not in found or w > found[k]["weight"]:
                found[k] = {"skill": k, "weight": w, "where": where, "evidence": ev}
    if not has_req:       # no headings: everything counts the same
        for f in found.values():
            if f["where"] != "title":
                f.update(weight=1, where="description")
    fam = job.get("family")
    if fam is None:
        from careers.classify import classify
        fam = classify(job)["family"]
    for k in FAMILY_CORE.get(fam, []):
        if k not in found or found[k]["weight"] < 2:
            found[k] = {"skill": k, "weight": 2, "where": "role", "evidence": f"core of a {fam} role"}
    return sorted(found.values(), key=lambda f: (-f["weight"], f["skill"]))


def hard_requirements(job):
    parts, _ = sections(job.get("desc"))
    req = parts["req"] or str(job.get("desc") or "")
    out = []
    if PHD.search(req) and not re.search(r"ph\.?d\.?\s*(?:is\s+)?(?:preferred|a plus|optional)|or (?:a )?ph\.?d|ph\.?d\.?,?\s*or\b", req, re.I):
        out.append("asks for a PhD")
    from common import levels
    y = levels.min_years(job.get("desc"))
    if y:
        out.append(f"asks for {y}+ years of experience")
    return out


def resume_lines(text):
    return [l.strip(" •-–*\t") for l in re.split(r"[\r\n]+", str(text or "")) if len(l.strip()) > 2]


def where_in_resume(skill, lines):
    for k in [skill] + [a for a, bs in IMPLIES.items() if skill in bs]:
        for l in lines:
            if _RX[k].search(l):
                return l[:160]
    return None


def match_one(job, resume, js=None):
    js = js if js is not None else job_skills(job)
    have = skills_in(resume["text"], implied=True)
    total = sum(f["weight"] for f in js) or 1
    got = [f for f in js if f["skill"] in have]
    pct = round(100 * sum(f["weight"] for f in got) / total)
    conf = "low" if len(js) < 3 else "medium" if len(js) < 6 else "high"
    return {"resume": resume["name"], "pct": pct if len(js) >= MIN_SKILLS else None, "confidence": conf,
            "matched": [f["skill"] for f in got], "missing": [f["skill"] for f in js if f["skill"] not in have],
            "n_job_skills": len(js)}


def advise(job, resumes):
    """Full advice for one job: every resume's match, the one to send, and grounded resume key points."""
    if not resumes:
        return {"resumes": [], "best": None, "points": [], "hard": hard_requirements(job), "job_skills": job_skills(job),
                "note": "Upload your resumes (Resumes tab) to see match %, the best one to send and what to change."}
    js = job_skills(job)
    res = [match_one(job, r, js) for r in resumes]
    best_i = max(range(len(res)), key=lambda i: ((res[i]["pct"] or 0), -i))
    best, br = res[best_i], resumes[best_i]
    lines = resume_lines(br["text"])
    w = {f["skill"]: f for f in js}
    points = []
    lead = [s for s in best["matched"] if w[s]["weight"] >= 2][:5]
    if lead:
        points.append({"kind": "lead", "text": "Put these near the top (the job asks for them and you have them): " +
                       ", ".join(lead),
                       "evidence": [{"skill": s, "resume_line": where_in_resume(s, lines), "job_says": w[s]["evidence"],
                                     "where": w[s]["where"]} for s in lead]})
    elsewhere = []
    for s in best["missing"]:
        for r, m in zip(resumes, res):
            if r is not br and s in m["matched"]:
                elsewhere.append({"skill": s, "from_resume": r["name"], "resume_line": where_in_resume(s, resume_lines(r["text"]))})
                break
    if elsewhere:
        points.append({"kind": "borrow", "text": "Your other resumes already show these — copy that line in: " +
                       ", ".join(f"{e['skill']} (from {e['from_resume']})" for e in elsewhere[:5]), "evidence": elsewhere[:5]})
    gaps = [s for s in best["missing"] if s not in {e["skill"] for e in elsewhere}]
    req_gaps = [s for s in gaps if w[s]["weight"] >= 2]
    if req_gaps:
        points.append({"kind": "gap", "text": "Asked for but not in any of your resumes — add ONLY if you have really "
                       "used it (a project or course line): " + ", ".join(req_gaps[:6]),
                       "evidence": [{"skill": s, "job_says": w[s]["evidence"], "where": w[s]["where"]} for s in req_gaps[:6]]})
    words = sorted({w[s]["evidence"] for s in best["matched"]
                    if w[s]["where"] != "role" and w[s]["evidence"].lower() != s.lower()})[:6]
    if words:
        points.append({"kind": "wording", "text": "Use the job's own words so screening software finds them: " +
                       ", ".join(f"“{x}”" for x in words), "evidence": []})
    hard = hard_requirements(job)
    return {"resumes": res, "best": best["resume"], "points": points, "hard": hard, "job_skills": js,
            "note": "Match % = share of the job's skills your resume shows (title ×3, required ×2, other ×1)."}


def quick(js, have):
    """Fast match % from precomputed job skills (js) and a resume's skill dict (have)."""
    total = sum(f["weight"] for f in js)
    if not total or len(js) < MIN_SKILLS:
        return None
    return round(100 * sum(f["weight"] for f in js if f["skill"] in have) / total)


def best_for(js, resumes_have):
    """→ (best %, best resume name) over [(name, have)]."""
    best = (None, None)
    for name, have in resumes_have:
        p = quick(js, have)
        if p is not None and (best[0] is None or p > best[0]):
            best = (p, name)
    return best
