from __future__ import annotations
import os
import requests
from crewai.tools import BaseTool


class SerperSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Searches the web via Google (Serper API) for current trends, "
        "news, and conversations about a topic."
    )

    def _run(self, query: str) -> str:
        api_key = os.getenv("SERPER_API_KEY", "")
        if not api_key:
            return "SERPER_API_KEY not set — web search unavailable."
        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": 10},
                timeout=10,
            )
            data = resp.json()
            results = []
            for item in data.get("organic", [])[:8]:
                results.append(f"- {item.get('title', '')} — {item.get('snippet', '')}")
            return "\n".join(results) if results else "No results found."
        except Exception as e:
            return f"Search failed: {e}"
