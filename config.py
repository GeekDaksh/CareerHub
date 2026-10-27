"""
Career Hub settings — the ONLY file you might ever edit.
Everything else runs by itself (GitHub Actions + Hugging Face).
"""

# ============================ ABOUT YOU ============================
PROFILE = {
    "name": "Daksh Patil",
    "first_name": "Daksh",
    "intro": "a final-year B.Tech AI student at NMIMS MPSTME, Mumbai (graduating 2027)",
    "headline": "AI/ML engineer — Python, PyTorch, LLM apps (LangGraph, RAG), computer vision, optimisation",
    "skills": ["Python", "PyTorch", "scikit-learn", "TensorFlow", "LangGraph", "FAISS",
               "Bayesian optimization", "BoTorch", "computer vision", "reinforcement learning",
               "machine learning", "deep learning", "LLM", "RAG", "C++", "embedded", "STM32"],
    # short = how a message mentions it; keywords = words that link it to a company's or client's work
    "projects": [
        {"name": "Self-Driving Lab for M-Sand concrete (Bayesian optimisation)",
         "short": "a self-driving lab for concrete mix design",
         "keywords": ["self-driving lab", "lab automation", "bayesian optimi", "experiment design", "materials",
                      "active learning", "closed-loop", "optimization", "optimisation", "high-throughput"]},
        {"name": "Uncertainty-aware multi-agent battery charging (BMS) — accepted at INDICON 2026",
         "short": "a multi-agent battery-charging system (accepted at INDICON 2026)",
         "keywords": ["battery", "bms", "energy storage", "electric vehicle", "multi-agent", "energy", "ev charging",
                      "reinforcement learning"]},
        {"name": "MediaLens — emotion-aware scene search, SafeCut video moderation, multimodal sarcasm detection",
         "short": "MediaLens, a multimodal video-understanding project",
         "keywords": ["video", "multimodal", "content moderation", "scene search", "sentiment", "emotion",
                      "nlp", "speech", "media", "computer vision"]},
        {"name": "FARM-AID", "short": "FARM-AID",
         "keywords": ["agri", "farm", "crop", "agritech", "agriculture"]},
        {"name": "Ballistics fire-control simulation (L&T internship)",
         "short": "a ballistics fire-control simulation at L&T",
         "keywords": ["simulation", "defence", "defense", "fire control", "ballistic", "drone"]},
        {"name": "STM32 firmware for an mmWave radar product (Meshnet internship)",
         "short": "STM32 firmware for an mmWave radar",
         "keywords": ["embedded", "firmware", "stm32", "radar", "iot", "microcontroller", "sensor"]},
    ],
}

# ============================ JOB FINDER (companies) ============================
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
CITIES = ["Bengaluru", "Pune", "Mumbai", "Hyderabad"]
EXTRA_COMPANIES = [
    # {"name": "Company Name", "website": "https://company.com", "domain": "bioinformatics", "type": "startup"},
]

# ============================ GIG RADAR (freelance / paid tasks) ============================
# Categories in priority order. ai_tasks = paid AI-training / evaluation work.
GIG_CATEGORIES = {
    "ai_tasks": {"label": "AI training & eval tasks", "weight": 1.0,
                 "words": ["ai trainer", "ai training", "rlhf", "llm evaluat", "model evaluat", "data annotat",
                           "ai tutor", "prompt engineer", "red team", "ai rater", "code review for ai",
                           "coding expert", "ai data", "train ai", "human feedback"]},
    "tech": {"label": "Tech / AI freelance", "weight": 0.95,
             "words": ["python", "machine learning", "deep learning", "pytorch", "tensorflow", "scikit",
                       "computer vision", "opencv", "yolo", "nlp", "llm", "chatbot", "langchain", "langgraph",
                       "rag", "openai", "gpt", "gemini api", "ai agent", "automation", "web scraping", "scraper",
                       "selenium", "playwright", "data analysis", "pandas", "data science", "streamlit", "flask",
                       "fastapi", "api integration", "telegram bot", "discord bot", "n8n", "zapier", "make.com",
                       "embedded", "arduino", "stm32", "raspberry pi", "matlab", "optimization", "jupyter",
                       "kaggle", "model training", "fine-tun", "huggingface", "hugging face"]},
    "content": {"label": "Content & technical writing", "weight": 0.7,
                "words": ["technical writ", "content writ", "blog", "article", "copywrit", "ghostwrit",
                          "documentation", "tutorial", "ai content", "newsletter", "script writ", "research writ"]},
    "marketing": {"label": "Marketing", "weight": 0.55,
                  "words": ["social media", "digital marketing", "seo", "email marketing", "lead generation",
                            "growth", "instagram", "linkedin content", "marketing automation", "ads", "content marketing"]},
}

# Search words sent to each gig source (kept short: each word = one request per run)
GIG_QUERIES = {
    "tech": ["python", "machine learning", "web scraping", "automation", "chatbot", "data analysis",
             "computer vision", "LLM", "deep learning", "API"],
    "content": ["technical writing", "content writing", "blog writing"],
    "marketing": ["social media marketing", "SEO"],
    "ai_tasks": ["AI trainer", "data annotation", "LLM evaluation"],
}

# Your time: under 8 hours/week -> favour small, well-paid tasks
HOURS_PER_WEEK = 8
MONTHLY_GOAL_INR = (15000, 40000)
MIN_HOURLY_INR = 500           # ignore hourly gigs below this
FIXED_SWEET_SPOT_INR = (2000, 60000)
MAX_GIG_AGE_DAYS = 10          # older gigs are dropped
SHOW_FULL_TIME = False         # full-time remote jobs are hidden from the gig list by default

# Rough exchange rates to show budgets in rupees (update yearly if you like)
FX_TO_INR = {"INR": 1, "USD": 88, "EUR": 95, "GBP": 112, "AUD": 57, "CAD": 63, "SGD": 66, "AED": 24,
             "NZD": 52, "HKD": 11, "JPY": 0.6, "PHP": 1.5, "PKR": 0.31}

# ============================ AI-TASK PLATFORMS ============================
# Facts as reported by public comparisons in Oct 2026 (parailabs.com/compare/ai-training-platforms,
# herworkcircle.com). Pay and eligibility change often — check each site before applying.
AI_PLATFORMS = [
    {"name": "Mercor", "url": "https://mercor.com", "india": "Yes (India contractor page)",
     "pay": "$10–$190/hr reported; coding & expert roles pay most", "fit": "Coding, ML, STEM projects",
     "payout": "Stripe / Wise, weekly", "priority": 1},
    {"name": "Alignerr", "url": "https://www.alignerr.com", "india": "Yes (ID checks can be slow)",
     "pay": "$40–$120/hr advertised (SWE roles); ~$37/hr measured", "fit": "Software engineering, AI evaluation",
     "payout": "PayPal / Stripe, weekly", "priority": 1},
    {"name": "micro1", "url": "https://www.micro1.ai", "india": "Yes",
     "pay": "~$72/hr average; senior SWE $100–$150/hr", "fit": "Software engineering, AI evaluation",
     "payout": "USD, twice a month", "priority": 1},
    {"name": "Outlier", "url": "https://outlier.ai", "india": "Yes (lower India rates)",
     "pay": "$10–$50/hr typical by tier; coding/CS tracks higher", "fit": "Coding, maths, generalist",
     "payout": "PayPal / Airtm, weekly", "priority": 2},
    {"name": "Turing", "url": "https://www.turing.com", "india": "Yes (India median ~$10/hr reported)",
     "pay": "Wide: $6–$100+/hr", "fit": "Coding, data engineering", "payout": "Deel / bank", "priority": 2},
    {"name": "Handshake AI", "url": "https://joinhandshake.com", "india": "Opening (India sign-ups from Jul 2026)",
     "pay": "$40–$125/hr advertised; India pay not published", "fit": "STEM, students & PhDs",
     "payout": "Stripe, weekly", "priority": 2},
    {"name": "AfterQuery", "url": "https://www.afterquery.com", "india": "Yes (official country list)",
     "pay": "$25–$50/hr verified listing", "fit": "Expert data tasks", "payout": "Stripe, weekly", "priority": 3},
    {"name": "Mindrift", "url": "https://mindrift.ai", "india": "Yes (pay indexed to cost of living)",
     "pay": "Specialists $37–$200/hr; India generalists $5–$15/hr", "fit": "Specialist AI tutor roles",
     "payout": "Payoneer / Tipalti", "priority": 3},
    {"name": "DataAnnotation", "url": "https://www.dataannotation.tech", "india": "No (6 countries only)",
     "pay": "—", "fit": "Not available in India — skip", "payout": "—", "priority": 9},
]

# ============================ RUN LIMITS (free tiers) ============================
GIG_AI_NOTES_PER_RUN = 15      # AI summaries + proposal drafts for the best new gigs per run
DIGEST_TOP_GIGS = 7
DIGEST_HOUR_IST = 8            # the run closest after this hour sends the daily email
