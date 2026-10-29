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

# ============================ CHOICES (change them in the app's ⚙️ Settings tab) ============================
# These are the DEFAULTS. Your picks in the app are saved to the private dataset and override them.

# Every sector you can pick, with the search words used to find companies in it
SECTOR_CATALOG = {
    "bioinformatics":     ["bioinformatics", "computational biology", "AI drug discovery"],
    "supply chain":       ["supply chain AI", "logistics tech"],
    "SDL":                ["self-driving lab", "lab automation AI"],
    "healthtech":         ["healthtech AI", "medical imaging AI"],
    "climate":            ["climate tech", "cleantech energy AI"],
    "EV & batteries":     ["battery tech", "EV battery management"],
    "agritech":           ["agritech AI"],
    "robotics":           ["robotics", "autonomous robots"],
    "drones & defence":   ["drone", "defence tech"],
    "quantum":            ["quantum computing"],
    "semiconductors":     ["semiconductor chip design"],
    "spacetech":          ["spacetech"],
    "materials":          ["materials science AI"],
    "manufacturing":      ["industrial AI manufacturing"],
    "IoT/embedded":       ["IoT embedded systems", "edge AI"],
    "computer vision":    ["computer vision AI"],
    "generative AI":      ["generative AI LLM", "AI agents"],
    "media & content AI": ["video AI", "media tech AI"],
    "cybersecurity":      ["cybersecurity AI"],
    "edtech":             ["edtech AI"],
}

# Cities you can pick (+ remote options)
CITY_OPTIONS = ["Bengaluru", "Pune", "Mumbai", "Hyderabad", "Delhi NCR", "Chennai", "Ahmedabad", "Kolkata",
                "Kochi", "Jaipur", "Indore", "Chandigarh"]
REMOTE_OPTIONS = ["Remote (India)", "Remote (worldwide)"]
CITY_ALIASES = {"Bengaluru": ["bengaluru", "bangalore"], "Delhi NCR": ["delhi", "gurugram", "gurgaon", "noida"],
                "Mumbai": ["mumbai", "navi mumbai", "thane"], "Kochi": ["kochi", "cochin"]}

# Roles you can target: words that must appear in a job title
ROLE_CATALOG = {
    "ML / AI Engineer":           ["machine learning", "ml engineer", "ai engineer", "ml ops", "mlops", "ai/ml", "applied scientist"],
    "LLM / GenAI Engineer":       ["llm", "genai", "generative ai", "nlp", "prompt", "ai agent"],
    "Data Scientist":             ["data scientist", "data science"],
    "Research Engineer":          ["research engineer", "research scientist", "research associate", "research intern"],
    "Computer Vision Engineer":   ["computer vision", "vision engineer", "perception", "image"],
    "Bioinformatics":             ["bioinformatic", "computational biolog", "genomic", "cheminformatic"],
    "Robotics / Autonomy":        ["robotics", "autonomy", "autonomous", "slam", "controls"],
    "Embedded / Firmware":        ["embedded", "firmware", "iot", "fpga"],
    "Software Engineer (Python)": ["python", "backend", "software engineer", "sde", "developer"],
    "Data Analyst":               ["data analyst", "analytics", "business analyst"],
    "Optimisation / Simulation":  ["optimization", "optimisation", "simulation", "operations research"],
}

# What to type into job searches for each role (used by the role radar and the one-click search links)
ROLE_QUERY = {
    "ML / AI Engineer": "Machine Learning Engineer", "LLM / GenAI Engineer": "Generative AI Engineer",
    "Data Scientist": "Data Scientist", "Research Engineer": "AI Research Engineer",
    "Computer Vision Engineer": "Computer Vision Engineer", "Bioinformatics": "Bioinformatics",
    "Robotics / Autonomy": "Robotics Engineer", "Embedded / Firmware": "Embedded Engineer",
    "Software Engineer (Python)": "Python Developer", "Data Analyst": "Data Analyst",
    "Optimisation / Simulation": "Optimization Engineer",
}

DEFAULT_SETTINGS = {
    "main_sectors": ["bioinformatics", "supply chain", "SDL"],             # searched in depth, ranked first
    "other_sectors": ["healthtech", "climate", "EV & batteries", "agritech", "robotics", "drones & defence",
                      "quantum", "semiconductors", "spacetech", "materials", "manufacturing", "IoT/embedded",
                      "computer vision", "generative AI", "media & content AI"],
    "locations": ["Bengaluru", "Pune", "Mumbai", "Hyderabad", "Remote (India)", "Remote (worldwide)"],
    "roles": ["ML / AI Engineer", "LLM / GenAI Engineer", "Data Scientist", "Research Engineer",
              "Computer Vision Engineer", "Bioinformatics", "Optimisation / Simulation"],
    "gig_types": ["ai_tasks", "tech", "content", "marketing"],
}
EXPERIENCE = "Fresher / entry-level"   # fixed: senior roles and roles needing 2+ years are always hidden

# Derived defaults (the pipelines replace these with your saved settings)
SEARCH_TERMS = {s: SECTOR_CATALOG[s] for s in DEFAULT_SETTINGS["main_sectors"] + DEFAULT_SETTINGS["other_sectors"]}
TOP_DOMAINS = list(DEFAULT_SETTINGS["main_sectors"])
CITIES = [c for c in DEFAULT_SETTINGS["locations"] if c in CITY_OPTIONS]
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

# ============================ FILTER SETTINGS (switched on/off by the measured loop: eval/loop.py) ============================
# Every option started OFF (= the original rules). Values below are the ones the loop ACCEPTED (eval/LOOP.md, run 4);
# the rest were measured and rejected — see the log for the numbers.
SHIELD = {
    "word_boundaries": True,       # bug fix: match whole words only ('demonstrate products' is not 'rate products')
    "normalize_text": True,         # undo tricks: 'W h a t s A p p', zero-width characters, look-alike letters
                                    #   ON as a red-team fix (eval/REDTEAM.md): no change on 10,802 EMSCAD train posts,
                                    #   blocks 5 evasion attacks. Not a loop acceptance — the loop found no EMSCAD evidence.
    "negation_guard": False,        # 'no registration fee' / 'we never charge money' must not count as a fee demand
    "chat_contact_only": True,     # WhatsApp/Telegram counts only as a contact channel, not a product ('WhatsApp chatbot' gigs)
    "wfh_money_rules": True,       # classic 'earn $X a week from home, no experience' pattern
    "money_transfer_rules": False,  # payment-processing, reshipping and mystery-shopper scams
    "personal_email_cv": False,     # 'send your CV to ...@gmail.com'
    "weak_signal_combo": 0,         # block when at least N weak warning signs appear together (0 = off)
}
LEVEL = {
    "entry_words_win": True,       # 'Junior Art Director', 'Graduate role': clear entry words in the title beat senior words
    "staff_needs_role": False,      # 'Warehouse Staff' is not 'Staff Engineer'
    "assistant_not_senior": False,  # 'Assistant Manager', 'Executive Assistant to the Chief…' are not senior roles
    "years_patterns_ext": True,    # read more ways of writing years: '3+ yrs', "4 years' experience", 'experience of 5 years'
    "senior_words_ext": False,      # extra senior title words: experienced, team lead, supervisor, head of
    "senior_from_desc": False,      # senior hints in the text: 'seasoned', 'extensive experience', 'proven track record'
    "hide_not_stated": False,       # hide every job whose level is not stated (strict mode)
}

# ============================ RUN LIMITS (free tiers) ============================
GIG_AI_NOTES_PER_RUN = 15      # AI summaries + proposal drafts for the best new gigs per run
ROLE_SEARCHES_PER_RUN = 16     # public job-page searches per role-radar run (rotates through roles × sites × cities)
ROLE_ALERT_EMAILS_PER_RUN = 25 # job-alert emails read per run (LinkedIn, Naukri, Internshala, ...)
ROLE_MAX_AGE_DAYS = 21
DIGEST_TOP_GIGS = 7
DIGEST_HOUR_IST = 8            # the run closest after this hour sends the daily email
