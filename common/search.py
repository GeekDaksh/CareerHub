"""Free web search with fallbacks: DuckDuckGo -> Tavily -> Serper (Google). Results cached on disk."""
import json
import os
import random
import re
import time

import requests

SERPER_KEY = os.environ.get("SERPER_API_KEY")
TAVILY_KEY = os.environ.get("TAVILY_API_KEY")
PAUSE = float(os.environ.get("SEARCH_PAUSE", "2"))


def ddg(query, n=10):
    try:
        from ddgs import DDGS
    except ImportError:
        return None
    for attempt in range(3):
        try:
            res = DDGS().text(query, region="in-en", max_results=n) or []
            time.sleep(PAUSE + random.random())
            return [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")} for r in res if r.get("href")]
        except Exception as e:
            if "no results" in str(e).lower():
                return []
            time.sleep(PAUSE * 4 * (attempt + 1))
    return None


def tavily(query, n=10):
    if not TAVILY_KEY:
        return None
    body = {"query": query, "max_results": n, "search_depth": "basic"}
    m = re.search(r"\bsite:(\S+)", query)
    if m:
        body["include_domains"] = [m.group(1).split("/")[0]]
        body["query"] = re.sub(r"\bsite:\S+\s*", "", query).strip()
    try:
        r = requests.post("https://api.tavily.com/search", json=body, timeout=30,
                          headers={"Authorization": f"Bearer {TAVILY_KEY}"})
        if r.status_code != 200:
            return None
        return [{"title": o.get("title", ""), "url": o.get("url", ""), "snippet": o.get("content", "")}
                for o in r.json().get("results", []) if o.get("url")]
    except Exception:
        return None


def serper(query, n=10):
    if not SERPER_KEY:
        return None
    try:
        r = requests.post("https://google.serper.dev/search", timeout=20,
                          headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                          json={"q": query, "gl": "in", "num": n, "tbs": "qdr:w"})
        if r.status_code != 200:
            return None
        return [{"title": o.get("title", ""), "url": o.get("link", ""), "snippet": o.get("snippet", "")}
                for o in r.json().get("organic", []) if o.get("link")]
    except Exception:
        return None


class Searcher:
    def __init__(self, cache_path, max_age_days=3):
        self.path, self.max_age = cache_path, max_age_days * 86400
        try:
            with open(cache_path) as f:
                self.cache = json.load(f)
        except Exception:
            self.cache = {}

    def search(self, query, n=10):
        hit = self.cache.get(query)
        if hit and time.time() - hit["at"] < self.max_age:
            return hit["results"]
        res = None
        for engine in (ddg, tavily, serper):
            res = engine(query, n)
            if res is not None:
                break
        if res is not None:
            self.cache[query] = {"at": time.time(), "results": res}
        return res or []

    def save(self):
        old = time.time() - 30 * 86400
        self.cache = {k: v for k, v in self.cache.items() if v["at"] > old}
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.cache, f)
