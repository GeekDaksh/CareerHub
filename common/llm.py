"""Free AI calls: every free Gemini/Gemma model first (each has its own daily quota), then Groq."""
import json
import os
import re
import time

import requests

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
PREFERRED = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
GROQ_MODELS = ["llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b-16e-instruct", "openai/gpt-oss-120b"]
PAUSE = float(os.environ.get("GEMINI_PAUSE", "7"))

_client = None
_models = None
_dead = set()
# Time budget for ALL AI calls in one run. Free-tier rate limits answer with "wait and retry"; without a budget,
# 15 gig notes x several models x growing back-off could keep a scheduled run busy for half an hour.
BUDGET = float(os.environ.get("AI_BUDGET_SECONDS", "300"))
_started = None


def _over_budget():
    global _started
    if _started is None:
        _started = time.time()
    return time.time() - _started > BUDGET


def _nap(secs):
    """Sleep, but never past the run's AI budget."""
    if _started is not None:
        secs = max(0, min(secs, BUDGET - (time.time() - _started)))
    time.sleep(secs)


def parse_json(text):
    if not text:
        return None
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(t)
    except Exception:
        pass
    for a in sorted(i for i in (t.find("["), t.find("{")) if i != -1):
        b = t.rfind("]" if t[a] == "[" else "}")
        if b > a:
            try:
                return json.loads(t[a:b + 1])
            except Exception:
                pass
    return None


def _gemini_models():
    global _client, _models
    if _models is not None:
        return _models
    _models = []
    if not GEMINI_KEY:
        return _models
    from google import genai
    _client = genai.Client(api_key=GEMINI_KEY)
    skip = ["image", "tts", "audio", "live", "embedding", "preview", "exp", "thinking", "nano", "robotics", "computer"]
    try:
        avail = [m.name.split("/")[-1] for m in _client.models.list()
                 if "generateContent" in (getattr(m, "supported_actions", None) or [])]
    except Exception:
        avail = list(PREFERRED)
    ok = [m for m in PREFERRED if m in avail]
    extra = [m for m in avail if m not in ok and ("flash" in m or "gemma-3-27b" in m or "gemma-3-12b" in m)
             and not any(x in m for x in skip)]
    _models = ok + sorted(extra, key=lambda m: ("gemma" in m, "lite" in m, m))
    return _models


def _ask_gemini(prompt, temperature):
    for model in _gemini_models():
        if model in _dead:
            continue
        for attempt in range(3):
            if _over_budget():
                return None
            try:
                cfg = {"temperature": temperature}
                if "gemma" not in model:
                    cfg["response_mime_type"] = "application/json"
                r = _client.models.generate_content(model=model, contents=prompt, config=cfg)
                time.sleep(PAUSE)
                out = parse_json(r.text)
                if out is not None:
                    return out
                break
            except Exception as e:
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    if "PerDay" in msg or "per day" in msg.lower():
                        _dead.add(model)
                        break
                    _nap(30 * (attempt + 1))
                elif "404" in msg or "NOT_FOUND" in msg:
                    _dead.add(model)
                    break
                elif any(c in msg for c in ("500", "503", "UNAVAILABLE", "INTERNAL", "DEADLINE")):
                    _nap(10 * (attempt + 1))
                else:
                    print("  gemini:", msg[:160])
                    break
    return None


def _ask_groq(prompt, temperature):
    if not GROQ_KEY:
        return None
    wrapped = ('Answer with ONE JSON object of the form {"result": <your answer>}.\n\n' + prompt)[:24000]
    for model in GROQ_MODELS:
        if "groq:" + model in _dead:
            continue
        for attempt in range(3):
            if _over_budget():
                return None
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
                return out
            if r.status_code == 429:
                if any(k in r.text for k in ("per day", "RPD", "TPD")):
                    _dead.add("groq:" + model)
                    break
                _nap(20 * (attempt + 1))
            else:
                if r.status_code == 404:
                    _dead.add("groq:" + model)
                break
    return None


def ask_json(prompt, temperature=0.3):
    out = _ask_gemini(prompt, temperature)
    return out if out is not None else _ask_groq(prompt, temperature)


def exhausted():
    if _started is not None and _over_budget():
        return True
    gm = _gemini_models()
    return all(m in _dead for m in gm) and (not GROQ_KEY or all("groq:" + m in _dead for m in GROQ_MODELS))
