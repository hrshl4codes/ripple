from __future__ import annotations
import os
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

_client: chromadb.PersistentClient | None = None
_collection = None

COLLECTION_NAME = "ripple_content_performance"


def get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./memory/performance_db")
        os.makedirs(persist_dir, exist_ok=True)
        _client = chromadb.PersistentClient(path=persist_dir)
    return _client


def get_collection():
    global _collection
    if _collection is None:
        ef = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2",
            device="cpu",
        )
        _collection = get_client().get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def upsert_content(
    content_id: str,
    text: str,
    platform: str,
    niche: str,
    predicted_score: float,
    engagement_score: float = 0.0,
) -> None:
    collection = get_collection()
    collection.upsert(
        ids=[content_id],
        documents=[text],
        metadatas=[{
            "platform": platform,
            "niche": niche,
            "predicted_score": predicted_score,
            "engagement_score": engagement_score,
        }],
    )
