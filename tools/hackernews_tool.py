from __future__ import annotations
import requests
from crewai.tools import BaseTool


class HackerNewsTool(BaseTool):
    name: str = "hackernews_trends"
    description: str = (
        "Fetches top HackerNews stories relevant to a niche. "
        "Good for tech, startup, and developer-focused content."
    )

    def _run(self, query: str) -> str:
        try:
            resp = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": query, "tags": "story", "hitsPerPage": 15},
                timeout=10,
            )
            hits = resp.json().get("hits", [])
            items = [
                f"- [HN] {h['title']} | {h.get('points', 0)} pts | {h.get('num_comments', 0)} comments"
                for h in hits
                if h.get("points", 0) > 10
            ]
            return "\n".join(items) if items else "No relevant HN stories found."
        except Exception as e:
            return f"HackerNews fetch failed: {e}"
