from __future__ import annotations
import time
import os
from functools import lru_cache
from crewai.tools import BaseTool
from pydantic import Field

_cache: dict[str, tuple[list[str], float]] = {}
CACHE_TTL = 3600  # 1 hour


def _fetch_reddit_trends(niche: str, subreddits: list[str]) -> list[str]:
    cache_key = f"{niche}:{','.join(sorted(subreddits))}"
    if cache_key in _cache:
        posts, ts = _cache[cache_key]
        if time.time() - ts < CACHE_TTL:
            return posts

    try:
        import praw
        client_id = os.getenv("REDDIT_CLIENT_ID", "")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            return _fallback_hn_search(niche)

        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=os.getenv("REDDIT_USER_AGENT", "Ripple/1.0"),
        )
        results: list[str] = []
        targets = subreddits if subreddits else _guess_subreddits(niche)
        for sub in targets[:3]:
            try:
                for post in reddit.subreddit(sub).hot(limit=15):
                    if post.score > 50 and not post.stickied:
                        results.append(f"[r/{sub}] {post.title} ({post.score} upvotes)")
            except Exception:
                continue
        _cache[cache_key] = (results[:20], time.time())
        return results[:20]
    except ImportError:
        return _fallback_hn_search(niche)


def _fallback_hn_search(niche: str) -> list[str]:
    import requests
    try:
        resp = requests.get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": niche, "tags": "story", "hitsPerPage": 20},
            timeout=10,
        )
        hits = resp.json().get("hits", [])
        return [
            f"[HN] {h['title']} ({h.get('points', 0)} pts)"
            for h in hits
            if h.get("points", 0) > 20
        ][:15]
    except Exception:
        return []


def _guess_subreddits(niche: str) -> list[str]:
    mapping = {
        "ai": ["artificial", "MachineLearning", "ChatGPT"],
        "saas": ["SaaS", "entrepreneur", "startups"],
        "fitness": ["fitness", "loseit", "bodyweightfitness"],
        "finance": ["personalfinance", "investing", "Fire"],
        "productivity": ["productivity", "getdisciplined", "LifeProTips"],
        "marketing": ["marketing", "digital_marketing", "Entrepreneur"],
        "tech": ["technology", "programming", "webdev"],
        "crypto": ["CryptoCurrency", "Bitcoin", "ethereum"],
    }
    niche_lower = niche.lower()
    for key, subs in mapping.items():
        if key in niche_lower:
            return subs
    return ["entrepreneur", "productivity", "technology"]


class RedditTrendTool(BaseTool):
    name: str = "reddit_trends"
    description: str = (
        "Fetches trending posts from Reddit (and HackerNews as fallback) "
        "for a given niche. Returns a list of trending titles with engagement scores."
    )
    niche: str = Field(default="")
    subreddits: list[str] = Field(default_factory=list)

    def _run(self, query: str) -> str:
        trends = _fetch_reddit_trends(self.niche or query, self.subreddits)
        if not trends:
            return "No trends found. Try a broader niche or check API credentials."
        return "\n".join(f"- {t}" for t in trends)
