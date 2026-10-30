"""Job finder pipeline (startups, people, work emails, outreach plan) — runs weekly on GitHub Actions.
Generated from the Colab notebook. Edit settings in config.py, not here.
  DATA_DIR=data python jobs/pipeline.py
"""
# ---- notes
# # Startup & Job Finder v3 (India first, strong contacts, free-tier stacked)
#
# For every company in your fields, this notebook finds:
# - **Company profile:** founded, city, what they build, products, research and discoveries, funding rounds and investors.
# - **People:** founders, CEO, CTO, heads of AI or research, directors and hiring leads. Each person is checked across **6 sources**: the company site, structured data on the site, LinkedIn (through search), company registry records, news, and Hunter.io.
# - **Work emails:** each email gets a **grade (A–D)** that says how sure we are, plus where it came from. Emails are confirmed with the mail-server check, the company's email pattern (learned from real examples) and the Hunter verifier.
# - **Who to contact first:** for each company, the best person, a backup, the hiring contact, the channel to use, a talking point linked to your projects, and a short LinkedIn note.
# - **Open roles:** live jobs from Greenhouse, Lever, Ashby, Workable and SmartRecruiters, plus careers pages.
#
# Ranking: **Indian startups → other startups → Indian corporates → global corporates.** Bioinformatics, supply chain and SDL come first in each tier.
#
# ### Email grades
# | Grade | Meaning | Send? |
# |---|---|---|
# | **A · verified** | A verifier (ZeroBounce or Hunter) says the mailbox exists | Yes |
# | **A · published** | Shown publicly for this person (company site, structured data) | Yes |
# | **B · strong** | Found in public data (web, GitHub, Hunter ≥70%), or built from a pattern confirmed by 2+ real emails | Yes, usually fine |
# | **C · likely** | Built from a pattern seen once, or from Hunter's pattern | Verify first |
# | **D · guess** | Common pattern, no proof | Verify first, or use LinkedIn |
#
# ### Keys (🔑 Secrets icon on the left, turn on Notebook access)
# | Key | Needed? | Free tier | What it adds |
# |---|---|---|---|
# Every key except Gemini is optional. Each one you add stacks more free capacity. None needs a card.
#
# | Key | Free tier (Oct 2026) | What it adds |
# |---|---|---|
# | `GEMINI_API_KEY` | **required** · daily limits per model (see AI Studio) | reads pages, builds profiles, writes drafts |
# | `GROQ_API_KEY` | ~1,000 requests/day on big models | backup AI when Gemini's daily limit runs out |
# | `TOMBA_KEY` + `TOMBA_SECRET` | 25 searches / 30 days, up to 10 emails each | best-value email finder → used first |
# | `HUNTER_API_KEY` | 50 credits / month (1 per email found, 0.5 per verification) | email pattern + verification |
# | `ZEROBOUNCE_API_KEY` | 100 verifications / month | main email verifier |
# | `SERPER_API_KEY` | 2,500 Google searches, one-time | LinkedIn people search (much better than DuckDuckGo) |
# | `TAVILY_API_KEY` | 1,000 searches / month | backup search when DuckDuckGo blocks |
# | `JINA_API_KEY` | works without a key (20/min); free key = 500/min | reads JavaScript-heavy websites |
# | `GITHUB_TOKEN` | 5,000 calls / hour (60 without) | email-pattern evidence from public commits |
#
# Use one account per service. Making extra accounts to get more free credits breaks their terms, and they ban it.
#
# ### Cells
# | Cell | What it does | Time (first run) |
# |---|---|---|
# | 1–3 | Install, settings, helpers | 1 min |
# | 4 | Find companies | 15–25 min |
# | 5 | Profile companies (40 per run) | 20–30 min |
# | 6 | Open roles | 2–5 min |
# | 7 | **Find people** (40 companies per run) | 15–25 min |
# | 8 | **Work emails + verification** | 3–8 min |
# | 9 | Rank | instant |
# | 10 | **Outreach plan** | instant |
# | 11 | Email drafts for top companies (optional) | 2–3 min |
# | 12 | Export to Excel | instant |
#
# Every step saves to `MyDrive/job_finder/`. If you stop, or a free limit runs out, rerun the cell later and it continues.

# ----------------------------------------------------------------------
# CELL 1 — Install libraries, read keys, connect Google Drive

import os, json, re, time, random, html
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from urllib.parse import urlparse, urljoin
from urllib import robotparser

import requests
import pandas as pd
from bs4 import BeautifulSoup
from ddgs import DDGS
from google import genai

try:
    from google.colab import userdata, drive, files
    IN_COLAB = True
except ImportError:
    IN_COLAB = False


def get_secret(name):
    if IN_COLAB:
        try:
            return userdata.get(name)
        except Exception:
            return None
    return os.environ.get(name)


GEMINI_KEY = get_secret("GEMINI_API_KEY")
HUNTER_KEY = get_secret("HUNTER_API_KEY")
SERPER_KEY = get_secret("SERPER_API_KEY")
GITHUB_TOKEN = get_secret("GITHUB_TOKEN")
GROQ_KEY = get_secret("GROQ_API_KEY")
TOMBA_KEY, TOMBA_SECRET = get_secret("TOMBA_KEY"), get_secret("TOMBA_SECRET")
ZEROBOUNCE_KEY = get_secret("ZEROBOUNCE_API_KEY")
TAVILY_KEY = get_secret("TAVILY_API_KEY")
JINA_KEY = get_secret("JINA_API_KEY")
assert GEMINI_KEY, "Add GEMINI_API_KEY in Colab Secrets (key icon on the left) and turn on Notebook access."

OUT_DIR = os.path.join(os.environ.get("DATA_DIR", "data"), "jobs")   # synced with the private HF dataset
os.makedirs(OUT_DIR, exist_ok=True)

def display(df):   # notebook display() -> log output
    try:
        print(df.head(15).to_string(max_colwidth=40))
    except Exception:
        print(df)

print("Saving to:", OUT_DIR)
for k, v in [("Groq (backup AI)", GROQ_KEY), ("Tomba (finder)", TOMBA_KEY and TOMBA_SECRET),
             ("Hunter (finder+verify)", HUNTER_KEY), ("ZeroBounce (verify)", ZEROBOUNCE_KEY),
             ("Serper (Google search)", SERPER_KEY), ("Tavily (backup search)", TAVILY_KEY),
             ("Jina key (JS sites)", JINA_KEY), ("GitHub token", GITHUB_TOKEN)]:
    print(f"{k:24s}", "yes" if v else "no")

# ----------------------------------------------------------------------
# CELL 2 — Settings: edit these

# ---------- Sectors to search (no finance) ----------
# Priority 1 = your main fields: searched in depth. Priority 2 = broad interests: lighter search.
SEARCH_TERMS = {
    # priority 1
    "bioinformatics": ["bioinformatics", "computational biology", "AI drug discovery"],
    "supply chain":   ["supply chain AI", "logistics tech"],
    "SDL":            ["self-driving lab", "lab automation AI"],
    # priority 2
    "healthtech":      ["healthtech AI"],
    "climate":         ["climate tech", "cleantech energy AI"],
    "agritech":        ["agritech AI"],
    "robotics":        ["robotics", "drone"],
    "defence tech":    ["defence tech"],
    "quantum":         ["quantum computing"],
    "semiconductors":  ["semiconductor chip design"],
    "spacetech":       ["spacetech"],
    "materials":       ["materials science AI"],
    "manufacturing":   ["industrial AI manufacturing"],
    "IoT/embedded":    ["IoT embedded systems"],
    "computer vision": ["computer vision AI"],
    "generative AI":   ["generative AI LLM"],
}
TOP_DOMAINS = ["bioinformatics", "supply chain", "SDL"]
PRIORITY = {d: (1 if d in TOP_DOMAINS else 2) for d in SEARCH_TERMS}

# Words that mark a company as working in your main fields (used for ranking and the YC directory)
INTEREST_WORDS = {
    "bioinformatics": ["bioinformatics", "genomic", "genome", "proteomic", "computational biology", "drug discovery",
                       "protein", "sequencing", "omics", "molecular", "biotech", "single-cell", "precision medicine"],
    "supply chain": ["supply chain", "logistics", "inventory", "demand forecast", "warehouse", "procurement",
                     "freight", "fleet", "last-mile", "route optimi", "fulfilment", "fulfillment"],
    "SDL": ["lab automation", "self-driving lab", "autonomous lab", "high-throughput", "bayesian optimi",
            "materials discovery", "robotic lab", "experiment design", "closed-loop", "active learning"],
}

CITIES = ["Bengaluru", "Pune", "Mumbai", "Hyderabad"]
USE_YC_DIRECTORY = True   # also pull Indian startups from the public Y Combinator directory

# Companies you already know. They skip discovery and go straight to profiling.
EXTRA_COMPANIES = [
    # {"name": "Company Name", "website": "https://company.com", "domain": "bioinformatics", "type": "startup"},
]

# ---------- About you (used for ranking, talking points and drafts — not for scraping) ----------
PROFILE = {
    "name": "Daksh",
    "intro": "a final-year B.Tech AI student at NMIMS MPSTME, Mumbai (graduating 2027)",
    "github": "github.com/GeekDaksh",
    "skills": ["Python", "PyTorch", "scikit-learn", "TensorFlow", "LangGraph", "FAISS",
               "Bayesian optimization", "BoTorch", "computer vision", "reinforcement learning",
               "machine learning", "deep learning", "LLM", "C++", "embedded"],
    # Each project: a short name for messages + words that link it to a company's work. Check these.
    "projects": [
        {"name": "Self-Driving Lab for M-Sand concrete (Bayesian optimisation)", "short": "a self-driving lab for concrete mix design",
         "keywords": ["self-driving lab", "lab automation", "bayesian optimi", "experiment design", "materials", "active learning",
                      "closed-loop", "optimization", "optimisation", "high-throughput"]},
        {"name": "Battery management multi-agent system (BMS)", "short": "a multi-agent battery management system",
         "keywords": ["battery", "bms", "energy storage", "electric vehicle", "multi-agent", "energy", "ev charging"]},
        {"name": "FARM-AID", "short": "FARM-AID",
         "keywords": ["agri", "farm", "crop", "agritech", "agriculture"]},
        {"name": "Ballistics fire-control simulation (L&T internship)", "short": "a ballistics fire-control simulation at L&T",
         "keywords": ["simulation", "defence", "defense", "fire control", "ballistic", "drone"]},
        # {"name": "<your publication title>", "short": "my paper on ...", "keywords": ["..."]},
    ],
}

# Job titles containing any of these words are marked "relevant"
PREFERRED_ROLES = ["AI", "ML", "machine learning", "deep learning", "data scientist", "data science",
                   "research", "researcher", "scientist", "bioinformatics", "computational",
                   "automation", "robotics", "computer vision", "LLM", "NLP", "intern", "internship",
                   "graduate", "fresher", "trainee", "new grad", "embedded", "python", "optimization"]

# ---------- People search ----------
PEOPLE_PER_RUN = 40          # companies searched for people per run of Cell 7
LINKEDIN_ROLE_WORDS = ["founder", "CTO", "head", "director", "scientist", "talent acquisition"]   # startups
LINKEDIN_ROLE_WORDS_CORP = ["head of AI", "director", "research", "talent acquisition"]          # corporates
PEOPLE_ENOUGH = 5            # stop LinkedIn searches for a company once this many key people are found
SEARCH_CACHE_DAYS = 30       # reuse a search result for this many days

# ---------- Time budget (GitHub's job limit is 2 hours; free minutes are limited) ----------
# Each stage stops at its share of the budget; unfinished work is saved and continues on the next run.
RUN_START = time.time()
RUN_BUDGET_MIN = float(os.environ.get("JOB_FINDER_BUDGET_MIN", "100"))
STAGE_END = {"discovery": 0.30, "extract": 0.40, "profile": 0.62, "people": 0.78, "emails": 0.88, "drafts": 0.94}
DISCOVERY_PER_RUN = 150      # web searches per run for finding new companies (the rest continue next run)

def stage_over(stage):
    """True once this stage has used its share of the run's time budget."""
    over = time.time() - RUN_START > STAGE_END[stage] * RUN_BUDGET_MIN * 60
    if over and stage not in _stage_logged:
        _stage_logged.add(stage)
        print(f"  ⏱ {stage}: time share used — the rest continues next run")
    return over

_stage_logged = set()

# ---------- Free-tier budgets ----------
MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]   # tried first; other free Gemini/Gemma models are added automatically
GROQ_MODELS = ["llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b-16e-instruct", "openai/gpt-oss-120b"]
GEMINI_PAUSE = 7             # seconds between Gemini calls (free tier allows about 10 per minute)
SEARCH_PAUSE = 2             # seconds between DuckDuckGo searches; raise to 4 if searches start failing
SEARCH_REGION = "in-en"
SERPER_MAX_PER_RUN = 400     # Google searches per run of a cell (2,500 free in total)
TAVILY_MAX_PER_RUN = 300     # backup searches per run (1,000 free / month)
ENRICH_PER_RUN = 40          # companies profiled per run of Cell 5
TOMBA_SEARCH_MAX = 25        # Tomba domain searches per run (free: 25 / 30 days, up to 10 emails each)
HUNTER_EMAILS_PER_DOMAIN = 1 # Hunter charges 1 credit PER EMAIL found; 1 email still returns the company's pattern
HUNTER_SEARCH_MAX = 15       # Hunter credits spent on domain searches per run (rest of the 50 go to verification)
HUNTER_VERIFY_MAX = 60       # Hunter verifications per run (0.5 credit each)
ZEROBOUNCE_VERIFY_MAX = 100  # ZeroBounce verifications per run (free: 100 / month)
VERIFY_TRIES_PER_PERSON = 2  # if a guess fails verification, try the next pattern
GITHUB_REPOS_PER_COMPANY = 3
DRAFT_TOP_N = 15             # Cell 11 writes email drafts for this many top companies
RETRY_FAILED = False         # True = Cell 5 retries companies that failed last time

# ---- shared settings from config.py (the single file you edit) ----
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as _cfg
from common import settings as _settings
_S = _settings.load(os.environ.get("DATA_DIR", "data"))        # your picks from the app's Settings tab
SEARCH_TERMS = _settings.search_terms(_S)                      # chosen sectors
TOP_DOMAINS = list(_S["main_sectors"])                         # searched in depth, ranked first
CITIES = _settings.cities(_S) or ["Bengaluru"]                 # chosen cities
EXTRA_COMPANIES = _cfg.EXTRA_COMPANIES
PRIORITY = {d: (1 if d in TOP_DOMAINS else 2) for d in SEARCH_TERMS}
INTEREST_WORDS = {k: v for k, v in INTEREST_WORDS.items() if k in SEARCH_TERMS}
PREFERRED_ROLES = sorted(set(_settings.role_words(_S)) | {"intern", "internship", "graduate", "fresher", "trainee",
                                                           "junior", "entry level", "associate"})
PROFILE.update({"name": _cfg.PROFILE["first_name"], "intro": _cfg.PROFILE["intro"],
                "skills": _cfg.PROFILE["skills"], "projects": _cfg.PROFILE["projects"]})
DISCOVERY_REFRESH_DAYS = 30  # re-run discovery searches monthly so new startups keep appearing

# ----------------------------------------------------------------------
# CELL 3 — Helper functions (nothing to edit)

client = genai.Client(api_key=GEMINI_KEY)

# Keep only models your key can use
try:
    _avail = [m.name.split("/")[-1] for m in client.models.list()
              if "generateContent" in (getattr(m, "supported_actions", None) or [])]
    _skip = ["image", "tts", "audio", "live", "embedding", "preview", "exp", "thinking", "nano", "robotics", "computer"]
    _ok = [m for m in MODELS if m in _avail]
    # every model has its OWN free daily quota, so more models = more free calls per day
    _extra = [m for m in _avail if m not in _ok and ("flash" in m or "gemma-3-27b" in m or "gemma-3-12b" in m)
              and not any(x in m for x in _skip)]
    MODELS = (_ok + sorted(_extra, key=lambda m: ("gemma" in m, "lite" in m, m))) or MODELS
except Exception as e:
    print("Could not list models; using the configured list.", str(e)[:100])
print("Gemini models:", MODELS)

# ---------- Saving progress ----------
def fpath(name):
    return os.path.join(OUT_DIR, name)

def load_json(name, default):
    try:
        with open(fpath(name)) as f:
            return json.load(f)
    except Exception:
        return default

def save_json(name, obj):
    tmp = fpath(name) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=list)
    os.replace(tmp, fpath(name))

def today():
    return datetime.now().strftime("%Y-%m-%d")

# ---------- Gemini ----------
def parse_json(text):
    if not text:
        return None
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(t)
    except Exception:
        pass
    starts = sorted(i for i in (t.find("["), t.find("{")) if i != -1)
    for a in starts:
        b = t.rfind("]" if t[a] == "[" else "}")
        if b > a:
            try:
                return json.loads(t[a:b + 1])
            except Exception:
                pass
    return None

_dead_models = set()

def gemini_exhausted():
    """True when every free AI model (Gemini, Gemma and Groq) is used up for today."""
    return all(m in _dead_models for m in MODELS) and groq_exhausted()

def ask_gemini(prompt, temperature=0.1):
    """Send a prompt, get parsed JSON back (or None). Moves to the next model on a daily limit."""
    for model in MODELS:
        if model in _dead_models:
            continue
        for attempt in range(4):
            try:
                cfg = {"temperature": temperature}
                if "gemma" not in model:   # Gemma models don't support JSON mode; parse_json handles their text
                    cfg["response_mime_type"] = "application/json"
                r = client.models.generate_content(model=model, contents=prompt, config=cfg)
                time.sleep(GEMINI_PAUSE)
                out = parse_json(r.text)
                if out is not None:
                    return out
            except Exception as e:
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    if "PerDay" in msg or "per day" in msg.lower():
                        print(f"  {model}: daily limit reached")
                        _dead_models.add(model)
                        break
                    wait = 30 * (attempt + 1)
                    print(f"  rate limit, waiting {wait}s")
                    time.sleep(wait)
                elif any(c in msg for c in ("500", "503", "UNAVAILABLE", "INTERNAL", "DEADLINE")):
                    time.sleep(10 * (attempt + 1))
                elif "404" in msg or "NOT_FOUND" in msg:
                    _dead_models.add(model)
                    break
                else:
                    print("  Gemini error:", msg[:200])
                    break
    return ask_groq(prompt, temperature)   # all Gemini models used up today -> Groq


_groq_dead = set()
GROQ_MAX_CHARS = 24000   # Groq's free per-minute token limit is small, so long prompts are trimmed

def groq_exhausted():
    return not GROQ_KEY or all(m in _groq_dead for m in GROQ_MODELS)

def ask_groq(prompt, temperature=0.1):
    if groq_exhausted():
        return None
    wrapped = ('Answer with ONE JSON object of the form {"result": <your answer>}.\n\n' + prompt)[:GROQ_MAX_CHARS]
    for model in GROQ_MODELS:
        if model in _groq_dead:
            continue
        for attempt in range(3):
            try:
                r = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=90,
                                  headers={"Authorization": f"Bearer {GROQ_KEY}"},
                                  json={"model": model, "temperature": temperature,
                                        "response_format": {"type": "json_object"},
                                        "messages": [{"role": "user", "content": wrapped}]})
            except Exception:
                time.sleep(10)
                continue
            if r.status_code == 200:
                out = parse_json(r.json()["choices"][0]["message"]["content"])
                time.sleep(3)
                if isinstance(out, dict) and "result" in out:
                    return out["result"]
                if out is not None:
                    return out
                break
            if r.status_code == 429:
                if any(k in r.text for k in ("per day", "RPD", "TPD")):
                    _groq_dead.add(model)
                    break
                time.sleep(20 * (attempt + 1))
            elif r.status_code in (400, 404, 413):
                if r.status_code == 404 or "model" in r.text.lower() and "decommission" in r.text.lower():
                    _groq_dead.add(model)
                break
            else:
                time.sleep(10)
    return None

# ---------- Web search: DuckDuckGo, with Google (Serper) as backup / for people ----------
_serper_used = 0

_ddg_fails = 0

def ddg_search(query, n=10):
    """DuckDuckGo. After 4 blocked searches in a row it is skipped for the rest of the run (it blocks
    cloud machines for a while, and each blocked try costs up to a minute of back-off)."""
    global _ddg_fails
    if _ddg_fails >= 4:
        return None
    for attempt in range(3):
        try:
            res = DDGS().text(query, region=SEARCH_REGION, max_results=n) or []
            time.sleep(SEARCH_PAUSE + random.random())
            _ddg_fails = 0
            return [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
                    for r in res if r.get("href")]
        except Exception as e:
            if "no results" in str(e).lower():
                _ddg_fails = 0
                return []
            time.sleep(SEARCH_PAUSE * 4 * (attempt + 1))
    _ddg_fails += 1
    if _ddg_fails == 4:
        print("  DuckDuckGo is blocking this machine — skipping it for the rest of this run")
    return None   # None = search failed (blocked), [] = no results

def serper_search(query, n=10):
    global _serper_used
    if not SERPER_KEY or _serper_used >= SERPER_MAX_PER_RUN:
        return None
    try:
        r = requests.post("https://google.serper.dev/search", timeout=20,
                          headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                          json={"q": query, "gl": "in", "num": n})
        _serper_used += 1
        if r.status_code != 200:
            return None
        return [{"title": o.get("title", ""), "url": o.get("link", ""), "snippet": o.get("snippet", "")}
                for o in r.json().get("organic", []) if o.get("link")]
    except Exception:
        return None

_tavily_used = 0

def tavily_search(query, n=10):
    global _tavily_used
    if not TAVILY_KEY or _tavily_used >= TAVILY_MAX_PER_RUN:
        return None
    body = {"query": query, "max_results": n, "search_depth": "basic"}
    m = re.search(r"\bsite:(\S+)", query)
    if m:   # Tavily uses a domain filter instead of the site: operator
        body["include_domains"] = [m.group(1).split("/")[0]]
        body["query"] = re.sub(r"\bsite:\S+\s*", "", query).strip()
    try:
        r = requests.post("https://api.tavily.com/search", json=body, timeout=30,
                          headers={"Authorization": f"Bearer {TAVILY_KEY}"})
        _tavily_used += 1
        if r.status_code != 200:
            return None
        return [{"title": o.get("title", ""), "url": o.get("url", ""), "snippet": o.get("content", "")}
                for o in r.json().get("results", []) if o.get("url")]
    except Exception:
        return None

def web_search_raw(query, n=10, prefer_google=False):
    """List of results, or None if every search engine failed.
    Normal: DuckDuckGo (free) -> Tavily -> Serper.  People searches: Serper (Google) -> Tavily -> DuckDuckGo."""
    order = [serper_search, tavily_search, ddg_search] if prefer_google else [ddg_search, tavily_search, serper_search]
    res = None
    for engine in order:
        res = engine(query, n)
        if res is not None:
            break
    if res is None:
        print("  search failed:", query)
    return res

def web_search(query, n=10, prefer_google=False):
    return web_search_raw(query, n, prefer_google) or []

_search_cache = load_json("search_cache.json", {})
_cache_new = 0

def cached_search(query, n=10, prefer_google=False):
    """web_search with a saved cache, so reruns cost no searches."""
    global _cache_new
    hit = _search_cache.get(query)
    if hit and hit["date"] >= (datetime.now() - timedelta(days=SEARCH_CACHE_DAYS)).strftime("%Y-%m-%d"):
        return hit["results"]
    res = web_search_raw(query, n, prefer_google)
    if res is not None:   # cache empty results too, so reruns don't repeat them
        _search_cache[query] = {"date": today(), "results": res}
        _cache_new += 1
        if _cache_new % 20 == 0:
            save_json("search_cache.json", _search_cache)
    return res or []

def flush_search_cache():
    save_json("search_cache.json", _search_cache)

# ---------- Fetching pages (respects robots.txt) ----------
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"),
    "Accept-Language": "en-IN,en;q=0.9",
})
_robots = {}

def allowed(url):
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = robotparser.RobotFileParser()
        try:
            r = SESSION.get(base + "/robots.txt", timeout=8)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch("*", url)

def fetch(url, timeout=15):
    """Return (html, final_url) or (None, url)."""
    try:
        if not allowed(url):
            return None, url
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code != 200 or "html" not in r.headers.get("Content-Type", "").lower():
            return None, url
        return r.text, r.url
    except Exception:
        return None, url

_jina_last = 0.0

def fetch_rendered(url, timeout=40):
    """Read a JavaScript-heavy page through the free Jina Reader (renders it in a real browser)."""
    global _jina_last
    try:
        if not allowed(url):
            return None, url
        wait = (0.2 if JINA_KEY else 3.2) - (time.time() - _jina_last)   # 20/min without a key
        if wait > 0:
            time.sleep(wait)
        h = {"X-Return-Format": "html"}
        if JINA_KEY:
            h["Authorization"] = f"Bearer {JINA_KEY}"
        r = SESSION.get("https://r.jina.ai/" + url, headers=h, timeout=timeout)
        _jina_last = time.time()
        return (r.text, url) if r.status_code == 200 and len(r.text.strip()) > 40 else (None, url)
    except Exception:
        return None, url

def get_json(url, params=None, timeout=20, headers=None):
    try:
        r = SESSION.get(url, params=params, timeout=timeout, headers=headers)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def page_text(html, limit=2500):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "iframe"]):
        t.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()[:limit]

# ---------- Names, domains, places ----------
LEGAL = r"\b(pvt|private|ltd|limited|llp|inc|corp|corporation|co|gmbh|plc)\b\.?"

def norm_name(n):
    n = str(n or "").lower().replace("&", " and ")
    n = re.sub(LEGAL, " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()

def clean_company(n):
    """Company name without 'Pvt Ltd' etc., original casing — for search queries."""
    n = re.sub(r"[\s,]+(pvt\.?|private|ltd\.?|limited|llp|inc\.?|corp\.?)(\s|$).*$", "", str(n), flags=re.I)
    return n.strip() or str(n)

def domain_of(url):
    if not url or not isinstance(url, str):
        return None
    if "://" not in url:
        url = "https://" + url
    d = urlparse(url).netloc.lower().split(":")[0]
    d = d[4:] if d.startswith("www.") else d
    return d or None

NOT_COMPANY = {
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com", "wikipedia.org",
    "crunchbase.com", "tracxn.com", "inc42.com", "yourstory.com", "entrackr.com", "indiatimes.com",
    "livemint.com", "moneycontrol.com", "business-standard.com", "thehindu.com", "thehindubusinessline.com",
    "techcrunch.com", "forbes.com", "forbesindia.com", "medium.com", "glassdoor.com", "glassdoor.co.in",
    "naukri.com", "indeed.com", "wellfound.com", "angel.co", "ambitionbox.com", "zaubacorp.com", "tofler.in",
    "f6s.com", "startupindia.gov.in", "seedtable.com", "ensun.io", "builtin.com", "cbinsights.com",
    "pitchbook.com", "zoominfo.com", "rocketreach.co", "apollo.io", "owler.com", "quora.com", "reddit.com",
    "github.com", "google.com", "bing.com", "instahyre.com", "cutshort.io", "internshala.com", "foundit.in",
    "shine.com", "ndtv.com", "vccircle.com", "the-ken.com", "analyticsindiamag.com", "failory.com",
    "topstartups.io", "dealroom.co", "craft.co", "signalhire.com", "lusha.com", "contactout.com", "theorg.com",
    "economictimes.com", "financialexpress.com", "deccanherald.com", "hindustantimes.com", "medianama.com",
    "startuptalky.com", "growthlist.co", "clutch.co", "goodfirms.co", "justdial.com", "indiamart.com",
    "thecompanycheck.com", "falconebiz.com", "instafinancials.com", "opencorporates.com", "ycombinator.com",
}
SKIP_FOR_DISCOVERY = {"youtube.com", "facebook.com", "instagram.com", "x.com", "twitter.com", "pinterest.com"}
REGISTRY_SITES = {"zaubacorp.com", "tofler.in", "thecompanycheck.com", "falconebiz.com", "instafinancials.com",
                  "opencorporates.com", "companydetails.in", "indiafilings.com"}

def in_set(dom, s):
    return bool(dom) and any(dom == d or dom.endswith("." + d) for d in s)

def is_non_company(dom):
    return in_set(dom, NOT_COMPANY)

def at_domain(email, dom):
    d = email.split("@")[-1].lower()
    return bool(dom) and (d == dom or d.endswith("." + dom))

INDIAN_CITIES = ["bengaluru", "bangalore", "pune", "mumbai", "hyderabad", "delhi", "new delhi", "gurugram",
                 "gurgaon", "noida", "chennai", "kolkata", "ahmedabad", "kochi", "jaipur", "chandigarh", "thane",
                 "navi mumbai", "indore", "coimbatore", "trivandrum", "thiruvananthapuram", "mysuru", "mysore",
                 "bhubaneswar", "vadodara", "nagpur", "goa", "lucknow", "india"]

def is_india(country=None, city=None, website=None):
    if country and "india" in str(country).lower():
        return True
    if city and any(c in str(city).lower() for c in INDIAN_CITIES):
        return True
    d = domain_of(website) or ""
    return d.endswith(".in")

TIER_LABEL = {1: "1 · India startup", 2: "2 · Startup (outside India)",
              3: "3 · India corporate / lab", 4: "4 · Global corporate"}

def tier_of(india, ctype, is_startup):
    startup = is_startup is True or (is_startup is None and str(ctype).lower() == "startup")
    if startup and india:
        return 1
    if startup:
        return 2
    return 3 if india else 4

def company_tier(p):
    pr, inp = p.get("profile") or {}, p["input"]
    india = is_india(pr.get("country") or inp.get("country"), pr.get("hq_city") or inp.get("city"), p.get("website"))
    return tier_of(india, inp.get("type"), pr.get("is_startup"))

def work_order(profiles):
    """Profiled companies, best first: India startups, then priority-1 fields."""
    ok = [n for n, p in profiles.items() if p.get("status") == "ok"]
    return sorted(ok, key=lambda n: (company_tier(profiles[n]), profiles[n]["input"].get("priority") or 2))

def mentions(text, company):
    """True if the company name appears in the text as whole words."""
    t, c = " " + norm_name(text) + " ", norm_name(company)
    if not c:
        return False
    if " " + c + " " in t:
        return True
    cc = c.replace(" ", "")
    return len(cc) >= 6 and cc in t.replace(" ", "")

# ---------- Emails ----------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
OBFUSCATED_RE = re.compile(
    r"([A-Za-z0-9._%+-]+)\s*[\[\(\{<]\s*at\s*[\]\)\}>]\s*([A-Za-z0-9-]+(?:\s*(?:[\[\(\{<]\s*dot\s*[\]\)\}>]|\.)\s*[A-Za-z0-9-]+)+)", re.I)
BAD_EMAIL_END = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")
BAD_EMAIL_DOMAINS = ("example.com", "sentry.io", "wixpress.com", "domain.com", "email.com",
                     "yourdomain.com", "sentry-next.wixpress.com", "company.com", "yourcompany.com")
FREE_MAIL = {"gmail.com", "yahoo.com", "yahoo.co.in", "outlook.com", "hotmail.com", "rediffmail.com",
             "protonmail.com", "proton.me", "icloud.com", "live.com", "zohomail.in"}
GENERIC_LOCAL = {"info", "contact", "hello", "hi", "support", "careers", "career", "jobs", "hr", "hiring",
                 "talent", "team", "admin", "sales", "enquiry", "enquiries", "inquiry", "office", "mail",
                 "recruitment", "recruiting", "people", "press", "media", "partnerships", "business",
                 "connect", "help", "marketing", "noreply", "no-reply", "privacy", "legal", "investors",
                 "founders", "contactus", "care", "accounts", "billing", "feedback", "grievance", "pr", "ir"}
CAREER_LOCAL = {"careers", "career", "jobs", "hr", "hiring", "talent", "recruitment", "recruiting", "people"}

def decode_cfemail(hexstr):
    try:
        key = int(hexstr[:2], 16)
        return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))
    except Exception:
        return None

def clean_email(e):
    e = e.strip().strip(".").lower()
    if e.endswith(BAD_EMAIL_END) or any(e.endswith("@" + d) or e.endswith("." + d) for d in BAD_EMAIL_DOMAINS):
        return None
    if len(e.split("@")[0]) > 40 or "@" not in e:
        return None
    return e

def extract_emails(html):
    """Plain, mailto, Cloudflare-protected and 'name [at] domain [dot] com' emails."""
    found = set(EMAIL_RE.findall(html))
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("[data-cfemail]"):
        d = decode_cfemail(tag.get("data-cfemail", ""))
        if d:
            found.add(d)
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if "/cdn-cgi/l/email-protection#" in h:
            d = decode_cfemail(h.split("#")[-1])
            if d:
                found.add(d)
    text = soup.get_text(" ")
    for m in OBFUSCATED_RE.finditer(text):
        dom = re.sub(r"\s*(?:[\[\(\{<]\s*dot\s*[\]\)\}>]|\.)\s*", ".", m.group(2), flags=re.I)
        found.add(f"{m.group(1)}@{dom}")
    return {c for c in (clean_email(e) for e in found) if c}

def is_generic(email):
    local = email.split("@")[0].lower()
    return local in GENERIC_LOCAL or any(local.startswith(g + ".") or local.startswith(g + "_") for g in CAREER_LOCAL)

HONORIFICS = {"dr", "mr", "mrs", "ms", "prof", "sir", "shri", "smt", "er"}
EMAIL_TEMPLATES = ["{first}", "{first}.{last}", "{f}{last}", "{first}{last}", "{first}_{last}", "{f}.{last}",
                   "{first}{l}", "{last}", "{last}.{first}", "{first}-{last}", "{last}{f}", "{first}.{l}"]
COMMON_PATTERNS = ["{first}", "{first}.{last}"]   # used only when there is no evidence (grade D)

def split_name(full):
    toks = [t for t in re.sub(r"[^A-Za-z\s]", " ", str(full)).split() if t.lower() not in HONORIFICS]
    if not toks:
        return None, None
    return toks[0].lower(), (toks[-1].lower() if len(toks) > 1 else "")

def apply_pattern(pat, first, last):
    if not pat or not first or (("{last}" in pat or "{l}" in pat) and not last):   # no pattern learned yet
        return None
    return (pat.replace("{first}", first).replace("{last}", last)
               .replace("{f}", first[:1]).replace("{l}", last[:1]))

def matching_patterns(local, first, last):
    return [p for p in EMAIL_TEMPLATES if apply_pattern(p, first, last) == local]

def choose_mail_domain(web_dom, emails):
    """The domain people's emails use. Usually the website domain; sometimes a sister domain (x.ai vs x.com)."""
    if not web_dom:
        return None
    doms = Counter(e.split("@")[1] for e in emails if "@" in e)
    if any(d == web_dom or d.endswith("." + web_dom) for d in doms):
        return web_dom
    root = web_dom.split(".")[0]
    alt = [d for d, _ in doms.most_common() if d.split(".")[0] == root and d not in FREE_MAIL]
    return alt[0] if alt else web_dom

def mx_lookup(domain):
    """Does this domain receive email, and who hosts it? (free DNS check)"""
    try:
        import dns.resolver
        ans = dns.resolver.resolve(domain, "MX", lifetime=8)
        hosts = [str(r.exchange).rstrip(".").lower() for r in sorted(ans, key=lambda r: r.preference)]
    except Exception as e:
        if type(e).__name__ in ("NXDOMAIN", "NoAnswer"):
            return {"has_mx": False, "provider": None, "hosts": []}
        return {"has_mx": None, "provider": None, "hosts": []}   # DNS error: unknown
    hosts = [h for h in hosts if h]
    prov = ("Google Workspace" if any("google" in h for h in hosts) else
            "Microsoft 365" if any("outlook" in h or "microsoft" in h for h in hosts) else
            "Zoho Mail" if any("zoho" in h for h in hosts) else (hosts[0] if hosts else None))
    return {"has_mx": bool(hosts), "provider": prov, "hosts": hosts[:3]}

# ---------- People ----------
NAME_STOP = {"linkedin", "jobs", "careers", "team", "company", "india", "private", "limited", "pvt", "ltd",
             "profile", "posts", "hiring", "official", "page", "the", "about", "inc", "llp", "technologies",
             "solutions", "labs", "ai", "and", "of", "for", "at", "group", "services", "systems", "bio"}

def looks_like_name(s):
    toks = str(s).strip().split()
    if not 2 <= len(toks) <= 4:
        return False
    if any(t.lower().strip(".,") in NAME_STOP for t in toks):
        return False
    return all(re.fullmatch(r"[A-Z][a-zA-Z'.-]*", t) for t in toks)

def tidy_name(s):
    s = re.sub(r"\s+", " ", str(s)).strip(" .,-–|")
    return s.title() if s.isupper() else s

def li_slug(u):
    m = re.search(r"linkedin\.com/in/([^/?#\s]+)", str(u or ""), re.I)
    return m.group(1).lower() if m else None

def li_url(slug):
    return f"https://www.linkedin.com/in/{slug}" if slug else None

KEY_ROLE_RE = re.compile(r"founder|ceo|cto|coo|cso|chief|director|head|vp|vice president|president|"
                         r"lead|principal|hr|talent|recruit|people|hiring|partner|managing", re.I)
JOB_WORD_RE = re.compile(r"\b(founder|co-founder|ceo|cto|coo|cso|chief|director|head|vp|president|lead|manager|"
                         r"engineer|scientist|researcher|analyst|developer|intern|recruiter|hr|talent|partner|"
                         r"consultant|architect|officer|associate|specialist|executive|professor|md)\b", re.I)
PAST_RE = re.compile(r"\b(former|ex-|ex |previously|past|until|left)\b", re.I)

def is_key_role(role):
    return bool(role) and bool(KEY_ROLE_RE.search(str(role))) and not PAST_RE.search(str(role))

CATEGORY_RULES = [
    ("Founder / CEO", r"founder|\bceo\b|chief executive|managing director|\bmd\b"),
    ("CTO / Engineering lead", r"\bcto\b|chief technology|vp,? (of )?engineering|head of (engineering|technology|tech)\b|"
                               r"engineering (head|director|manager)|chief architect|director of engineering"),
    ("AI / Research lead", r"head of (ai|ml|machine learning|data|research|science|r&d|bioinformatics)|"
                           r"chief (scientist|data|ai|science)|\bcso\b|principal (scientist|engineer)|"
                           r"research (director|head|lead)|(ai|ml|data science|research|bioinformatics) (lead|head|director|manager)|"
                           r"director.*(ai|research|data|science|r&d)|lead (data|ai|ml) scientist"),
    ("Hiring / HR", r"\bhr\b|human resources|talent|recruit|people (ops|operations|partner|team)|hiring|\bchro\b|head of people"),
    ("Other leader", r"\bcoo\b|chief|director|\bvp\b|vice president|\bhead\b|president|partner|general manager|\blead\b"),
]
CATEGORIES = [c for c, _ in CATEGORY_RULES] + ["Team member"]

def role_category(roles):
    best = len(CATEGORIES) - 1
    for r in roles:
        if PAST_RE.search(str(r)):
            continue
        for i, (_, pat) in enumerate(CATEGORY_RULES):
            if re.search(pat, str(r), re.I):
                best = min(best, i)
                break
    return CATEGORIES[best]

# How much each source proves "this person works there NOW"
SOURCE_WEIGHT = {"official site": 3, "structured data": 3, "LinkedIn headline": 3, "LinkedIn experience": 2,
                 "Hunter.io": 2, "Tomba": 2, "news": 1, "web": 1, "company registry": 1, "LinkedIn mention": 1}
FINDER_LABELS = {"hunter.io", "tomba.io"}
ROLE_SOURCE_PREF = ["official site", "structured data", "LinkedIn headline", "Hunter.io", "Tomba", "LinkedIn experience",
                    "news", "web", "LinkedIn mention", "company registry"]

GRADES = ["A · verified", "A · published", "B · strong", "C · likely", "D · guess"]
GRADE_RANK = {g: i for i, g in enumerate(GRADES)}
CONF_RANK = {"High": 0, "Medium": 1, "Low": 2}
ORDER_STARTUP = ["Founder / CEO", "CTO / Engineering lead", "AI / Research lead", "Hiring / HR", "Other leader", "Team member"]
ORDER_CORP = ["AI / Research lead", "Hiring / HR", "CTO / Engineering lead", "Other leader", "Founder / CEO", "Team member"]

def contact_sort_key(c, startup):
    order = ORDER_STARTUP if startup else ORDER_CORP
    return (order.index(c.get("category") or "Team member"),
            GRADE_RANK.get(c.get("email_grade"), 9), CONF_RANK.get(c.get("person_confidence"), 9))

def as_list(x):
    if isinstance(x, list):
        return x
    return [] if x in (None, "", {}) else [x]

def to_dict_emails(x, default_url):
    """Older runs saved site emails as a list; newer as {email: page}."""
    if isinstance(x, dict):
        return x
    return {e: default_url for e in as_list(x)}

print("Helpers ready.")

# ----------------------------------------------------------------------
# CELL 4 — Find startups and companies
# First run takes 15–25 min. Reruns skip searches already done.

FULL = ["{t} startup {c}", "{t} startup {c} funding", "{t} startup {c} hiring", "{t} company {c}"]
LIGHT = ["{t} startup {c}"]
NATIONAL_FULL = ["top {t} startups in India", "{t} startup India raises funding", "{t} deeptech startup India"]
NATIONAL_LIGHT = ["top {t} startups in India"]

queries = []
for dom, terms in SEARCH_TERMS.items():
    p1 = PRIORITY[dom] == 1
    for t in terms:
        for c in CITIES:
            for tpl in (FULL if p1 else LIGHT):
                queries.append((dom, tpl.format(t=t, c=c)))
        for tpl in (NATIONAL_FULL if p1 else NATIONAL_LIGHT):
            queries.append((dom, tpl.format(t=t)))
queries = list(dict.fromkeys(queries))

# --- Step A: web searches (saved as they run) ---
search_log = load_json("search_results.json", {})
_stale = (datetime.now() - timedelta(days=DISCOVERY_REFRESH_DAYS)).strftime("%Y-%m-%d")
todo = [q for q in queries if q[1] not in search_log or search_log[q[1]].get("date", "2000-01-01") < _stale]
print(f"{len(queries)} searches in total, {len(todo)} left, up to {DISCOVERY_PER_RUN} this run")
todo = todo[:DISCOVERY_PER_RUN]
for i, (dom, q) in enumerate(todo, 1):
    if stage_over("discovery"):
        break
    res = web_search_raw(q)
    if res is None:          # every engine failed (blocked): don't mark it done, retry next run
        continue
    search_log[q] = {"domain": dom, "results": res, "date": today()}
    if i % 10 == 0 or i == len(todo):
        save_json("search_results.json", search_log)
        print(f"  {i}/{len(todo)} searches done")

rows, seen = [], set()
for q, v in search_log.items():
    for r in v["results"]:
        key = v["domain"] + "|" + r["url"]
        if key in seen or in_set(domain_of(r["url"]), SKIP_FOR_DISCOVERY):
            continue
        seen.add(key)
        rows.append({"domain": v["domain"], **r})
print(len(rows), "unique search results")

# --- Step B: Gemini reads the results and lists the companies named in them ---
EXTRACT_PROMPT = """You read web search results about {dom} companies in India and list the companies they name.
Rules:
- Only companies clearly named in the results below. Never add companies from memory.
- Skip news sites, job boards, VC funds, accelerators, universities, directories, and the publishers of "top startups" lists.
- type: "startup" (young, venture-funded or small), "corporate" (large established firm or MNC) or "research_lab".
- Unknown fields: null.
Return a JSON list. Each item:
{{"name": str, "website": str|null, "city": str|null, "country": str|null, "type": str, "what_they_do": str, "source_url": str}}

Results:
{text}"""

found = load_json("companies_found.json", {"done": [], "companies": []})
done = set(found["done"])
pending = [r for r in rows if r["domain"] + "|" + r["url"] not in done]
print(len(pending), "results for Gemini to read")

stop = False
for dom in SEARCH_TERMS:
    grp = [r for r in pending if r["domain"] == dom]
    for i in range(0, len(grp), 30):
        if stage_over("extract"):
            stop = True
            break
        batch = grp[i:i + 30]
        text = "\n".join(f"- {r['title']} | {r['url']} | {r['snippet']}" for r in batch)
        out = ask_gemini(EXTRACT_PROMPT.format(dom=dom, text=text))
        if out is None:
            if gemini_exhausted():
                print("Gemini daily limit reached. Rerun this cell tomorrow; it continues from here.")
                stop = True
                break
            continue
        if isinstance(out, dict):
            out = next((v for v in out.values() if isinstance(v, list)), [])
        low = re.sub(r"\s+", " ", text.lower())
        kept = 0
        for c in out:
            if not isinstance(c, dict):
                continue
            nm = re.sub(r"\s+", " ", str(c.get("name") or "")).strip()
            if len(nm) < 2 or nm.lower() not in low:   # guard: the name must appear in the results
                continue
            c["name"], c["domain"] = nm, dom
            found["companies"].append(c)
            kept += 1
        done.update(r["domain"] + "|" + r["url"] for r in batch)
        found["done"] = sorted(done)
        save_json("companies_found.json", found)
        print(f"  {dom}: batch {i // 30 + 1}, {kept} companies")
    if stop:
        break

# --- Step C: Indian startups from the public Y Combinator directory (free, structured) ---
def domain_words(dom):
    words = list(INTEREST_WORDS.get(dom, []))
    for t in SEARCH_TERMS[dom]:
        core = [w for w in t.lower().split() if w not in {"ai", "tech", "startup", "company", "llm"}]
        if core:
            words.append(" ".join(core))
    return words

yc_items = []
if USE_YC_DIRECTORY:
    yc = load_json("yc_directory.json", None)
    if yc is None:
        yc = get_json("https://yc-oss.github.io/api/companies/all.json", timeout=90) or []
        if yc:
            save_json("yc_directory.json", yc)
    for c in yc if isinstance(yc, list) else []:
        locs = " ".join(str(x) for x in [c.get("all_locations"), c.get("regions")] if x)
        if "india" not in locs.lower() or str(c.get("status", "")).lower() not in ("active", "public", ""):
            continue
        txt = " ".join(str(x) for x in [c.get("one_liner"), c.get("long_description"), c.get("tags"),
                                         c.get("industries"), c.get("industry"), c.get("subindustry")] if x).lower()
        for dom in SEARCH_TERMS:
            if any(w in txt for w in domain_words(dom)):
                city = str(c.get("all_locations") or "").split(";")[0].split(",")[0].strip() or None
                yc_items.append({"name": c.get("name"), "website": c.get("website"), "city": city, "country": "India",
                                 "type": "startup", "what_they_do": c.get("one_liner"), "domain": dom,
                                 "source_url": c.get("url") or "https://www.ycombinator.com/companies"})
    print(len(yc_items), "matches from the YC directory")

# --- Step D: merge duplicates ---
def merge_companies(items):
    merged = {}
    for c in items:
        if not c.get("name"):
            continue
        k = norm_name(c.get("name"))
        if not k:
            continue
        m = merged.setdefault(k, {"name": str(c["name"]).strip(), "domains": set(), "sources": set()})
        if c.get("domain"):
            m["domains"].add(c["domain"])
        if c.get("source_url"):
            m["sources"].add(c["source_url"])
        site = c.get("website")
        if site and is_non_company(domain_of(site)):
            site = None
        if site and not m.get("website"):
            m["website"] = site if "://" in site else "https://" + site
        for f in ("city", "country", "type", "what_they_do"):
            if not m.get(f) and c.get(f):
                m[f] = c[f]
    by_site, out = {}, []   # same website = same company
    for m in merged.values():
        d = domain_of(m.get("website"))
        if d and d in by_site:
            o = by_site[d]
            o["domains"] |= m["domains"]
            o["sources"] |= m["sources"]
            continue
        if d:
            by_site[d] = m
        out.append(m)
    for m in out:
        ds = sorted(m["domains"], key=lambda d: (PRIORITY.get(d, 2), d))
        m["priority"] = min([PRIORITY.get(d, 2) for d in ds] or [2])
        m["domains"] = ", ".join(ds)
        m["sources"] = " | ".join(sorted(m["sources"])[:3])
        m["india"] = is_india(m.get("country"), m.get("city"), m.get("website"))
    return out

all_items = ([c for c in found["companies"] + yc_items if c.get("domain") in SEARCH_TERMS]   # only chosen sectors
             + [{**c, "source_url": "added by you"} for c in EXTRA_COMPANIES])
companies = pd.DataFrame(merge_companies(all_items))
assert len(companies), "No companies found. Check that searches returned results (see Step A)."

companies["_startup"] = (companies["type"].astype(str).str.lower() == "startup").astype(int)
companies = (companies.sort_values(["india", "_startup", "priority"], ascending=[False, False, True])
                      .drop(columns="_startup").reset_index(drop=True))
cols = ["name", "domains", "priority", "type", "india", "city", "country", "website", "what_they_do", "sources"]
companies = companies.reindex(columns=cols)
companies.to_csv(fpath("companies.csv"), index=False)

print(f"\n{len(companies)} companies found  ·  India: {int(companies['india'].sum())}  ·  "
      f"startups: {int((companies['type'] == 'startup').sum())}")
print(companies["domains"].str.split(", ").explode().value_counts().to_string())
display(companies.head(20))

# ----------------------------------------------------------------------
# CELL 5 — Profile each company: website, people, products, research, funding, open roles
# ENRICH_PER_RUN companies per run (India startups and priority-1 fields first). Rerun for the next batch.

PAGE_HINTS = ["about", "team", "leadership", "people", "founder", "company", "who-we-are", "story",
              "careers", "career", "jobs", "join", "contact", "research", "science", "publications",
              "technology", "platform", "product", "solutions", "news", "press"]
GUESS_PATHS = ["/about", "/about-us", "/team", "/our-team", "/leadership", "/company", "/contact", "/contact-us", "/careers"]
CAREER_HINTS = ["careers", "career", "jobs", "join", "hiring", "work-with-us"]
ATS_PATTERNS = {
    "greenhouse": r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)",
    "lever": r"jobs\.lever\.co/([A-Za-z0-9_.-]+)",
    "ashby": r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)",
    "workable": r"apply\.workable\.com/([A-Za-z0-9_-]+)",
    "smartrecruiters": r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)",
}
JOB_SITES = ["keka.com", "darwinbox", "zohorecruit", "freshteam", "wellfound.com", "instahyre.com",
             "cutshort.io", "workable.com", "smartrecruiters.com", "teamtailor.com", "breezy.hr",
             "recruitee.com", "naukri.com", "linkedin.com/jobs"]
ATS_SKIP_SLUGS = {"embed", "v1", "jobs", "job_board", "boards", "api"}
GH_SKIP = {"features", "about", "pricing", "login", "orgs", "sponsors", "topics", "marketplace", "enterprise",
           "site", "contact", "collections", "explore", "apps", "settings", "join", "security", "customer-stories"}


def find_website(name, field):
    res = web_search(f'"{name}" {field} company official website', n=8)
    toks = [t for t in norm_name(name).split() if len(t) >= 3]
    compact = norm_name(name).replace(" ", "")
    for r in res:
        d = domain_of(r["url"])
        if not d or is_non_company(d):
            continue
        root = re.sub(r"[^a-z0-9]", "", d.rsplit(".", 1)[0])
        if (toks and toks[0] in root) or (compact and compact[:8] in root):
            return "https://" + d
    return None   # better none than a wrong site


def empty_info(website):
    return {"website": website, "pages": {}, "emails": {}, "phones": set(), "linkedin_company": None,
            "github_org": None, "twitter": None, "ats": set(), "job_links": set(), "careers_url": None,
            "contact_url": None, "jsonld_people": [], "jsonld_org": {}}


def read_jsonld(html, url, info):
    """schema.org data many sites embed: founders, employees, email, phone, social links."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            o = stack.pop()
            if isinstance(o, list):
                stack.extend(o)
                continue
            if not isinstance(o, dict):
                continue
            stack.extend(v for v in o.values() if isinstance(v, (dict, list)))
            t = str(o.get("@type", ""))
            if "Person" in t and o.get("name"):
                info["jsonld_people"].append({"name": str(o["name"]), "role": o.get("jobTitle"),
                                              "email": str(o.get("email") or "").replace("mailto:", "") or None,
                                              "sameAs": as_list(o.get("sameAs")), "url": url})
            if "Organization" in t or "Corporation" in t:
                org = info["jsonld_org"]
                for k in ("name", "foundingDate", "email", "telephone"):
                    if o.get(k) and not org.get(k):
                        org[k] = str(o[k])
                for f in as_list(o.get("founder")) + as_list(o.get("founders")):
                    nm = f.get("name") if isinstance(f, dict) else f
                    if nm:
                        info["jsonld_people"].append({"name": str(nm), "role": "Founder", "email": None,
                                                      "sameAs": [], "url": url})
                for s in as_list(o.get("sameAs")):
                    s = str(s)
                    if "linkedin.com/company/" in s and not info["linkedin_company"]:
                        info["linkedin_company"] = s


def scan_links(html, url, info, base_dom):
    soup = BeautifulSoup(html, "html.parser")
    cands = []
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"].strip())
        low = href.lower()
        if low.startswith("tel:"):
            info["phones"].add(re.sub(r"\s+", " ", href[4:]).strip())
            continue
        if low.startswith(("mailto:", "javascript:")):
            continue
        if "linkedin.com/company/" in low and not info["linkedin_company"]:
            info["linkedin_company"] = href.split("?")[0]
        m = re.search(r"github\.com/(?:orgs/)?([A-Za-z0-9-]+)", href)
        if m and m.group(1).lower() not in GH_SKIP and not info["github_org"]:
            info["github_org"] = m.group(1)
        if re.search(r"(twitter|x)\.com/[A-Za-z0-9_]+", low) and not info["twitter"]:
            info["twitter"] = href.split("?")[0]
        for kind, pat in ATS_PATTERNS.items():
            mm = re.search(pat, href)
            if mm and mm.group(1).lower() not in ATS_SKIP_SLUGS:
                info["ats"].add(f"{kind}:{mm.group(1)}")
        if any(s in low for s in JOB_SITES):
            info["job_links"].add(href.split("?")[0])
        d = domain_of(href)
        if d and (d == base_dom or d.endswith("." + base_dom)):
            path = urlparse(href).path.lower()
            text = (a.get_text(" ") or "").lower()
            hit = next((i for i, h in enumerate(PAGE_HINTS) if h in path or h in text), None)
            if hit is not None:
                cands.append((hit, href.split("#")[0]))
            if not info["careers_url"] and any(h in path or h in text for h in CAREER_HINTS):
                info["careers_url"] = href.split("#")[0]
            if not info["contact_url"] and "contact" in (path + " " + text):
                info["contact_url"] = href.split("#")[0]
    for kind, pat in ATS_PATTERNS.items():   # embedded job widgets
        for mm in re.finditer(pat, html):
            if mm.group(1).lower() not in ATS_SKIP_SLUGS:
                info["ats"].add(f"{kind}:{mm.group(1)}")
    return cands


def crawl(website, max_pages=8):
    info = empty_info(website)
    html, final = fetch(website)
    get = fetch
    if not html or len(page_text(html, 1000)) < 300:   # empty or JavaScript-only page
        h2, f2 = fetch_rendered(website)
        if h2:
            html, final, get = h2, (final if html else f2), fetch_rendered
            info["rendered_with_jina"] = True
            max_pages = min(max_pages, 5)
    if not html:
        return info
    info["website"] = final
    base_dom = domain_of(final)
    root = f"{urlparse(final).scheme}://{urlparse(final).netloc}"

    def absorb(h, u):
        info["pages"][u] = page_text(h, 2500 if info["pages"] else 3000)
        for e in extract_emails(h):
            info["emails"].setdefault(e, u)
        read_jsonld(h, u, info)
        return scan_links(h, u, info, base_dom)

    cands = absorb(html, final)
    linked = {c[1].rstrip("/") for c in cands}
    cands += [(len(PAGE_HINTS) + i, root + p) for i, p in enumerate(GUESS_PATHS) if (root + p) not in linked]
    visited = {final.rstrip("/")}
    for _, link in sorted(set(cands)):
        if len(info["pages"]) >= max_pages:
            break
        if link.rstrip("/") in visited or re.search(r"\.(pdf|jpg|png|zip|docx?)$", link, re.I):
            continue
        visited.add(link.rstrip("/"))
        h, f = get(link)
        if h and f.rstrip("/") not in {u.rstrip("/") for u in info["pages"]}:
            absorb(h, f)
        time.sleep(0.5)
    return info


PROFILE_PROMPT = """Build a structured profile of the company "{name}" (website: {website}) for a job seeker.
Use ONLY the text below. Do not use outside knowledge. If something is not in the text, use null or [].
Each block of text starts with "### SOURCE: <url>". Use that url as the source of facts taken from it.

Return JSON with exactly these keys:
{{
 "official_name": str|null,
 "founded_year": int|null,
 "hq_city": str|null,
 "country": str|null,
 "is_startup": bool|null,
 "stage": str|null,            // e.g. Bootstrapped, Pre-seed, Seed, Series A, Series B, Public, Subsidiary
 "employee_count": str|null,
 "one_liner": str|null,
 "what_they_do": str|null,     // 2-3 plain sentences
 "products": [{{"name": str, "description": str, "source": str}}],
 "research_and_discoveries": [{{"item": str, "source": str}}],   // papers, patents, breakthroughs, awards
 "tech_and_methods": [str],
 "funding": {{"total": str|null, "last_round": str|null, "last_round_amount": str|null,
             "last_round_date": str|null, "investors": [str], "source": str|null}},
 "funding_rounds": [{{"round": str, "amount": str|null, "date": str|null, "investors": [str], "source": str}}],
 "people": [{{"name": str, "role": str, "is_key_contact": bool, "linkedin": str|null, "email": str|null, "source": str}}],
 "open_roles": [{{"title": str, "location": str|null, "url": str|null}}],
 "contact": {{"general_email": str|null, "phone": str|null, "address": str|null}}
}}
People rules:
- Only real people the text says CURRENTLY work at THIS company. Skip former employees and people at other companies.
- is_key_contact = true for founders, CEO, CTO, directors, heads of AI/ML/research/engineering/data, and HR/talent/hiring leads.
- If a person comes from a linkedin.com/in/ source, set linkedin to that url.
- Never guess emails or links. Copy them only if they appear in the text.
open_roles: only job titles actually listed in the text.

TEXT:
{corpus}"""


def build_corpus(name, info):
    blocks = [f"### SOURCE: {u}\n{t}" for u, t in info["pages"].items()]
    if info["jsonld_people"] or info["jsonld_org"]:
        blocks.append(f"### SOURCE: {info['website']} (structured data)\n"
                      + json.dumps({"organization": info["jsonld_org"], "people": info["jsonld_people"]})[:1500])
    if info["emails"]:
        blocks.append(f"### SOURCE: {info['website']} (emails on site)\n" + ", ".join(sorted(info["emails"])))
    site = "\n\n".join(blocks)[:13000]
    snips, used = [], set()
    for q in [f'"{name}" funding raised investors', f'"{name}" founder CEO CTO', f'"{name}" research OR patent OR launch']:
        for r in cached_search(q, n=8):
            if r["url"] in used:
                continue
            used.add(r["url"])
            snips.append(f"### SOURCE: {r['url']}\n{r['title']} — {r['snippet']}")
    return site + "\n\n" + "\n\n".join(snips)[:7000], sorted(used)


def validate(prof, corpus):
    """Drop anything Gemini could not have read in the text (anti-hallucination check)."""
    low = corpus.lower()
    people, seen_p = [], set()
    for p in as_list(prof.get("people")):
        if not isinstance(p, dict):
            continue
        nm = str(p.get("name") or "").strip()
        toks = [t for t in norm_name(nm).split() if len(t) > 1]
        if not toks or not all(t in low for t in toks) or norm_name(nm) in seen_p:
            continue
        if PAST_RE.search(str(p.get("role") or "")):
            continue
        seen_p.add(norm_name(nm))
        s = li_slug(p.get("linkedin"))
        p["linkedin"] = li_url(s) if s and s in low else None
        if p.get("email") and str(p["email"]).lower() not in low:
            p["email"] = None
        p["is_key_contact"] = bool(p.get("is_key_contact")) or is_key_role(p.get("role"))
        people.append(p)
    prof["people"] = people
    c = prof.get("contact") if isinstance(prof.get("contact"), dict) else {}
    if c.get("general_email") and str(c["general_email"]).lower() not in low:
        c["general_email"] = None
    prof["contact"] = c
    prof["open_roles"] = [r for r in as_list(prof.get("open_roles"))
                          if isinstance(r, dict) and r.get("title") and str(r["title"]).lower()[:25] in low]
    return prof


companies = pd.read_csv(fpath("companies.csv"))
companies = companies.astype(object).where(pd.notna(companies), None)
profiles = load_json("profiles.json", {})

todo = [r for r in companies.to_dict("records")
        if r["name"] not in profiles or (RETRY_FAILED and profiles[r["name"]].get("status") != "ok")]
todo = todo[:ENRICH_PER_RUN]
print(f"Profiled so far: {sum(1 for p in profiles.values() if p.get('status') == 'ok')} · this run: {len(todo)} "
      f"· left after this: {max(len(companies) - len(profiles) - len(todo), 0)}")

for n, r in enumerate(todo, 1):
    if stage_over("profile"):
        break
    name = r["name"]
    field = (r.get("domains") or "").split(",")[0]
    print(f"[{n}/{len(todo)}] {name}")
    website = r.get("website") or find_website(name, field)
    info = crawl(website) if website else empty_info(None)
    corpus, search_urls = build_corpus(name, info)
    prof = ask_gemini(PROFILE_PROMPT.format(name=name, website=info["website"] or "unknown", corpus=corpus))
    if prof is None and gemini_exhausted():
        print("Gemini daily limit reached. Rerun this cell tomorrow; it continues from here.")
        break
    if isinstance(prof, list):
        prof = next((x for x in prof if isinstance(x, dict)), None)
    status = "ok" if isinstance(prof, dict) else "failed"
    prof = validate(prof, corpus) if status == "ok" else {}
    profiles[name] = {
        "status": status,
        "input": r,
        "website": info["website"],
        "crawl": {k: (sorted(v) if isinstance(v, set) else v) for k, v in info.items() if k != "pages"},
        "pages_read": list(info["pages"].keys()),
        "search_sources": search_urls,
        "profile": prof,
        "updated": datetime.now().isoformat(timespec="minutes"),
    }
    save_json("profiles.json", profiles)
    if status == "ok":
        key = [p["name"] for p in prof["people"] if p.get("is_key_contact")]
        print(f"   founded {prof.get('founded_year')} · {len(prof['people'])} people ({len(key)} key) · "
              f"{len(as_list(prof.get('funding_rounds')))} rounds · {len(info['emails'])} emails on site")

flush_search_cache()
print("\nDone. Profiles saved:", len(profiles))

# ----------------------------------------------------------------------
# CELL 6 — Open roles
# Live jobs from Greenhouse / Lever / Ashby / Workable / SmartRecruiters boards found on company sites,
# plus roles Gemini read on careers pages.

ROLE_RE = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in PREFERRED_ROLES) + r")\b", re.I)

def fetch_ats(kind, slug):
    jobs = []
    if kind == "greenhouse":
        d = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"}) or {}
        for j in d.get("jobs", []):
            jobs.append({"title": j.get("title"), "location": (j.get("location") or {}).get("name"),
                         "url": j.get("absolute_url"), "posted": j.get("updated_at"),
                         "desc": page_text(html.unescape(j.get("content") or ""), 1500) if j.get("content") else ""})
    elif kind == "lever":
        d = get_json(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"}) or []
        for j in d if isinstance(d, list) else []:
            cat = j.get("categories") or {}
            jobs.append({"title": j.get("text"), "location": cat.get("location"),
                         "url": j.get("hostedUrl"), "posted": j.get("createdAt"),
                         "desc": str(j.get("descriptionPlain") or "")[:1500]})
    elif kind == "ashby":
        d = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}") or {}
        for j in d.get("jobs", []):
            jobs.append({"title": j.get("title"), "location": j.get("location"),
                         "url": j.get("jobUrl"), "posted": j.get("publishedAt"),
                         "desc": str(j.get("descriptionPlain") or "")[:1500]})
    elif kind == "workable":
        d = get_json(f"https://apply.workable.com/api/v1/widget/accounts/{slug}") or {}
        for j in d.get("jobs", []):
            loc = ", ".join(str(x) for x in [j.get("city"), j.get("country")] if x)
            jobs.append({"title": j.get("title"), "location": loc or None,
                         "url": j.get("url") or j.get("shortlink"), "posted": j.get("published_on")})
    elif kind == "smartrecruiters":
        d = get_json(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings") or {}
        for j in d.get("content", []):
            loc = j.get("location") or {}
            jobs.append({"title": j.get("name"), "location": ", ".join(str(x) for x in [loc.get("city"), loc.get("country")] if x) or None,
                         "url": f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}", "posted": j.get("releasedDate")})
    return jobs

job_rows = []
for name, p in profiles.items():
    if p.get("status") != "ok":
        continue
    for a in p["crawl"].get("ats", []):
        kind, slug = a.split(":", 1)
        for j in fetch_ats(kind, slug):
            job_rows.append({"company": name, **j, "source": f"{kind} job board"})
        time.sleep(0.5)
    for j in as_list(p["profile"].get("open_roles")):
        job_rows.append({"company": name, "title": j.get("title"), "location": j.get("location"),
                         "url": j.get("url") or p["crawl"].get("careers_url"), "posted": None,
                         "source": "careers page"})

jobs = pd.DataFrame(job_rows, columns=["company", "title", "location", "url", "posted", "source", "desc"])
if len(jobs):
    jobs = jobs.dropna(subset=["title"]).drop_duplicates(["company", "title", "location"])
    jobs["relevant"] = jobs["title"].astype(str).str.contains(ROLE_RE)
    jobs["in_india"] = jobs["location"].apply(lambda l: is_india(city=l) or "remote" in str(l).lower())
    jobs = jobs.sort_values(["relevant", "in_india"], ascending=False)
else:
    jobs["relevant"], jobs["in_india"] = pd.Series(dtype=bool), pd.Series(dtype=bool)
jobs.to_csv(fpath("jobs.csv"), index=False)
print(f"{len(jobs)} open roles · relevant to you: {int(jobs['relevant'].sum()) if len(jobs) else 0}")
display(jobs[jobs["relevant"]].head(20) if len(jobs) else jobs)

# ----------------------------------------------------------------------
# CELL 7 — Find people (6 sources), merge them, and score how sure we are they work there now
# Sources: company site · structured data on the site · LinkedIn (via search) · company registry (India)
#          · news / interviews · Hunter.io
# PEOPLE_PER_RUN companies per run, best-ranked first. Rerun for the next batch.

def parse_linkedin(r, company):
    """'Priya Sharma - Co-founder & CEO - GenoMind AI | LinkedIn' -> person, if they work at this company."""
    slug = li_slug(r["url"])
    if not slug:
        return None
    title = re.sub(r"\s*(?:\||·|-|–)\s*LinkedIn.*$", "", r.get("title") or "", flags=re.I).strip()
    parts = [p.strip() for p in re.split(r"\s+[-–—|]\s+", title) if p.strip()]
    if not parts:
        return None
    name = tidy_name(parts[0])
    if not looks_like_name(name) or mentions(name, company):
        return None
    rest, snip = parts[1:], r.get("snippet") or ""
    in_head = mentions(" ".join(rest), company)
    exp = re.search(r"Experience:\s*([^·|]+)", snip)
    in_exp = bool(exp and mentions(exp.group(1), company))
    in_snip = mentions(snip, company)
    if not (in_head or in_exp or in_snip):
        return None
    if not (in_head or in_exp) and PAST_RE.search(snip):
        return None
    role = None
    for p in rest:
        m = re.match(r"(.+?)\s+(?:at|@)\s+(.+)$", p)
        if m and mentions(m.group(2), company):
            role = m.group(1)
            break
        if not role and not mentions(p, company) and JOB_WORD_RE.search(p):
            role = p
    if not role:
        m = re.search(r"([A-Z][\w&/,.' -]{1,60}?)\s+(?:at|@)\s+(?i:" + re.escape(clean_company(company)) + ")", snip)
        if m and JOB_WORD_RE.search(m.group(1)):
            role = m.group(1).strip(" ,.")
    if role and PAST_RE.search(role):
        return None
    kind = "LinkedIn headline" if in_head else "LinkedIn experience" if in_exp else "LinkedIn mention"
    return {"name": name, "role": role, "type": kind, "url": li_url(slug), "linkedin": li_url(slug)}


def parse_registry(r, company):
    """Directors from company-registry pages (Zaubacorp, Tofler, ...). Indian private limiteds list founders as directors."""
    if not in_set(domain_of(r["url"]), REGISTRY_SITES):
        return []
    txt = f"{r.get('title', '')}. {r.get('snippet', '')}"
    if not mentions(txt, company):
        return []
    out = []
    for m in re.finditer(r"(?i:directors?|board members?)\s+(?:of\s+[^.]{0,90}?\s+)?(?i:are|is|include|:)\s+([^.;]+)", txt):
        for nm in re.split(r",\s*|\s+and\s+|\s*&\s*", m.group(1), flags=re.I):
            nm = tidy_name(nm)
            if looks_like_name(nm):
                out.append({"name": nm, "role": "Director (company registry)", "type": "company registry",
                            "url": r["url"]})
    return out


ROLE_WORDS = r"(?:co-?founder|founder|ceo|cto|coo|cso|chief [a-z]+ officer|managing director|director|head of [a-z&]+(?: [a-z&]+)?)"
NAME_PAT = r"([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2})"

def parse_news(r, company):
    """'Priya Sharma, co-founder and CEO of GenoMind AI' or 'GenoMind AI CEO Priya Sharma'."""
    txt = f"{r.get('title', '')}. {r.get('snippet', '')}"
    c = r"(?i:" + re.escape(clean_company(company)) + r")"
    role = r"(?i:(" + ROLE_WORDS + r"(?:\s*(?:and|&)\s*" + ROLE_WORDS + r")?))"
    out = []
    for m in re.finditer(NAME_PAT + r",?\s+(?:the\s+)?" + role + r"\s+(?i:of|at)\s+" + c, txt):
        out.append((m.group(1), m.group(2)))
    for m in re.finditer(c + r"(?:'s|’s)?\s+" + role + r",?\s+" + NAME_PAT, txt):
        out.append((m.group(2), m.group(1)))
    res = []
    for nm, rl in out:
        nm = tidy_name(nm)
        if looks_like_name(nm) and not mentions(nm, company):
            res.append({"name": nm, "role": rl.strip(), "type": "news", "url": r["url"]})
    return res


def same_person(a, b):
    sa, sb = li_slug(a.get("linkedin")), li_slug(b.get("linkedin"))
    if sa and sb:
        return sa == sb
    fa, la = split_name(a["name"])
    fb, lb = split_name(b["name"])
    if not fa or fa != fb:
        return False
    return la == lb or not la or not lb or la[0] == lb[0] and (len(la) == 1 or len(lb) == 1)


def merge_people(found):
    people = []
    for f in found:
        m = next((p for p in people if same_person(p, f)), None)
        if m is None:
            m = {"name": f["name"], "roles": [], "linkedin": None, "emails": [], "sources": []}
            people.append(m)
        if len(f["name"]) > len(m["name"]) and split_name(f["name"])[1]:
            m["name"] = f["name"]
        if f.get("role"):
            m["roles"].append([f["type"], str(f["role"]).strip()])
        if f.get("linkedin") and not m["linkedin"]:
            m["linkedin"] = f["linkedin"]
        if f.get("email"):
            m["emails"].append({"email": f["email"].lower(), "source": f["type"], "url": f.get("url"),
                                "conf": f.get("conf")})
        if {"type": f["type"], "url": f.get("url")} not in m["sources"]:
            m["sources"].append({"type": f["type"], "url": f.get("url")})
    for m in people:
        roles = sorted(m["roles"], key=lambda x: ROLE_SOURCE_PREF.index(x[0]) if x[0] in ROLE_SOURCE_PREF else 99)
        m["role"] = roles[0][1] if roles else None
        m["category"] = role_category([r for _, r in roles])
        types = {s["type"] for s in m["sources"]}
        score = sum(SOURCE_WEIGHT.get(t, 1) for t in types)
        m["evidence_score"] = score
        m["person_confidence"] = "High" if score >= 3 else "Medium" if score == 2 else "Low"
        m["source_types"] = sorted(types, key=lambda t: -SOURCE_WEIGHT.get(t, 1))
        m["key_contact"] = m["category"] != "Team member"
    return people


def source_type(url, dom):
    d = domain_of(url) or ""
    if dom and (d == dom or d.endswith("." + dom)):
        return "official site"
    if "linkedin.com" in d:
        return "LinkedIn mention"
    if in_set(d, REGISTRY_SITES):
        return "company registry"
    return "news" if is_non_company(d) else "web"


hunter_cache = load_json("hunter_cache.json", {})
tomba_cache = load_json("tomba_cache.json", {})

def hunter_account():
    """Hunter credits left. New plans share one pool: 1 credit per email found, 0.5 per verification."""
    d = get_json("https://api.hunter.io/v2/account", params={"api_key": HUNTER_KEY}) if HUNTER_KEY else None
    req = ((d or {}).get("data") or {}).get("requests") or {}
    def left(k):
        try:
            return float(req[k]["available"]) - float(req[k]["used"])
        except Exception:
            return None
    if left("credits") is not None:
        c = left("credits")
        return {"search": c, "verify": c * 2}
    return {"search": left("searches"), "verify": left("verifications")}

def finder_result(data, emails, key_conf, pattern):
    return {"pattern": pattern if pattern in EMAIL_TEMPLATES else None, "accept_all": data.get("accept_all"),
            "emails": [{"email": e.get("value") or e.get("email"), "first": e.get("first_name"),
                        "last": e.get("last_name"), "position": e.get("position"),
                        "confidence": e.get(key_conf), "linkedin": e.get("linkedin")}
                       for e in emails if isinstance(e, dict) and (e.get("value") or e.get("email"))]}

def hunter_domain(dom):
    if dom in hunter_cache:
        return hunter_cache[dom]
    d = get_json("https://api.hunter.io/v2/domain-search",
                 params={"domain": dom, "api_key": HUNTER_KEY, "limit": HUNTER_EMAILS_PER_DOMAIN, "type": "personal"}) or {}
    data = d.get("data")
    if data is None:
        return None   # failed call: don't cache, try again next run
    hunter_cache[dom] = finder_result(data, data.get("emails", []), "confidence", data.get("pattern"))
    save_json("hunter_cache.json", hunter_cache)
    return hunter_cache[dom]

def tomba_domain(dom):
    if dom in tomba_cache:
        return tomba_cache[dom]
    d = get_json("https://api.tomba.io/v1/domain-search", params={"domain": dom},
                 headers={"X-Tomba-Key": TOMBA_KEY, "X-Tomba-Secret": TOMBA_SECRET}) or {}
    data = d.get("data")
    if not isinstance(data, dict):
        return None
    org = data.get("organization") or {}
    tomba_cache[dom] = finder_result({"accept_all": org.get("accept_all")}, data.get("emails") or [], "score",
                                     org.get("pattern") or data.get("pattern"))
    save_json("tomba_cache.json", tomba_cache)
    return tomba_cache[dom]

def finder_entries(res, label, site):
    found, evidence = [], []
    for h in (res or {}).get("emails", []):
        full = f"{h.get('first') or ''} {h.get('last') or ''}".strip()
        if full and h.get("first"):
            found.append({"name": tidy_name(full), "role": h.get("position"), "type": label, "url": site,
                          "linkedin": h.get("linkedin"), "email": h["email"], "conf": h.get("confidence")})
        else:
            evidence.append({"email": h["email"], "source": label, "url": site, "conf": h.get("confidence")})
    return found, evidence

def run_finders(dom):
    """Tomba first (up to 10 emails per credit), Hunter only if Tomba found nothing (1 credit per email)."""
    global tomba_left, hunter_left
    t, h = tomba_cache.get(dom), hunter_cache.get(dom)
    if t is None and tomba_left > 0:
        t = tomba_domain(dom)
        tomba_left -= 1
    if h is None and hunter_left >= HUNTER_EMAILS_PER_DOMAIN and not (t and t["emails"]):
        h = hunter_domain(dom)
        hunter_left -= HUNTER_EMAILS_PER_DOMAIN
    tomba_ok = t is not None or not (TOMBA_KEY and TOMBA_SECRET)
    hunter_ok = h is not None or bool(t and t["emails"]) or not HUNTER_KEY
    done = tomba_ok and hunter_ok   # False = credits ran out; topped up next month
    return t, h, done

def apply_finders(entry, t, h):
    f1, e1 = finder_entries(t, "Tomba", "tomba.io")
    f2, e2 = finder_entries(h, "Hunter.io", "hunter.io")
    entry["found"] = [x for x in entry.get("found", []) if x["type"] not in ("Tomba", "Hunter.io")] + f1 + f2
    entry["evidence"] = [x for x in entry.get("evidence", []) if x["source"] not in ("Tomba", "Hunter.io")] + e1 + e2
    entry["finder_patterns"] = {k: v["pattern"] for k, v in (("tomba.io", t), ("hunter.io", h)) if v and v.get("pattern")}
    entry["accept_all"] = bool((t or {}).get("accept_all") or (h or {}).get("accept_all"))
    entry["people"] = merge_people(entry["found"])


people_db = load_json("people.json", {})
order = work_order(profiles)
todo = [n for n in order if n not in people_db][:PEOPLE_PER_RUN]
print(f"People searched so far: {len(people_db)} companies · this run: {len(todo)} · "
      f"left after this: {max(len([n for n in order if n not in people_db]) - len(todo), 0)}")

tomba_left = TOMBA_SEARCH_MAX if (TOMBA_KEY and TOMBA_SECRET) else 0
hunter_left = 0
if HUNTER_KEY:
    acc = hunter_account()
    hunter_left = min(HUNTER_SEARCH_MAX, acc["search"] if acc["search"] is not None else HUNTER_SEARCH_MAX)
print(f"Free finder budget this run: Tomba {tomba_left} searches · Hunter {hunter_left:g} credits")

# --- top-up: companies searched in earlier runs that never got a finder lookup (credits had run out) ---
for n in order:
    if tomba_left <= 0 and hunter_left < HUNTER_EMAILS_PER_DOMAIN:
        break
    e = people_db.get(n)
    dom = domain_of(profiles[n].get("website"))
    if e is None or e.get("finder_done") or not dom or "found" not in e:
        continue
    t, h, done = run_finders(dom)
    apply_finders(e, t, h)
    e["finder_done"] = done
    save_json("people.json", people_db)
    print(f"  top-up {n}: {len(e['people'])} people")

for k, n in enumerate(todo, 1):
    if stage_over("people"):
        break
    p = profiles[n]
    pr = p["profile"]
    comp = clean_company(pr.get("official_name") or n)
    dom = domain_of(p.get("website"))
    tier = company_tier(p)
    india = tier in (1, 3)
    found, evidence = [], []

    # 1. company site (read by Gemini in Cell 5)
    for x in as_list(pr.get("people")):
        t = source_type(x.get("source"), dom)
        found.append({"name": tidy_name(x["name"]), "role": x.get("role"), "type": t, "url": x.get("source"),
                      "linkedin": x.get("linkedin"),
                      "email": x.get("email") if t in ("official site", "structured data") else None})
    # 2. structured data on the site
    for x in p["crawl"].get("jsonld_people", []):
        if looks_like_name(tidy_name(x["name"])):
            li = next((s for s in x.get("sameAs", []) if li_slug(s)), None)
            found.append({"name": tidy_name(x["name"]), "role": x.get("role"), "type": "structured data",
                          "url": x.get("url"), "linkedin": li_url(li_slug(li)), "email": x.get("email")})
    # 3. LinkedIn profiles through search (Google first if you have a Serper key); stop once we have enough
    for w in (LINKEDIN_ROLE_WORDS if tier in (1, 2) else LINKEDIN_ROLE_WORDS_CORP):
        if sum(1 for x in merge_people(found) if x["key_contact"] and x["linkedin"]) >= PEOPLE_ENOUGH:
            break
        w = f'"{w}"' if " " in w else w
        for r in cached_search(f'site:linkedin.com/in "{comp}" {w}', n=10, prefer_google=True):
            x = parse_linkedin(r, comp)
            if x:
                found.append(x)
    # 4. company registry directors (Indian companies)
    if india:
        for r in cached_search(f'"{comp}" private limited directors', n=8):
            found += parse_registry(r, comp)
    # 5. news and interviews
    for r in cached_search(f'"{comp}" co-founder CEO said', n=10):
        found += parse_news(r, comp)
    # 6. emails shown anywhere on the web for this domain
    if dom:
        for r in cached_search(f'"@{dom}"', n=10):
            for e in EMAIL_RE.findall(f"{r.get('title', '')} {r.get('snippet', '')}"):
                e = clean_email(e)
                if e and at_domain(e, dom):
                    evidence.append({"email": e, "source": "web search", "url": r["url"]})

    entry = {"searched": today(), "found": found, "evidence": evidence, "finder_done": not dom}
    # 7. email finders (best-ranked companies get the free credits first)
    if dom:
        t, h, done = run_finders(dom)
        apply_finders(entry, t, h)
        entry["finder_done"] = done
    else:
        entry["people"] = merge_people(found)
    people_db[n] = entry
    save_json("people.json", people_db)
    key = [x for x in entry["people"] if x["key_contact"]]
    print(f"[{k}/{len(todo)}] {n}: {len(entry['people'])} people · {len(key)} key · "
          f"high-confidence: {sum(x['person_confidence'] == 'High' for x in key)}")

flush_search_cache()
tot = [x for v in people_db.values() for x in v["people"]]
print(f"\nTotal: {len(tot)} people at {len(people_db)} companies · key contacts: {sum(x['key_contact'] for x in tot)}")
print(pd.Series([x["category"] for x in tot], dtype=object).value_counts().to_string() if tot else "")

# ----------------------------------------------------------------------
# CELL 8 — Work emails: collect evidence, learn each company's email pattern, check the mail server,
# build missing emails, and verify the best ones with Hunter. Every email gets a grade A–D.

gh_cache = load_json("github_cache.json", {})
mx_cache = load_json("mx_cache.json", {})
verify_cache = load_json("verify_cache.json", {})
_gh_blocked = False

def gh_get(url, params=None):
    global _gh_blocked
    if _gh_blocked:
        return None
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    try:
        r = SESSION.get(url, params=params, headers=h, timeout=20)
    except Exception:
        return None
    if r.status_code in (403, 429) or r.headers.get("X-RateLimit-Remaining") == "0":
        _gh_blocked = True
        print("  GitHub hourly limit reached; rest of GitHub checks skipped this run (add GITHUB_TOKEN for more).")
        return None
    return r.json() if r.status_code == 200 else None

def github_emails(org):
    """Author emails from the company's public GitHub commits — strong evidence of the email pattern."""
    repos = gh_get(f"https://api.github.com/orgs/{org}/repos", {"sort": "pushed", "per_page": 20})
    if repos is None:
        repos = gh_get(f"https://api.github.com/users/{org}/repos", {"sort": "pushed", "per_page": 20})
    if not isinstance(repos, list):
        return None if _gh_blocked else []
    out = {}
    for rp in [r for r in repos if not r.get("fork")][:GITHUB_REPOS_PER_COMPANY]:
        commits = gh_get(f"https://api.github.com/repos/{org}/{rp['name']}/commits", {"per_page": 100})
        if commits is None and _gh_blocked:
            return None
        for c in commits if isinstance(commits, list) else []:
            a = (c.get("commit") or {}).get("author") or {}
            e = clean_email(str(a.get("email") or ""))
            if e and "noreply" not in e and e.split("@")[1] not in FREE_MAIL and e not in out:
                out[e] = {"email": e, "name": a.get("name"), "url": rp.get("html_url")}
    return list(out.values())[:60]

ZB_MAP = {"valid": "valid", "invalid": "invalid", "catch-all": "accept_all", "unknown": "unknown",
          "spamtrap": "risky", "abuse": "risky", "do_not_mail": "risky"}
HUNTER_MAP = {"valid": "valid", "invalid": "invalid", "accept_all": "accept_all", "unknown": "unknown",
              "webmail": "valid", "disposable": "risky"}
zb_left = hv_left = 0

def zb_verify(email):
    d = get_json("https://api.zerobounce.net/v2/validate",
                 params={"api_key": ZEROBOUNCE_KEY, "email": email, "ip_address": ""}, timeout=45) or {}
    st = ZB_MAP.get(str(d.get("status", "")).lower())
    return {"status": st, "by": "ZeroBounce", "detail": d.get("sub_status")} if st else None

def hunter_verify(email):
    d = get_json("https://api.hunter.io/v2/email-verifier", params={"email": email, "api_key": HUNTER_KEY},
                 timeout=45) or {}
    data = d.get("data") or {}
    st = HUNTER_MAP.get(str(data.get("status", "")).lower())
    return {"status": st, "by": "Hunter", "detail": data.get("score")} if st else None

def verify_email(email):
    """ZeroBounce first (100 free), Hunter next (or when ZeroBounce says 'unknown'). Cached forever."""
    global zb_left, hv_left
    if email in verify_cache:
        return verify_cache[email]
    res = None
    if ZEROBOUNCE_KEY and zb_left > 0:
        res = zb_verify(email)
        if res:
            zb_left -= 1
    if (res is None or res["status"] == "unknown") and HUNTER_KEY and hv_left > 0:
        r2 = hunter_verify(email)
        if r2:
            hv_left -= 1
            res = r2 if (res is None or r2["status"] != "unknown") else res
    if res:
        verify_cache[email] = {**res, "date": today()}
        save_json("verify_cache.json", verify_cache)
    return res

def grade_tied(source, conf):
    if source in ("official site", "structured data"):
        return "A · published"
    if source in ("Hunter.io", "Tomba"):
        return "B · strong" if (conf or 0) >= 70 else "C · likely"
    return "B · strong"


companies_mail, all_contacts = {}, []
_emails_cut = False
for n in work_order(profiles):
    if n not in people_db:
        continue
    if not _emails_cut and stage_over("emails"):
        _emails_cut = True    # keep listing companies already worked on, but stop spending lookups
    p, pdb = profiles[n], people_db[n]
    web_dom = domain_of(p.get("website"))
    site = to_dict_emails(p["crawl"].get("emails"), p.get("website"))
    people = [dict(x) for x in pdb["people"]]

    # --- evidence: every real email we have seen for this company ---
    evidence = [{"email": e, "source": "official site", "url": u} for e, u in site.items()]
    evidence += pdb.get("evidence", [])
    for x in people:
        evidence += [{**e, "name": x["name"]} for e in x.get("emails", [])]
    mail_dom = choose_mail_domain(web_dom, [e["email"] for e in evidence])

    org = p["crawl"].get("github_org")
    if org and mail_dom:
        if org not in gh_cache and not _gh_blocked and not _emails_cut:
            res = github_emails(org)
            if res is not None:
                gh_cache[org] = res
                save_json("github_cache.json", gh_cache)
        evidence += [{"email": g["email"], "source": "GitHub commits", "url": g["url"], "name": g.get("name")}
                     for g in gh_cache.get(org, [])]

    mx = None
    if mail_dom:
        if (mail_dom not in mx_cache or mx_cache[mail_dom].get("has_mx") is None) and not _emails_cut:
            mx_cache[mail_dom] = mx_lookup(mail_dom)
        mx = mx_cache.get(mail_dom)

    own = {}
    for e in evidence:
        if mail_dom and at_domain(e["email"], mail_dom) and not is_generic(e["email"]):
            own.setdefault(e["email"], e)

    # --- learn the pattern from real (email, name) pairs ---
    votes, support = Counter(), defaultdict(set)
    for e in own.values():
        local = e["email"].split("@")[0]
        names = [e["name"]] if e.get("name") else []
        names += [x["name"] for x in people if matching_patterns(local, *split_name(x["name"]))]
        for nm in dict.fromkeys(names):
            first, last = split_name(nm)
            pats = matching_patterns(local, first, last)
            for pt in pats:
                votes[pt] += 1 / len(pats)
                support[pt].add(e["email"])
        if not names:   # unnamed hints (weak)
            if re.fullmatch(r"[a-z]{2,}\.[a-z]{2,}", local):
                votes["{first}.{last}"] += 0.3
            elif re.fullmatch(r"[a-z]{3,12}", local):
                votes["{first}"] += 0.2
    fpats = dict(pdb.get("finder_patterns") or {})
    if pdb.get("hunter_pattern"):   # files from v2
        fpats.setdefault("hunter.io", pdb["hunter_pattern"])
    for label, hp in fpats.items():
        if hp in EMAIL_TEMPLATES:
            votes[hp] += 1.5
            support[hp].add(label)
    ranked_pats = [pt for pt, _ in votes.most_common()]
    best = ranked_pats[0] if ranked_pats else None
    real = len([s for s in support.get(best, set()) if s not in FINDER_LABELS]) if best else 0
    by_finder = bool(best and support.get(best, set()) & FINDER_LABELS)
    if best and (real >= 2 or (real == 1 and by_finder) or len(support.get(best, set()) & FINDER_LABELS) == 2):
        pat_status, pat_grade = f"confirmed ({real} email(s){' + finder' if by_finder else ''})", "B · strong"
    elif best and real == 1:
        pat_status, pat_grade = "seen once", "C · likely"
    elif by_finder:
        pat_status, pat_grade = "email finder's pattern", "C · likely"
    elif best:
        pat_status, pat_grade = "weak hint", "D · guess"
    else:
        pat_status, pat_grade = "no evidence", "D · guess"
    candidates = list(dict.fromkeys(ranked_pats + COMMON_PATTERNS))

    # --- best email for each person ---
    for x in people:
        first, last = split_name(x["name"])
        opts = []
        for e in x.get("emails", []):
            opts.append((e["email"], grade_tied(e["source"], e.get("conf")), f"{e['source']}: {e.get('url') or ''}".strip(": ")))
        for e in own.values():
            local = e["email"].split("@")[0]
            named_other = e.get("name") and not same_person({"name": e["name"]}, x)
            if not named_other and first and matching_patterns(local, first, last) and (last or local == first):
                g = "A · published" if e["source"] == "official site" else "B · strong"
                opts.append((e["email"], g, f"{e['source']}: {e.get('url') or ''}".strip(": ")))
        x["guess_queue"] = []
        if opts:
            opts.sort(key=lambda o: GRADE_RANK[o[1]])
            x["email"], x["email_grade"], x["email_source"] = opts[0]
        elif mail_dom and first:
            locs = [apply_pattern(pt, first, last) for pt in candidates]
            locs = [l for l in dict.fromkeys(locs) if l]
            if locs:
                x["email"] = f"{locs[0]}@{mail_dom}"
                g = pat_grade if apply_pattern(best, first, last) == locs[0] else "D · guess"
                x["email_grade"] = g
                x["email_source"] = f"built from pattern {candidates[0]} ({pat_status})"
                x["guess_queue"] = [f"{l}@{mail_dom}" for l in locs[1:]]
        else:
            x["email"] = x["email_grade"] = x["email_source"] = None
        x["verification"] = None
        if x.get("email") and mx and mx.get("has_mx") is False and at_domain(x["email"], mail_dom):
            x["verification"] = "domain has no mail server"
            if x["email_grade"] != "A · published":   # a published address is kept; guesses are downgraded
                x["email_grade"] = "D · guess"

    careers = [e for e in site if is_generic(e) and e.split("@")[0].split(".")[0] in CAREER_LOCAL]
    general = (p["profile"].get("contact") or {}).get("general_email") \
        or next((e for e in site if is_generic(e) and e not in careers), None) \
        or next((e for e in site if e.split("@")[1] in FREE_MAIL), None)
    companies_mail[n] = {
        "mail_domain": mail_dom, "mail_provider": (mx or {}).get("provider"),
        "receives_mail": (mx or {}).get("has_mx"), "pattern": best or None, "pattern_status": pat_status,
        "pattern_examples": ", ".join(sorted(s for s in support.get(best, set()) if s not in FINDER_LABELS)[:4]) if best else None,
        "accept_all": pdb.get("accept_all") or pdb.get("hunter_accept_all"), "careers_email": careers[0] if careers else None,
        "general_email": general,
        "phone": (p["profile"].get("contact") or {}).get("phone") or next(iter(p["crawl"].get("phones", [])), None),
        "contact_page": p["crawl"].get("contact_url"), "startup": company_tier(p) in (1, 2),
    }
    for x in people:
        all_contacts.append({"company": n, **x})

# --- verification: best-ranked companies first, top 2 contacts each, only C/D emails ---
if ZEROBOUNCE_KEY:
    d = get_json("https://api.zerobounce.net/v2/getcredits", params={"api_key": ZEROBOUNCE_KEY}) or {}
    try:
        zb_left = min(ZEROBOUNCE_VERIFY_MAX, max(int(float(d.get("Credits"))), 0))
    except Exception:
        zb_left = ZEROBOUNCE_VERIFY_MAX
if HUNTER_KEY:
    acc = hunter_account()   # live: already reflects credits Cell 7 spent
    hv_left = int(min(HUNTER_VERIFY_MAX, acc["verify"] if acc["verify"] is not None else HUNTER_VERIFY_MAX))
if zb_left + hv_left > 0:
    print(f"Free verifications this run: ZeroBounce {zb_left} · Hunter {hv_left}")
    by_co = defaultdict(list)
    for c in all_contacts:
        if c["key_contact"]:
            by_co[c["company"]].append(c)
    for n in work_order(profiles):
        if zb_left + hv_left <= 0:
            break
        cm = companies_mail.get(n)
        if not cm:
            continue
        top = sorted(by_co.get(n, []), key=lambda c: contact_sort_key(c, cm["startup"]))[:2]
        for c in top:
            tries = 0
            while (not stage_over("emails") and zb_left + hv_left > 0 and c.get("email")
                   and c["email_grade"] in ("C · likely", "D · guess")
                   and tries < VERIFY_TRIES_PER_PERSON and not cm.get("accept_all")
                   and cm.get("receives_mail") is not False):
                v = verify_email(c["email"])
                tries += 1
                if not v:
                    break
                st = v["status"]
                if st == "valid":
                    c["email_grade"], c["verification"] = "A · verified", f"valid ({v['by']})"
                    pt = next((pt for pt in EMAIL_TEMPLATES
                               if apply_pattern(pt, *split_name(c["name"])) == c["email"].split("@")[0]), None)
                    if pt:
                        cm["pattern"], cm["pattern_status"] = pt, f"verified on {c['name']}"
                elif st == "accept_all":
                    cm["accept_all"] = True
                    c["verification"] = "server accepts every address, so it can't be confirmed"
                elif st == "invalid":
                    c["verification"] = f"{c['email']} failed verification"
                    if c["guess_queue"]:
                        c["email"] = c["guess_queue"].pop(0)
                        c["email_grade"], c["email_source"] = "D · guess", "next common pattern"
                        continue
                    c["email"] = None
                    c["email_grade"] = None
                elif st == "risky":
                    c["verification"] = f"risky address ({v['by']}: {v.get('detail')}) — don't use"
                    c["email_grade"] = "D · guess"
                else:
                    c["verification"] = f"{v['by']}: {st}"
                break

    # a verified colleague confirms the pattern for everyone else at that company
    for c in all_contacts:
        cm = companies_mail[c["company"]]
        if (str(cm.get("pattern_status", "")).startswith("verified") and c.get("email")
                and c["email_grade"] in ("C · likely", "D · guess")
                and apply_pattern(cm["pattern"], *split_name(c["name"])) == c["email"].split("@")[0]):
            c["email_grade"] = "B · strong"
            c["email_source"] = f"pattern {cm['pattern']} ({cm['pattern_status']})"

save_json("mx_cache.json", mx_cache)

cols = ["company", "name", "category", "role", "key_contact", "person_confidence", "source_types", "email",
        "email_grade", "email_source", "verification", "linkedin", "sources"]
contacts = pd.DataFrame(all_contacts).reindex(columns=cols)
if len(contacts):
    contacts["source_types"] = contacts["source_types"].apply(lambda v: ", ".join(v) if isinstance(v, list) else v)
    contacts["sources"] = contacts["sources"].apply(
        lambda v: " | ".join(dict.fromkeys(s["url"] for s in v if s.get("url"))) if isinstance(v, list) else v)
    contacts["_g"] = contacts["email_grade"].map(GRADE_RANK).fillna(9)
    contacts = contacts.sort_values(["company", "key_contact", "_g"], ascending=[True, False, True]).drop(columns="_g")
contacts.to_csv(fpath("contacts.csv"), index=False)
mail_info = pd.DataFrame([{"company": k, **v} for k, v in companies_mail.items()])
mail_info.to_csv(fpath("company_mail.csv"), index=False)

key = contacts[contacts["key_contact"] == True] if len(contacts) else contacts
print(f"\n{len(contacts)} people · {len(key)} key contacts · key contacts with an email: {int(key['email'].notna().sum())}")
print("Email grades (key contacts):")
print(key["email_grade"].fillna("no email").value_counts().reindex(GRADES + ["no email"]).dropna().astype(int).to_string())
display(key.head(20))

# ----------------------------------------------------------------------
# CELL 9 — Rank: India startups first, then other startups, then corporates.
# Inside each tier: priority-1 fields first, then fit score (0–100).

SKILL_WORDS = [s.lower() for s in PROFILE["skills"]] + ["artificial intelligence", "neural", "optimization",
                                                        "simulation", "data science", "robotics", "automation"]
YEAR_NOW = datetime.now().year
assert profiles, "No profiles yet. Run Cell 5 first."

def text_of(pr, inp):
    parts = [pr.get("one_liner"), pr.get("what_they_do"), inp.get("what_they_do"),
             " ".join(str(t) for t in as_list(pr.get("tech_and_methods"))),
             " ".join(f"{x.get('name', '')} {x.get('description', '')}" for x in as_list(pr.get("products")) if isinstance(x, dict)),
             " ".join(str(x.get("item", "")) for x in as_list(pr.get("research_and_discoveries")) if isinstance(x, dict))]
    return " ".join(str(x) for x in parts if x).lower()

rank_rows = []
for name, p in profiles.items():
    inp, pr = p["input"], p.get("profile") or {}
    profiled = p.get("status") == "ok"
    tier = company_tier(p)
    txt = text_of(pr, inp)
    why, score = [], 0

    prio = inp.get("priority") or 2
    score += 30 if prio == 1 else 12
    why.append("main field" if prio == 1 else "broad field")

    hits = [w for ws in INTEREST_WORDS.values() for w in ws if w in txt]
    if hits:
        score += min(15, 5 * len(hits)); why.append("works on " + ", ".join(hits[:3]))
    skills = [w for w in SKILL_WORDS if re.search(r"\b" + re.escape(w) + r"\b", txt)]
    if skills:
        score += min(20, 5 * len(skills)); why.append("uses " + ", ".join(skills[:3]))

    cj = jobs[jobs["company"] == name] if len(jobs) else jobs
    n_rel = int(cj["relevant"].sum()) if len(cj) else 0
    if n_rel:
        score += 15; why.append(f"{n_rel} relevant open role(s)")
    elif len(cj):
        score += 7; why.append(f"{len(cj)} open role(s)")

    cc = contacts[(contacts["company"] == name) & (contacts["key_contact"] == True)] if len(contacts) else contacts
    best_g = min([GRADE_RANK.get(g, 9) for g in cc["email_grade"]] or [9]) if len(cc) else 9
    if best_g <= 2:
        score += 10; why.append("key contact with a reliable email")
    elif best_g <= 4:
        score += 6; why.append("key contact with an email to verify")
    elif len(cc):
        score += 3; why.append("key contact found (LinkedIn)")

    city = str(pr.get("hq_city") or inp.get("city") or "")
    if city and any(c.lower() in city.lower() for c in CITIES):
        score += 5; why.append(f"in {city}")

    f = pr.get("funding") if isinstance(pr.get("funding"), dict) else {}
    yr = re.search(r"(20\d\d)", str(f.get("last_round_date") or ""))
    if yr and int(yr.group(1)) >= YEAR_NOW - 1:
        score += 5; why.append(f"raised in {yr.group(1)}")

    rank_rows.append({
        "tier": TIER_LABEL[tier], "_tier": tier, "priority": prio, "fit_score": min(score, 100) if profiled else None,
        "company": pr.get("official_name") or name, "_key": name, "fields": inp.get("domains"),
        "why_it_fits": "; ".join(why) if profiled else "not profiled yet",
        "city": city or None, "country": pr.get("country") or inp.get("country"),
        "founded": pr.get("founded_year"), "stage": pr.get("stage"), "employees": pr.get("employee_count"),
        "one_liner": pr.get("one_liner") or inp.get("what_they_do"), "what_they_do": pr.get("what_they_do"),
        "products": "; ".join(f"{x.get('name')}: {x.get('description')}" for x in as_list(pr.get("products")) if isinstance(x, dict)),
        "research_and_discoveries": "; ".join(str(x.get("item")) for x in as_list(pr.get("research_and_discoveries")) if isinstance(x, dict)),
        "tech": ", ".join(str(t) for t in as_list(pr.get("tech_and_methods"))),
        "total_funding": f.get("total"), "last_round": f.get("last_round"),
        "last_round_amount": f.get("last_round_amount"), "last_round_date": f.get("last_round_date"),
        "investors": ", ".join(str(i) for i in as_list(f.get("investors"))),
        "open_roles": len(cj), "relevant_roles": n_rel,
        "website": p.get("website"), "careers_page": (p.get("crawl") or {}).get("careers_url"),
        "linkedin_company": (p.get("crawl") or {}).get("linkedin_company"),
        "funding_source": f.get("source"),
        "sources": " | ".join((p.get("pages_read") or [])[:3] + (p.get("search_sources") or [])[:3]),
        "updated": p.get("updated"),
    })

ranked = pd.DataFrame(rank_rows)
ranked["founded"] = pd.to_numeric(ranked["founded"], errors="coerce").astype("Int64")
ranked["_fit"] = ranked["fit_score"].fillna(-1)
ranked = ranked.sort_values(["_tier", "priority", "_fit"], ascending=[True, True, False]).reset_index(drop=True)
ranked.insert(0, "rank", range(1, len(ranked) + 1))
ranked = ranked.drop(columns=["_tier", "_fit"])
ranked.to_csv(fpath("ranked.csv"), index=False)
print(ranked["tier"].value_counts().sort_index().to_string())
display(ranked[["rank", "tier", "company", "fields", "fit_score", "why_it_fits", "city", "founded", "last_round"]].head(25))

# ----------------------------------------------------------------------
# CELL 10 — Outreach plan: who to contact first at each company, how, and what to say

def match_project(txt):
    """Best-matching project + the matched phrases, written as they appear in the company's text."""
    best = None
    for pj in PROFILE["projects"]:
        hits = []
        for k in pj["keywords"]:
            m = re.search(r"[a-z-]*" + re.escape(k) + r"[a-z-]*", txt)
            if m:
                hits.append(m.group(0).strip("-"))
        if hits and (best is None or len(hits) > len(best[1])):
            best = (pj, hits)
    return best

def first_name(n):
    return str(n).split()[0] if n else "there"

def talking_point(pr, inp, txt):
    bits = []
    m = match_project(txt)
    if m:
        bits.append(f"Lead with {m[0]['name']} — it links to their work on {m[1][0]}.")
    prods = [x.get("name") for x in as_list(pr.get("products")) if isinstance(x, dict) and x.get("name")]
    res = [x.get("item") for x in as_list(pr.get("research_and_discoveries")) if isinstance(x, dict) and x.get("item")]
    if res:
        bits.append(f"Mention their {res[0]}.")
    elif prods:
        bits.append(f"Ask how {prods[0]} works under the hood.")
    f = pr.get("funding") if isinstance(pr.get("funding"), dict) else {}
    yr = re.search(r"(20\d\d)", str(f.get("last_round_date") or ""))
    if f.get("last_round") and yr and int(yr.group(1)) >= YEAR_NOW - 1:
        bits.append(f"They raised a {f['last_round']} ({f.get('last_round_date')}) — likely hiring.")
    return " ".join(bits) or "Read their site first and mention one specific product or result."

def linkedin_note(person, company, pr, txt):
    """Connection note, kept under 200 characters (LinkedIn's limit for free accounts)."""
    m = match_project(txt)
    topic = (m[1][0] if m else (pr.get("one_liner") or "your work")).rstrip(".")
    proj = m[0]["short"] if m else "AI/ML projects"
    notes = [
        f"Hi {first_name(person)}, I'm {PROFILE['name']}, a final-year AI student. I built {proj}, close to {company}'s work on {topic}. Would love to connect and learn about your team.",
        f"Hi {first_name(person)}, I'm {PROFILE['name']}, a final-year AI student. I work on {proj} and admire {company}'s work. Would love to connect.",
        f"Hi {first_name(person)}, final-year AI student here. Keen on {company}'s work — would love to connect.",
    ]
    return next((t for t in notes if len(t) <= 200), notes[-1][:200])

def channel(c):
    if not c:
        return "Careers email / contact page"
    g = c.get("email_grade")
    if g in ("A · verified", "A · published", "B · strong"):
        return "Email" + (" + LinkedIn" if c.get("linkedin") else "")
    if g in ("C · likely", "D · guess"):
        return ("LinkedIn first; email after verifying" if c.get("linkedin") else "Email after verifying (Hunter free check)")
    return "LinkedIn" if c.get("linkedin") else "Careers email / contact page"

con_by_co = defaultdict(list)
for c in contacts.to_dict("records") if len(contacts) else []:
    if c["key_contact"]:
        con_by_co[c["company"]].append(c)

plan_rows = []
for r in ranked.to_dict("records"):
    n = r["_key"]
    p = profiles[n]
    if p.get("status") != "ok":
        continue
    pr, inp = p["profile"], p["input"]
    cm = companies_mail.get(n, {})
    startup = company_tier(p) in (1, 2)
    cs = sorted(con_by_co.get(n, []), key=lambda c: contact_sort_key(c, startup))
    c1 = cs[0] if cs else None
    c2 = next((c for c in cs[1:]), None)
    hr = next((c for c in cs if c["category"] == "Hiring / HR" and c not in (c1, c2)), None)
    txt = text_of(pr, inp)
    cj = jobs[(jobs["company"] == n) & (jobs["relevant"] == True)] if len(jobs) else jobs
    row = {"rank": r["rank"], "tier": r["tier"], "company": r["company"], "fields": r["fields"],
           "fit_score": r["fit_score"], "channel": channel(c1)}
    for tag, c in (("contact_1", c1), ("contact_2", c2), ("hiring_contact", hr)):
        row[f"{tag}"] = c["name"] if c else None
        row[f"{tag}_role"] = c["role"] if c else None
        row[f"{tag}_email"] = c["email"] if c else None
        row[f"{tag}_grade"] = c["email_grade"] if c else None
        row[f"{tag}_linkedin"] = c["linkedin"] if c else None
        if tag != "hiring_contact":
            row[f"{tag}_sure_they_work_there"] = c["person_confidence"] if c else None
    row.update({
        "careers_email": cm.get("careers_email"), "general_email": cm.get("general_email"), "phone": cm.get("phone"),
        "contact_page": cm.get("contact_page"), "careers_page": r.get("careers_page"),
        "relevant_roles": "; ".join(f"{t} ({l})" if isinstance(l, str) and l else str(t) for t, l in zip(cj["title"], cj["location"]))[:300] if len(cj) else None,
        "talking_point": talking_point(pr, inp, txt),
        "linkedin_note": linkedin_note(c1["name"], r["company"], pr, txt) if c1 else None,
        "email_pattern": cm.get("pattern"), "pattern_status": cm.get("pattern_status"),
        "mail_provider": cm.get("mail_provider"), "_key": n,
    })
    plan_rows.append(row)

plan = pd.DataFrame(plan_rows)
plan.to_csv(fpath("outreach_plan.csv"), index=False)
print(f"{len(plan)} companies in the plan · with a reliable email (A/B) for contact 1: "
      f"{int(plan['contact_1_grade'].isin(GRADES[:3]).sum()) if len(plan) else 0}")
display(plan[["rank", "company", "contact_1", "contact_1_role", "contact_1_email", "contact_1_grade", "channel"]].head(20))

# ----------------------------------------------------------------------
# CELL 11 — Email drafts for the top companies (optional; uses DRAFT_TOP_N Gemini calls)
# Uses only facts found about the company. Read and edit every draft before sending.

DRAFT_PROMPT = """Write a short cold email from a student to a person at a company.
Sender: {me_name}, {me_intro}. GitHub: {me_github}.
Sender's most relevant project: {project}.
Recipient: {person} ({role}) at {company}.
Facts about the company (use ONLY these, do not invent anything):
{facts}
Rules:
- 90 to 130 words. Plain, warm, direct. No flattery clichés, no "I hope this email finds you well".
- First line: one specific fact about their work.
- Then: how the sender's project connects to it, in one or two sentences.
- Ask: a 15-minute chat, and whether they take interns or freshers in AI/ML.
- Sign off with the sender's name.
Return JSON: {{"subject": str, "body": str}}"""

drafts = load_json("drafts.json", {})
made = 0
for r in plan.head(DRAFT_TOP_N).to_dict("records"):
    if stage_over("drafts"):
        break
    if not isinstance(r.get("contact_1"), str):   # no person found: nothing to draft
        continue
    k = f"{r['_key']}|{r['contact_1']}"
    if k in drafts:
        continue
    pr = profiles[r["_key"]]["profile"]
    txt = text_of(pr, profiles[r["_key"]]["input"])
    m = match_project(txt)
    f = pr.get("funding") if isinstance(pr.get("funding"), dict) else {}
    facts = "\n".join(f"- {x}" for x in [
        pr.get("what_they_do"),
        *[f"Product: {x.get('name')} — {x.get('description')}" for x in as_list(pr.get("products"))[:2] if isinstance(x, dict)],
        *[f"Research: {x.get('item')}" for x in as_list(pr.get("research_and_discoveries"))[:2] if isinstance(x, dict)],
        f"Funding: {f.get('last_round')} {f.get('last_round_amount') or ''} {f.get('last_round_date') or ''}" if f.get("last_round") else None,
    ] if x)
    out = ask_gemini(DRAFT_PROMPT.format(
        me_name=PROFILE["name"], me_intro=PROFILE["intro"], me_github=PROFILE["github"],
        project=m[0]["name"] if m else PROFILE["projects"][0]["name"],
        person=r["contact_1"], role=r["contact_1_role"] or "team member", company=r["company"], facts=facts or "-"),
        temperature=0.6)
    if isinstance(out, dict) and out.get("body"):
        drafts[k] = {"subject": out.get("subject"), "body": out["body"], "to": r["contact_1_email"],
                     "grade": r["contact_1_grade"], "date": today()}
        save_json("drafts.json", drafts)
        made += 1
    elif gemini_exhausted():
        print("Gemini daily limit reached. Rerun this cell later.")
        break

plan["email_subject"] = plan.apply(lambda r: (drafts.get(f"{r['_key']}|{r['contact_1']}") or {}).get("subject"), axis=1)
plan["email_draft"] = plan.apply(lambda r: (drafts.get(f"{r['_key']}|{r['contact_1']}") or {}).get("body"), axis=1)
print(f"{made} new drafts · {int(plan['email_draft'].notna().sum())} companies have a draft")
plan.to_csv(fpath("outreach_plan.csv"), index=False)   # now with drafts, for the web app
for r in plan[plan["email_draft"].notna()].head(2).to_dict("records"):
    print(f"\n--- To: {r['contact_1']} <{r['contact_1_email']}> [{r['contact_1_grade']}]\nSubject: {r['email_subject']}\n{r['email_draft']}")

# ----------------------------------------------------------------------
# CELL 12 — Export to Excel (saved to Drive and downloaded)
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

rank_of = dict(zip(ranked["_key"], ranked["rank"]))
tier_of_key = dict(zip(ranked["_key"], ranked["tier"]))

people_sheet = contacts.copy()
if len(people_sheet):
    people_sheet.insert(0, "company_rank", people_sheet["company"].map(rank_of))
    people_sheet.insert(1, "tier", people_sheet["company"].map(tier_of_key))
    people_sheet["_g"] = people_sheet["email_grade"].map(GRADE_RANK).fillna(9)
    people_sheet = people_sheet.sort_values(["company_rank", "key_contact", "_g"], ascending=[True, False, True]).drop(columns="_g")

jobs_sheet = jobs.copy()
if len(jobs_sheet):
    jobs_sheet.insert(0, "company_rank", jobs_sheet["company"].map(rank_of))
    jobs_sheet = jobs_sheet.sort_values(["relevant", "company_rank"], ascending=[False, True])

rounds = []
for name, p in profiles.items():
    for r in as_list((p.get("profile") or {}).get("funding_rounds")):
        if isinstance(r, dict):
            rounds.append({"company_rank": rank_of.get(name), "company": name, "round": r.get("round"),
                           "amount": r.get("amount"), "date": r.get("date"),
                           "investors": ", ".join(str(i) for i in as_list(r.get("investors"))), "source": r.get("source")})
rounds = pd.DataFrame(rounds, columns=["company_rank", "company", "round", "amount", "date", "investors", "source"])
if len(rounds):
    rounds = rounds.sort_values(["company_rank", "date"])

mail_sheet = mail_info.copy()
if len(mail_sheet):
    mail_sheet.insert(0, "company_rank", mail_sheet["company"].map(rank_of))
    mail_sheet = mail_sheet.sort_values("company_rank")

not_done = companies[~companies["name"].isin(profiles.keys())]

sheets = {
    "Outreach plan": plan.drop(columns=["_key"]),
    "Ranked companies": ranked.drop(columns=["_key"]),
    "Contacts": people_sheet,
    "Open roles": jobs_sheet,
    "Funding rounds": rounds,
    "Email patterns": mail_sheet,
    "Not profiled yet": not_done,
}
OUT_XLSX = fpath("job_finder_results.xlsx")
HEADER = PatternFill("solid", fgColor="DCE8F2")
GRADE_FILL = {"A · verified": "C6E7C6", "A · published": "D5EDD5", "B · strong": "E6F3DA",
              "C · likely": "FFF2CC", "D · guess": "FCE4D6", "High": "D5EDD5", "Medium": "FFF2CC", "Low": "FCE4D6"}
WIDE = {"why_it_fits", "what_they_do", "products", "research_and_discoveries", "one_liner", "sources",
        "investors", "tech", "talking_point", "linkedin_note", "email_draft", "relevant_roles", "email_source"}

with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xw:
    for sname, sdf in sheets.items():
        sdf.to_excel(xw, sheet_name=sname, index=False)
        ws = xw.sheets[sname]
        ws.freeze_panes = "D2" if sname == "Outreach plan" else "B2" if sname == "Ranked companies" else "A2"
        for cell in ws[1]:
            cell.font, cell.fill = Font(bold=True), HEADER
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        for i, col in enumerate(sdf.columns, 1):
            letter = get_column_letter(i)
            width = 60 if col == "email_draft" else 48 if col in WIDE else min(
                40, max(10, len(str(col)) + 2, *(len(str(v)) + 2 for v in sdf[col].head(200))))
            ws.column_dimensions[letter].width = width
            for c in ws[letter][1:]:
                c.alignment = Alignment(wrap_text=col in WIDE, vertical="top")
                v = c.value
                if isinstance(v, str) and v in GRADE_FILL:
                    c.fill = PatternFill("solid", fgColor=GRADE_FILL[v])
                elif isinstance(v, str) and v.startswith("http") and " " not in v:
                    c.hyperlink, c.font = v, Font(color="1F5FA8", underline="single")
        ws.auto_filter.ref = ws.dimensions

print("Saved:", OUT_XLSX)
for s, d in sheets.items():
    print(f"  {s}: {len(d)} rows")
if IN_COLAB:
    files.download(OUT_XLSX)

save_json("run_status.json", {
    "finished_ist": (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%d %b %Y %H:%M IST"),
    "companies_found": int(len(companies)), "profiled": int(sum(p.get("status") == "ok" for p in profiles.values())),
    "people_searched": int(len(people_db)), "contacts": int(len(contacts)),
    "key_contacts_with_reliable_email": int(contacts[(contacts["key_contact"] == True) & contacts["email_grade"].isin(GRADES[:3])].shape[0]) if len(contacts) else 0,
    "open_roles": int(len(jobs)),
})

# ---- notes
# ### Running it again
# - **More companies:** rerun Cell 5 (profiles) and Cell 7 (people). Each continues where it stopped.
# - **More verified emails:** each month, when the free credits reset, rerun Cells 7 → 12. Companies that missed out on finder credits are topped up first, then new ones. Emails already checked are never checked again.
#
# ### Monthly routine to get the most out of the free tiers
# | When | Do | Free credits it uses |
# |---|---|---|
# | Day 1 of the month | Cells 7 → 12 | Tomba 25, Hunter 50, ZeroBounce 100, Tavily 1,000 refill |
# | Any day | Cell 5 (40 companies) → Cell 7 (40) | Gemini daily limits reset midnight Pacific (12:30 pm IST) |
# | Weekly | Cells 6, 9 → 12 | none (job boards are free) |
# | Once | Keep Serper's 2,500 Google searches for LinkedIn people search (it's one-time) | — |
# - **Fresh jobs:** rerun Cells 6 and 9 → 12. Job boards are re-read every time.
# - **New sectors or cities:** edit Cell 2, then rerun from Cell 4. Only new searches run.
# - **Start from scratch:** delete the files in `MyDrive/job_finder/`.
#
# ### Using the contacts well
# - **Start with the Outreach plan sheet.** Rows are in rank order; contact 1 is the best person for that kind of company (founders at startups, AI/research leads at corporates).
# - **A or B grade:** email directly. **C or D:** check it first (Hunter's free verifier, or ask on LinkedIn), or send the LinkedIn note.
# - **"Sure they work there" = Low:** the person was found in only one weak source (often registry or old news). Check their LinkedIn before writing.
# - Write one personal email per person. Don't send the same text to many people at one company. Follow up once after 5–7 days, then stop.
# - This is public, professional contact data. Use it only for your own job outreach, and remove anyone who asks.
