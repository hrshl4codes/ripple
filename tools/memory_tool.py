from __future__ import annotations
from crewai.tools import BaseTool
from pydantic import Field


class MemoryQueryTool(BaseTool):
    name: str = "query_past_performance"
    description: str = (
        "Queries the local vector database for past content that performed well "
        "on a similar topic or hook. Returns top matching posts with their scores."
    )
    top_k: int = Field(default=5)

    def _run(self, query: str) -> str:
        try:
            from memory.chroma_client import get_collection
            collection = get_collection()
            results = collection.query(query_texts=[query], n_results=self.top_k)
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            if not docs:
                return "No past performance data found for this topic yet."
            lines = []
            for doc, meta in zip(docs, metas):
                score = meta.get("engagement_score", "N/A")
                platform = meta.get("platform", "unknown")
                lines.append(f"[{platform}] Score:{score} — {doc[:120]}")
            return "\n".join(lines)
        except Exception as e:
            return f"Memory query unavailable: {e}"
